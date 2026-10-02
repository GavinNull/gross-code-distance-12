"""单一评估入口（评估器 v2，2026-10-02）。

    from evaluators.pipeline import evaluate
    rep = evaluate("gross-sd6-p4e-3", None, schedule_json, seed=20261002)
    print(rep.to_text())            # 可直接喂给 LLM 的逐项诊断
    rep.status, rep.score, rep.leaderboard_record

流程（全部由评估器完成，候选只提供 code_spec 与调度 JSON）：
  1. 从冻结的任务注册表（evaluators/tasks.py）取任务；码由任务的码族与 code_spec 生成（逻辑算符评估器自己算）。
  2. 解析、校验调度（evaluators/candidate.py 的模板约束），不合法 → "rejected_schedule"，附可读诊断。
  3. 评估器用模板生成每个需要的轮数（打分轮数 r2；diff 时还有 r1；距离用 distance_rounds）的两个基底电路。
  4. L0：每个打分轮数的电路都过完整 L0（不含距离），并核对 L0 实测的每个生成元测量次数 = 该轮数；
     距离在 distance_rounds 轮电路上做（同一调度、同一模板）。任一不过 → "rejected_l0"。
  5. 分层漏斗（任务的 funnel.tiers，E-004 之后填）：每层一次小预算采样，不达标 → "filtered"。
  6. L2：X/Z 联合采样，任务的噪声、p、解码器、边界、停止规则。diff 时两个轮数的电路都由评估器生成。
     diff 点估计为负 → "rejected_l2"；任一 sector 失败数 < 1000 → "insufficient_statistics"（不上榜）。
  7. 环境核对（库版本 = tasks.PINNED_VERSIONS；冻结后评估器文件与清单一致），通过后由本模块写成绩单
     （leaderboard._append 只接受本模块的凭证；记录由本模块从自己的计算结果组装，调用方不能传字典进去）。

成绩（score）：体内 / 单次运行的每轮 P_any（`l2.per_round["P_any"]`，口径由任务的 boundary 决定），以及除以 k 的
“每逻辑比特每轮”值（H-003 指标 B）。
"""
from __future__ import annotations

import dataclasses
import importlib.metadata as md
import time
from dataclasses import dataclass, field
from typing import Mapping

import numpy as np

from evaluators import candidate as cand
from evaluators import tasks as tasks_mod
from evaluators.l0 import L0Constraints, check_l0
from evaluators.l2 import DecoderConfig, StopRule, circuit_hash, sample_l2

__all__ = ["Report", "evaluate", "STATUSES"]

STATUSES = ("scored", "rejected_code", "rejected_schedule", "rejected_l0", "filtered", "rejected_l2",
            "insufficient_statistics")

TEMPLATE_GATES = frozenset({"R", "RX", "M", "MX", "CX"})

# 写榜凭证：只有本模块持有。leaderboard._append 用身份比较核对（防误用，不防同进程里的恶意代码；
# 后者靠沙箱 + verify_leaderboard 的语义核对 + reproduce_entry 复算，见 README §8）。
_CREDENTIAL = object()

# 注册表在导入时的哈希；运行时任务对象被改动则拒绝评估。
_REGISTERED_TASK_HASHES = {tid: t.hash() for tid, t in tasks_mod.TASKS.items()}


@dataclass
class Report:
    task_id: str
    status: str
    candidate_id: str | None = None
    task_hash: str | None = None
    seed: int | None = None
    code: dict = field(default_factory=dict)
    schedule: dict | None = None
    schedule_hash: str | None = None
    circuit_hashes: dict = field(default_factory=dict)     # 轮数 -> 两个基底无噪声电路的 sha256
    rounds_verified: dict = field(default_factory=dict)    # 轮数 -> L0 实测的测量次数（全部生成元）
    diagnostics: list = field(default_factory=list)
    l0: dict = field(default_factory=dict)                 # "r=<R>" / "distance r=<R>" -> L0Report.to_dict()
    l0_text: dict = field(default_factory=dict)
    distance_upper_bound: int | None = None
    funnel: list = field(default_factory=list)
    l2: dict | None = None
    score: dict | None = None
    eligible: bool = False
    ineligible_reasons: list = field(default_factory=list)
    leaderboard_record: dict | None = None
    environment: dict = field(default_factory=dict)
    timing: dict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == "scored"

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    def to_text(self) -> str:
        lines = [f"EVALUATION {self.status.upper()} [task {self.task_id}]"
                 + (f" schedule {self.schedule_hash[:12]}" if self.schedule_hash else "")]
        for d in self.diagnostics:
            lines.append(f"  - {d}")
        for key, txt in self.l0_text.items():
            lines.append(f"--- L0 ({key})")
            lines.append(txt)
        for t in self.funnel:
            lines.append(f"--- funnel tier {t['name']}: {t['decision']} (per-round P_any {t.get('per_round_P_any')})")
        if self.score:
            s = self.score
            lines.append(f"--- score: per-round P_any = {s['per_round_P_any']['best']:.4e} "
                         f"[{s['per_round_P_any']['low']:.4e}, {s['per_round_P_any']['high']:.4e}] "
                         f"({s['definition']}); per logical qubit {s['per_round_per_logical']:.4e}")
        if self.ineligible_reasons:
            lines.append("--- not put on the leaderboard: " + "; ".join(self.ineligible_reasons))
        elif self.leaderboard_record is not None:
            lines.append(f"--- leaderboard: appended as seq {self.leaderboard_record['seq']}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------

def _l0_constraints(task, code, rounds: int, *, with_distance: bool) -> L0Constraints:
    lay = cand.layout_for(code)
    kw = dict(data_qubits=list(lay.data), max_qubits=lay.num_qubits, allowed_edges=cand.template_edges(code),
              allowed_gates=TEMPLATE_GATES, rounds=rounds, require_opposite_type_detectors=False)
    if with_distance:
        L = task.l0
        kw.update(min_circuit_distance=L["min_circuit_distance"], distance_seed=L.get("distance_seed", 0),
                  distance_bposd_trials=L.get("distance_bposd_trials", 1500),
                  distance_lns_starts=L.get("distance_lns_starts", 96),
                  distance_timeout_s=L.get("distance_timeout_s", 1800.0),
                  distance_num_workers=task.num_workers)
    return L0Constraints(**kw)


def _decoder(task) -> DecoderConfig:
    return DecoderConfig(task.decoder["name"], dict(task.decoder.get("params") or {}))


def _stop(task, override: Mapping | None = None) -> StopRule:
    d = dict(task.stop)
    if override:
        d.update(override)
    return StopRule(max_shots=int(d["max_shots"]), max_errors=d.get("max_errors"),
                    min_sector_errors=d.get("min_sector_errors"), batch_size=int(d.get("batch_size", 256)))


def environment_check() -> dict:
    """库版本与冻结完整性。返回 {"ok": bool, "problems": [...], "versions": {...}, "evaluator": {...}}。"""
    problems = []
    versions = {}
    for pkg, want in tasks_mod.PINNED_VERSIONS.items():
        try:
            have = md.version(pkg)
        except md.PackageNotFoundError:
            have = None
        versions[pkg] = have
        if have != want:
            problems.append(f"{pkg} {have} != pinned {want}")
    from evaluators import leaderboard as lb
    ev = lb.evaluator_hash()
    if ev.get("frozen") and not ev.get("verified"):
        problems.append("evaluator is frozen but its files do not match the frozen manifest: "
                        + "; ".join(ev.get("problems", [])[:5]))
    return {"ok": not problems, "problems": problems, "versions": versions, "evaluator": ev}


def _verified_rounds(rep) -> dict:
    out = {}
    for b, sub in rep.per_basis.items():
        cov = sub.get("stabilizer_coverage")
        out[b] = sorted(set((cov.details or {}).get("counts", {}).values()))
    return out


def evaluate(task_id: str, code_spec: Mapping | None, schedule, *, seed: int, candidate_id: str | None = None,
             leaderboard_path=None, submit: bool = True, work_dir=None) -> Report:
    """评估一个候选调度（见模块说明）。只有通过全部检查且统计量足够的结果才会写进成绩单。

    Args:
        task_id: 任务注册表里的任务。
        code_spec: 码族参数（fixed 码的任务可传 None）。
        schedule: 调度 JSON（字符串或 dict），规范见 evaluators/candidate.py。
        seed: L2 采样种子（非负整数）。
        candidate_id: 写进成绩单的候选名（可选）。
        leaderboard_path: 成绩单路径（默认 research/leaderboard.jsonl；测试必须传临时路径）。
        submit: False 时只评估、不写榜。
    """
    task = tasks_mod.get_task(task_id)
    return _evaluate_task(task, code_spec, schedule, seed=seed, candidate_id=candidate_id,
                          leaderboard_path=leaderboard_path, submit=submit, work_dir=work_dir,
                          registered=True)


def _evaluate_task(task, code_spec, schedule, *, seed, candidate_id=None, leaderboard_path=None, submit=True,
                   work_dir=None, registered=False) -> Report:
    t0 = time.time()
    rep = Report(task_id=task.task_id, status="rejected_code", candidate_id=candidate_id, task_hash=task.hash(),
                 seed=seed)
    if registered and _REGISTERED_TASK_HASHES.get(task.task_id) != task.hash():
        raise RuntimeError(f"task {task.task_id} was modified at runtime (hash mismatch with the registry)")
    if not isinstance(seed, (int, np.integer)) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a non-negative int")

    # ---- 码
    try:
        code, norm = tasks_mod.build_code(task, code_spec)
    except tasks_mod.CodeSpecError as e:
        rep.diagnostics.append(f"code rejected: {e}")
        return _finish(rep, t0)
    rep.code = {"spec": norm, "name": code.name, "n": int(code.n), "k": int(code.k),
                "HX_rows": int(code.HX.shape[0]), "HZ_rows": int(code.HZ.shape[0]),
                "checks_sha256": tasks_mod.code_hash(code)}

    # ---- 调度
    rep.status = "rejected_schedule"
    try:
        spec = cand.parse_schedule(schedule)
        problems = cand.validate_schedule(spec, code)
        if problems:
            raise cand.ScheduleError(problems)
    except cand.ScheduleError as e:
        rep.diagnostics.extend(e.problems)
        return _finish(rep, t0)
    rep.schedule = spec.canonical().to_dict()
    rep.schedule_hash = spec.hash()

    # ---- 电路（全部由评估器生成）
    score_rounds = [task.rounds] if task.boundary != "diff" else [task.boundary_options["diff_rounds"], task.rounds]
    dist_rounds = int(task.l0.get("distance_rounds", task.rounds))
    circuits = {}
    try:
        for R in sorted(set(score_rounds) | {dist_rounds}):
            circuits[R] = cand.build_circuits(spec, code, R)
    except cand.ScheduleError as e:
        rep.diagnostics.extend(e.problems)
        return _finish(rep, t0)
    rep.circuit_hashes = {str(R): circuit_hash(c) for R, c in circuits.items()}

    # ---- L0（每个打分轮数都过，距离在 distance_rounds 上）
    rep.status = "rejected_l0"
    l0_ok = True
    for R in score_rounds:
        with_d = R == dist_rounds
        r = check_l0(circuits[R], code, "both", _l0_constraints(task, code, R, with_distance=with_d))
        key = f"r={R}" + (" (with distance)" if with_d else "")
        rep.l0[key] = r.to_dict()
        rep.l0_text[key] = r.to_text()
        if r.passed:
            vr = _verified_rounds(r)
            rep.rounds_verified[str(R)] = vr
            if any(v != [R] for v in vr.values()):
                l0_ok = False
                rep.diagnostics.append(f"internal: L0 counted {vr} measurements per generator, expected {R}")
            if with_d:
                rep.distance_upper_bound = r.d_circ
        else:
            l0_ok = False
    if dist_rounds not in score_rounds:
        r = check_l0(circuits[dist_rounds], code, "both", _l0_constraints(task, code, dist_rounds, with_distance=True))
        key = f"distance r={dist_rounds}"
        rep.l0[key] = r.to_dict()
        rep.l0_text[key] = r.to_text()
        rep.distance_upper_bound = r.d_circ
        l0_ok = l0_ok and r.passed
    if not l0_ok:
        rep.diagnostics.append("L0 failed (see the L0 reports below)")
        return _finish(rep, t0)

    # ---- 分层漏斗（E-004 之后填配置）
    tiers = list((task.funnel or {}).get("tiers") or [])
    lay = cand.layout_for(code)
    for ti, tier in enumerate(tiers):
        res = sample_l2(code, circuits[task.rounds], list(lay.data), p=task.p, rounds=task.rounds,
                        noise_model=task.noise_model, boundary="paper", decoder=_decoder(task),
                        seed=int(np.random.SeedSequence([int(seed), ti, 0x7135]).generate_state(1)[0]),
                        stop=_stop(task, tier.get("stop")), num_workers=task.num_workers)
        pr = res.per_round["P_any"]
        thr = tier.get("promote_if_per_round_P_any_below")
        decision = "promote" if thr is None or (pr["low"] is not None and pr["low"] < thr) else "reject"
        rep.funnel.append({"name": tier.get("name", f"tier{ti}"), "decision": decision,
                           "per_round_P_any": pr["best"], "counts": res.counts, "threshold": thr})
        if decision != "promote":
            rep.status = "filtered"
            rep.diagnostics.append(f"filtered at funnel tier {tier.get('name', ti)}: per-round P_any lower bound "
                                   f"{pr['low']} >= {thr}")
            return _finish(rep, t0)

    # ---- L2
    rep.status = "rejected_l2"
    kwargs = dict(p=task.p, noise_model=task.noise_model, decoder=_decoder(task), seed=int(seed), stop=_stop(task),
                  num_workers=task.num_workers, work_dir=work_dir)
    data = list(lay.data)
    if task.boundary == "diff":
        r1 = task.boundary_options["diff_rounds"]
        res = sample_l2(code, {r1: circuits[r1], task.rounds: circuits[task.rounds]}, data, rounds=task.rounds,
                        boundary="diff", diff_rounds=r1, diff_inner_boundary=task.boundary_options.get("inner", "paper"),
                        **kwargs)
    else:
        res = sample_l2(code, circuits[task.rounds], data, rounds=task.rounds, boundary=task.boundary, **kwargs)
    rep.l2 = res.to_dict()
    pr = res.per_round["P_any"]
    if task.boundary == "diff":
        bad = [key for key in ("P_Z", "P_X", "P_any") if not res.per_round[key]["diff"].get("valid")]
        if bad:
            rep.diagnostics.append(f"diff estimate invalid (negative or saturated) for {bad}: "
                                   + "; ".join(res.per_round[k]["diff"].get("warning", "") for k in bad))
            return _finish(rep, t0)
        runs = [res.components[str(r)]["counts"] for r in (r1, task.rounds)]
    else:
        runs = [res.counts]
    rep.score = {"per_round_P_any": {"best": pr["best"], "low": pr["low"], "high": pr["high"]},
                 "per_round_per_logical": pr["best"] / code.k,
                 "definition": ("bulk per-round P_any from rounds "
                                f"{task.boundary_options.get('diff_rounds')} and {task.rounds} (diff)"
                                if task.boundary == "diff" else
                                f"per-round P_any 1-(1-P)^(1/{task.rounds}) of one {task.rounds}-round run "
                                f"({task.boundary} boundary)"),
                 "k": int(code.k)}
    rep.status = "scored"

    # ---- 上榜资格
    need = tasks_mod.MIN_SECTOR_ERRORS_FOR_LEADERBOARD
    for c in runs:
        if min(c["fail_Z"], c["fail_X"]) < need:
            rep.ineligible_reasons.append(f"fewer than {need} logical failures in a sector (Z {c['fail_Z']}, "
                                          f"X {c['fail_X']}, shots {c['shots']}): budget exhausted before the "
                                          f"stop rule; small-sample results are not ranked")
            rep.status = "insufficient_statistics"
    env = environment_check()
    rep.environment = env
    if not env["ok"]:
        rep.ineligible_reasons.extend(env["problems"])
    from evaluators import leaderboard as lb
    to_official = leaderboard_path is None or str(leaderboard_path) == str(lb.DEFAULT_PATH)
    if to_official and task.purpose == "score" and not env["evaluator"].get("verified"):
        rep.ineligible_reasons.append("the evaluator is not frozen (or does not match its frozen manifest); only "
                                      "the frozen evaluator may write research results to the official leaderboard")
    if to_official and task.purpose != "score":
        rep.ineligible_reasons.append(f"task purpose {task.purpose!r} is never written to the official leaderboard")
    if not submit:
        rep.ineligible_reasons.append("submit=False")
    rep.eligible = not rep.ineligible_reasons
    if rep.eligible:
        rep.leaderboard_record = lb._append(_record(rep, task), leaderboard_path, _CREDENTIAL)
    return _finish(rep, t0)


def _finish(rep: Report, t0: float) -> Report:
    rep.timing["wall_s"] = round(time.time() - t0, 2)
    return rep


def _record(rep: Report, task) -> dict:
    """成绩单条目（只由本模块从自己的计算结果组装）。"""
    l2 = rep.l2
    inp = l2["inputs"]
    return {
        "candidate_id": rep.candidate_id,
        "task_id": task.task_id,
        "task_hash": task.hash(),
        "purpose": task.purpose,
        "code": rep.code,
        "schedule": rep.schedule,
        "schedule_hash": rep.schedule_hash,
        "circuit_hashes": rep.circuit_hashes,
        "rounds_verified": rep.rounds_verified,
        "noise_model": inp["noise_model"],
        "p": inp["p"],
        "rounds": task.rounds,
        "boundary": task.boundary,
        "boundary_options": dict(task.boundary_options),
        "seed": rep.seed,
        "l0": {k: {"passed": v["passed"], "d_circ": v["d_circ"], "d_circ_per_basis": v["d_circ_per_basis"],
                   "checks": {c["name"]: c["status"] for c in v["checks"]}} for k, v in rep.l0.items()},
        "distance_upper_bound": rep.distance_upper_bound,
        "score": rep.score,
        "l2": l2,
    }
