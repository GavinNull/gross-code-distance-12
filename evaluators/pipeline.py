"""单一评估入口（评估器 v2.1，2026-10-02）。

    from evaluators.pipeline import evaluate, screen
    rep = evaluate("gross-sd6-p4e-3", None, schedule_json)       # 正式任务的种子由评估器派生
    print(rep.to_text())            # 可直接喂给 LLM 的逐项诊断
    rep.status, rep.score, rep.leaderboard_record
    rep = screen("bb90-dcirc", None, schedule_json)              # 搜索内循环：只跑 L0 + 距离，不写榜

流程（全部由评估器完成，候选只提供 code_spec 与调度 JSON）：
  0. 运行时完整性（auditor v2 F7）：sys.pycache_prefix 必须为 None，每个已加载的 evaluators.* 模块的源文件与
     字节码缓存路径都必须在 evaluators/ 内、由源文件加载。否则直接抛 RuntimeError。
  1. 从冻结的任务注册表（evaluators/tasks.py）取任务；码由任务的码族与 code_spec 生成（逻辑算符评估器自己算）。
  2. 解析、校验调度（evaluators/candidate.py 的模板约束 + 任务的 schedule_constraints），不合法 → "rejected_schedule"。
  3. 评估器用**规范化调度** spec.canonical() 生成每个需要的轮数的两个基底电路（auditor v2 S1：保证“哈希相同 ⇔ 电路相同”），
     并直接从电路核对模板结构（每行每轮恰好被自己的辅助比特测一次，candidate.template_round_counts）。
  4. L0：每个打分轮数的电路都过完整 L0（不含距离），flow 计数按“每行自己的辅助比特”数窗口（auditor v2 S8）；
     距离在 distance_rounds 轮电路上做。任一不过 → "rejected_l0"。距离见证翻译成调度坐标（Report.distance）。
  5. kind="distance" 的任务（H-004）到此为止：分数 = 距离上界（越大越好），并列看最小权重见证数、周期。
  6. 分层漏斗、L2（X/Z 联合采样）；批文件逐个核对 HMAC 等并随机抽查重算（auditor v2 S4），不一致 → "integrity_error"。
  7. 环境核对（库版本、冻结完整性、运行时完整性），正式成绩单只收已冻结评估器 + purpose="score" 的任务
     （路径 resolve 后比较，auditor v2 S10），由本模块写入。

种子（auditor v2 S5）：purpose="score" 的任务，L2 种子 = derive_seed(task_hash, schedule_hash, "l2")，调用方传入的 seed
被忽略（Report.diagnostics 里记一条）；距离任务的距离种子 = derive_seed(..., "distance")。自检任务可以用调用方的种子。
"""
from __future__ import annotations

import dataclasses
import hashlib
import importlib.machinery
import importlib.metadata as md
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import numpy as np

from evaluators import candidate as cand
from evaluators import tasks as tasks_mod
from evaluators.l0 import L0Constraints, check_l0
from evaluators.l2 import DecoderConfig, L2IntegrityError, StopRule, circuit_hash, sample_l2

__all__ = ["Report", "evaluate", "screen", "STATUSES", "derive_seed", "runtime_integrity", "environment_check",
           "circuits_for"]

STATUSES = ("scored", "screened", "rejected_code", "rejected_schedule", "rejected_l0", "filtered", "rejected_l2",
            "insufficient_statistics", "integrity_error")

TEMPLATE_GATES = frozenset({"R", "RX", "M", "MX", "CX"})
EVAL_DIR = Path(__file__).resolve().parent

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
    kind: str = "l2"
    seed: int | None = None                                # L2 种子（距离任务：距离种子）
    code: dict = field(default_factory=dict)
    schedule: dict | None = None
    schedule_hash: str | None = None
    circuit_hashes: dict = field(default_factory=dict)     # 轮数 -> 两个基底无噪声电路的 sha256
    rounds_verified: dict = field(default_factory=dict)    # 轮数 -> 每行被测次数（模板结构核对 + L0 flow 计数一致）
    diagnostics: list = field(default_factory=list)
    l0: dict = field(default_factory=dict)                 # "r=<R>" / "distance r=<R>" -> L0Report.to_dict()
    l0_text: dict = field(default_factory=dict)
    distance_upper_bound: int | None = None
    distance: dict | None = None                           # 距离详情：每个基底的权重、见证（调度坐标）、低权重见证数
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
        return self.status in ("scored", "screened")

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    def to_text(self, witness_limit: int = 24) -> str:
        lines = [f"EVALUATION {self.status.upper()} [task {self.task_id}]"
                 + (f" schedule {self.schedule_hash[:12]}" if self.schedule_hash else "")]
        for d in self.diagnostics:
            lines.append(f"  - {d}")
        for key, txt in self.l0_text.items():
            lines.append(f"--- L0 ({key})")
            lines.append(txt)
        if self.distance:
            dd = self.distance
            per = ", ".join(f"{b}: {v.get('weight')}" for b, v in dd["per_basis"].items())
            lines.append(f"--- circuit distance (upper bound, {dd['rounds']} rounds, seed {dd['seed']}): "
                         f"d_circ <= {dd['d_circ_upper_bound']} ({per}); minimum-weight witnesses found: "
                         f"{dd['low_weight_witnesses']}")
            for b, v in dd["per_basis"].items():
                if not v.get("coords"):
                    continue
                lines.append(f"    shortest witness, {b} basis (weight {v['weight']}, found by {v['method']}, "
                             f"flips logical observables {v.get('flipped_observables')}), in schedule coordinates "
                             f"(cycle/step = period coordinates of the schedule JSON; round = instance of that check):")
                for c in v["coords"][:witness_limit]:
                    lines.append(f"      {c['text']}")
                if len(v["coords"]) > witness_limit:
                    lines.append(f"      ... ({len(v['coords']) - witness_limit} more)")
        for t in self.funnel:
            lines.append(f"--- funnel tier {t['name']}: {t['decision']} (per-round P_any {t.get('per_round_P_any')})")
        if self.score and self.kind == "distance":
            s = self.score
            lines.append(f"--- score: d_circ upper bound {s['d_circ_upper_bound']} (larger is better); ties: "
                         f"{s['low_weight_witnesses']} minimum-weight witnesses (fewer is better), period "
                         f"{s['period']} (smaller is better)")
        elif self.score:
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
# 种子、运行时完整性、环境
# ---------------------------------------------------------------------------

def derive_seed(task_hash: str, schedule_hash: str, purpose: str) -> int:
    """评估器派生的种子（auditor v2 S5）：sha256("qec-eval-seed|purpose|task_hash|schedule_hash") 的前 63 位。"""
    h = hashlib.sha256(f"qec-eval-seed|{purpose}|{task_hash}|{schedule_hash}".encode()).digest()
    return int.from_bytes(h[:8], "big") >> 1


def _inside(p, d: Path) -> bool:
    rp = Path(p).resolve()
    return rp == d or d in rp.parents


def runtime_integrity() -> list[str]:
    """auditor v2 F7：字节码缓存不能放在 evaluators/ 之外；每个已加载的 evaluators.* 模块必须从 evaluators/ 里的
    .py 源文件加载（SourceFileLoader），缓存路径 __cached__ 在 evaluators/__pycache__ 里。返回问题列表。"""
    probs = []
    if sys.pycache_prefix is not None:
        probs.append(f"sys.pycache_prefix is set ({sys.pycache_prefix!r}; PYTHONPYCACHEPREFIX / -X pycache_prefix): "
                     f"byte code would be cached outside the protected evaluators/ directory")
    cache_dir = EVAL_DIR / "__pycache__"
    for name, mod in sorted(sys.modules.items()):
        if mod is None or (name != "evaluators" and not name.startswith("evaluators.")):
            continue
        f = getattr(mod, "__file__", None)
        spec = getattr(mod, "__spec__", None)
        if f is None or not _inside(f, EVAL_DIR):
            probs.append(f"module {name} loaded from {f!r}, outside {EVAL_DIR}")
            continue
        if spec is not None and spec.origin and not _inside(spec.origin, EVAL_DIR):
            probs.append(f"module {name}: spec origin {spec.origin!r} outside {EVAL_DIR}")
        loader = getattr(spec, "loader", None) if spec is not None else getattr(mod, "__loader__", None)
        if not isinstance(loader, importlib.machinery.SourceFileLoader) or not str(f).endswith(".py"):
            probs.append(f"module {name} was not loaded from a .py source file (loader {type(loader).__name__})")
        cached = getattr(mod, "__cached__", None)
        if cached is not None and not _inside(cached, cache_dir):
            probs.append(f"module {name}: byte-code cache {cached!r} outside {cache_dir}")
    return probs


def _assert_runtime_integrity() -> None:
    probs = runtime_integrity()
    if probs:
        raise RuntimeError("evaluator runtime integrity check failed: " + "; ".join(probs[:5]))


def environment_check() -> dict:
    """库版本、冻结完整性、运行时完整性。返回 {"ok": bool, "problems": [...], "versions": {...}, "evaluator": {...}}。"""
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
    problems.extend(runtime_integrity())
    return {"ok": not problems, "problems": problems, "versions": versions, "evaluator": ev}


# ---------------------------------------------------------------------------
# 约束、电路
# ---------------------------------------------------------------------------

def _own_ancillas(code) -> dict:
    lay = cand.layout_for(code)
    return {**{f"X{i}": q for i, q in enumerate(lay.x_anc)}, **{f"Z{i}": q for i, q in enumerate(lay.z_anc)}}


def _l0_constraints(task, code, rounds: int, *, with_distance: bool, distance_seed: int | None = None) -> L0Constraints:
    lay = cand.layout_for(code)
    kw = dict(data_qubits=list(lay.data), max_qubits=lay.num_qubits, allowed_edges=cand.template_edges(code),
              allowed_gates=TEMPLATE_GATES, rounds=rounds, require_opposite_type_detectors=False,
              generator_ancillas=_own_ancillas(code))
    if with_distance:
        L = task.l0
        seed = L.get("distance_seed", 0)
        if seed == "derived":
            if distance_seed is None:
                raise ValueError("this task derives the distance seed from the schedule hash")
            seed = distance_seed
        kw.update(min_circuit_distance=L.get("min_circuit_distance"), distance_seed=int(seed),
                  distance_bposd_trials=L.get("distance_bposd_trials", 1500),
                  distance_lns_starts=L.get("distance_lns_starts", 96),
                  distance_lns_det_time=L.get("distance_lns_det_time", 1.0),
                  distance_timeout_s=L.get("distance_timeout_s", 1800.0),
                  distance_num_workers=task.num_workers, distance_noise_model=task.noise_model)
        if "distance_methods" in L:
            kw["distance_methods"] = tuple(L["distance_methods"])
        if task.kind == "distance":
            kw.update(compute_distance=True, distance_early_stop=False)
    return L0Constraints(**kw)


def circuits_for(spec, code, rounds: int) -> dict:
    """pipeline 生成电路的唯一方式：用规范化调度（auditor v2 S1）。全局时间平移的调度给出同一电路、同一哈希。"""
    return cand.build_circuits(cand.parse_schedule(spec).canonical(), code, rounds)


def _decoder(task) -> DecoderConfig:
    return DecoderConfig(task.decoder["name"], dict(task.decoder.get("params") or {}))


def _stop(task, override: Mapping | None = None) -> StopRule:
    d = dict(task.stop)
    if override:
        d.update(override)
    return StopRule(max_shots=int(d["max_shots"]), max_errors=d.get("max_errors"),
                    min_sector_errors=d.get("min_sector_errors"), batch_size=int(d.get("batch_size", 256)))


def _verified_rounds(rep) -> dict:
    out = {}
    for b, sub in rep.per_basis.items():
        cov = sub.get("stabilizer_coverage")
        out[b] = sorted(set((cov.details or {}).get("counts", {}).values()))
    return out


def _distance_info(r, canon, code, R: int, seed: int) -> dict:
    """L0 报告里每个基底的距离结果，见证翻译成调度坐标。"""
    per = {}
    for b, sub in r.per_basis.items():
        try:
            cd = sub.get("circuit_distance")
        except KeyError:
            continue
        det = cd.details or {}
        w = det.get("witness")
        if cd.status == "skipped":
            continue
        entry = {"weight": det.get("weight"), "status": cd.status, "methods": det.get("methods") and
                 ", ".join(f"{m['method']}={m['weight']}" if m["status"] == "ok" else f"{m['method']}:{m['status']}"
                           for m in det["methods"]),
                 "min_weight_count": det.get("min_weight_count"),
                 "low_weight_histogram": {str(k): v for k, v in (det.get("low_weight_histogram") or {}).items()},
                 "seconds": det.get("wall_seconds")}
        if w:
            entry.update(method=w["method"], verified=w["verified"], flipped_observables=w["flipped_observables"],
                         faults=w["faults"])
            try:
                entry["coords"] = cand.describe_faults(canon, code, R, w["faults"])
            except Exception as e:  # noqa: BLE001  诊断信息，失败不影响判定
                entry["coords"] = []
                entry["coords_error"] = str(e)
        per[b] = entry
    ws = [v["weight"] for v in per.values()]
    d = min(ws) if per and all(x is not None for x in ws) else None
    lw = sum(v.get("min_weight_count") or 0 for v in per.values() if d is not None and v["weight"] == d) \
        if d is not None else None
    return {"rounds": R, "seed": seed, "d_circ_upper_bound": d, "low_weight_witnesses": lw, "per_basis": per}


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def evaluate(task_id: str, code_spec: Mapping | None, schedule, *, seed: int | None = None,
             candidate_id: str | None = None, leaderboard_path=None, submit: bool = True) -> Report:
    """评估一个候选调度（见模块说明）。只有通过全部检查且统计量足够的结果才会写进成绩单。

    Args:
        task_id: 任务注册表里的任务。
        code_spec: 码族参数（fixed 码的任务可传 None）。
        schedule: 调度 JSON（字符串或 dict），规范见 evaluators/candidate.py。
        seed: L2 采样种子。**purpose="score" 的任务忽略它**，种子由评估器从 (task_hash, schedule_hash) 派生
            （auditor v2 S5）；自检任务用它（None = 同样派生）。
        candidate_id: 写进成绩单的候选名（可选）。
        leaderboard_path: 成绩单路径（默认 research/leaderboard.jsonl；测试必须传临时路径）。
        submit: False 时只评估、不写榜。
    批文件目录由评估器自己创建（0700，结束后删除）；v2 的公开参数 work_dir 已删除（auditor v2 S4）。
    """
    task = tasks_mod.get_task(task_id)
    return _evaluate_task(task, code_spec, schedule, seed=seed, candidate_id=candidate_id,
                          leaderboard_path=leaderboard_path, submit=submit, registered=True)


def screen(task_id: str, code_spec: Mapping | None, schedule) -> Report:
    """搜索内循环用的便宜入口：只跑调度校验 + L0（含任务的距离预算），不跑漏斗与 L2，不写成绩单。

    距离任务（kind="distance"）上它给出与 evaluate 相同的距离分数（同一派生种子、同一预算）；L2 任务上给出
    L0 判定和距离上界。状态 "screened" = 全部通过；否则与 evaluate 相同的拒绝状态。
    """
    task = tasks_mod.get_task(task_id)
    return _evaluate_task(task, code_spec, schedule, seed=None, submit=False, registered=True, mode="screen")


def _evaluate_task(task, code_spec, schedule, *, seed, candidate_id=None, leaderboard_path=None, submit=True,
                   registered=False, mode: str = "evaluate") -> Report:
    t0 = time.time()
    _assert_runtime_integrity()
    rep = Report(task_id=task.task_id, status="rejected_code", candidate_id=candidate_id, task_hash=task.hash(),
                 kind=task.kind)
    if registered and _REGISTERED_TASK_HASHES.get(task.task_id) != task.hash():
        raise RuntimeError(f"task {task.task_id} was modified at runtime (hash mismatch with the registry)")
    if seed is not None and (not isinstance(seed, (int, np.integer)) or isinstance(seed, bool) or seed < 0):
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
        maxp = (task.schedule_constraints or {}).get("max_period")
        if maxp is not None and spec.period > maxp:
            problems.append(f"period {spec.period} exceeds this task's maximum {maxp} (amortized depth of the IBM "
                            f"circuit)")
        if problems:
            raise cand.ScheduleError(problems)
    except cand.ScheduleError as e:
        rep.diagnostics.extend(e.problems)
        return _finish(rep, t0)
    canon = spec.canonical()
    rep.schedule = canon.to_dict()
    rep.schedule_hash = spec.hash()

    # ---- 种子（auditor v2 S5）
    dist_seed = tasks_mod_seed = None
    if task.l0.get("distance_seed") == "derived":
        dist_seed = derive_seed(rep.task_hash, rep.schedule_hash, "distance")
    if task.kind == "l2":
        derived = derive_seed(rep.task_hash, rep.schedule_hash, "l2")
        if task.purpose == "score":
            if seed is not None and int(seed) != derived:
                rep.diagnostics.append(f"caller seed {seed} ignored: official tasks use the evaluator-derived seed "
                                       f"{derived} (sha256 of task and schedule hashes)")
            tasks_mod_seed = derived
        else:
            tasks_mod_seed = derived if seed is None else int(seed)
        rep.seed = tasks_mod_seed
    else:
        if seed is not None:
            rep.diagnostics.append(f"caller seed {seed} ignored: distance tasks derive the distance seed "
                                   f"{dist_seed} from the task and schedule hashes")
        rep.seed = dist_seed
    l2_seed = tasks_mod_seed

    # ---- 电路（全部由评估器从规范化调度生成）
    if task.kind == "distance":
        score_rounds = []
    else:
        score_rounds = [task.rounds] if task.boundary != "diff" else [task.boundary_options["diff_rounds"],
                                                                      task.rounds]
    dist_rounds = int(task.l0.get("distance_rounds", task.rounds))
    circuits = {}
    try:
        for R in sorted(set(score_rounds) | {dist_rounds}):
            circuits[R] = cand.build_circuits(canon, code, R)
    except cand.ScheduleError as e:
        rep.diagnostics.extend(e.problems)
        return _finish(rep, t0)
    rep.circuit_hashes = {str(R): circuit_hash(c) for R, c in circuits.items()}

    # ---- 模板结构核对（每行每轮恰好被自己的辅助比特测一次）
    rep.status = "rejected_l0"
    struct = {}
    for R, cs in circuits.items():
        try:
            struct[R] = {b: sorted(set(v for t in "XZ" for v in cand.template_round_counts(cs[b], code, b)[t]))
                         for b in ("Z", "X")}
        except ValueError as e:
            rep.diagnostics.append(f"internal: generated circuit does not have the template structure: {e}")
            return _finish(rep, t0)
        if any(v != [R] for v in struct[R].values()):
            rep.diagnostics.append(f"internal: template structure has {struct[R]} measurements per row, expected {R}")
            return _finish(rep, t0)

    # ---- L0（每个打分轮数都过，距离在 distance_rounds 上）
    l0_ok = True
    for R in score_rounds:
        with_d = R == dist_rounds
        r = check_l0(circuits[R], code, "both", _l0_constraints(task, code, R, with_distance=with_d,
                                                                distance_seed=dist_seed))
        key = f"r={R}" + (" (with distance)" if with_d else "")
        rep.l0[key] = r.to_dict()
        rep.l0_text[key] = r.to_text()
        if r.passed:
            vr = _verified_rounds(r)
            if any(v != [R] for v in vr.values()) or vr != struct[R]:
                l0_ok = False
                rep.diagnostics.append(f"internal: L0 counted {vr} measurements per generator, template {struct[R]}, "
                                       f"expected {R}")
            else:
                rep.rounds_verified[str(R)] = vr
        else:
            l0_ok = False
        if with_d:
            rep.distance_upper_bound = r.d_circ
            rep.distance = _distance_info(r, canon, code, R, dist_seed if dist_seed is not None
                                          else int(task.l0.get("distance_seed", 0)))
    if dist_rounds not in score_rounds:
        r = check_l0(circuits[dist_rounds], code, "both",
                     _l0_constraints(task, code, dist_rounds, with_distance=True, distance_seed=dist_seed))
        key = f"distance r={dist_rounds}"
        rep.l0[key] = r.to_dict()
        rep.l0_text[key] = r.to_text()
        rep.distance_upper_bound = r.d_circ
        rep.distance = _distance_info(r, canon, code, dist_rounds, dist_seed if dist_seed is not None
                                      else int(task.l0.get("distance_seed", 0)))
        if r.passed:
            vr = _verified_rounds(r)
            if any(v != [dist_rounds] for v in vr.values()) or vr != struct[dist_rounds]:
                r_ok = False
                rep.diagnostics.append(f"internal: L0 counted {vr} measurements per generator, expected {dist_rounds}")
            else:
                r_ok = True
                if task.kind == "distance":
                    rep.rounds_verified[str(dist_rounds)] = vr
        else:
            r_ok = False
        l0_ok = l0_ok and r_ok
    if not l0_ok:
        rep.diagnostics.append("L0 failed (see the L0 reports below)")
        return _finish(rep, t0)

    if task.kind == "distance":
        d = rep.distance["d_circ_upper_bound"] if rep.distance else None
        if d is None:
            rep.diagnostics.append("no injection-verified logical error found: the distance cannot be bounded")
            return _finish(rep, t0)
        rep.score = {"d_circ_upper_bound": int(d), "low_weight_witnesses": int(rep.distance["low_weight_witnesses"]),
                     "period": int(canon.period), "sort_key": [-int(d), int(rep.distance["low_weight_witnesses"]),
                                                               int(canon.period)],
                     "definition": (f"circuit-level distance upper bound on the {dist_rounds}-round memory circuits "
                                    f"(min over Z/X bases; injection-verified witness), larger is better; ties: number "
                                    f"of distinct minimum-weight logical errors (DEM column sets) found by the fixed-"
                                    f"budget search in the bases attaining the minimum, fewer is better; then period "
                                    f"(amortized depth), smaller is better")}
    if mode == "screen":
        rep.status = "screened"
        rep.ineligible_reasons.append("screen(): never written to the leaderboard")
        return _finish(rep, t0)
    if task.kind == "distance":
        rep.status = "scored"
        return _submit(rep, task, leaderboard_path, submit, t0)

    # ---- 分层漏斗（E-004 之后填配置）
    tiers = list((task.funnel or {}).get("tiers") or [])
    lay = cand.layout_for(code)
    try:
        for ti, tier in enumerate(tiers):
            res = sample_l2(code, circuits[task.rounds], list(lay.data), p=task.p, rounds=task.rounds,
                            noise_model=task.noise_model, boundary="paper", decoder=_decoder(task),
                            seed=int(np.random.SeedSequence([int(l2_seed), ti, 0x7135]).generate_state(1)[0]),
                            stop=_stop(task, tier.get("stop")), num_workers=task.num_workers)
            pr = res.per_round["P_any"]
            thr = tier.get("promote_if_per_round_P_any_below")
            decision = "promote" if thr is None or (pr["low"] is not None and pr["low"] < thr) else "reject"
            rep.funnel.append({"name": tier.get("name", f"tier{ti}"), "decision": decision,
                               "per_round_P_any": pr["best"], "counts": res.counts, "threshold": thr})
            if decision != "promote":
                rep.status = "filtered"
                rep.diagnostics.append(f"filtered at funnel tier {tier.get('name', ti)}: per-round P_any lower "
                                       f"bound {pr['low']} >= {thr}")
                return _finish(rep, t0)

        # ---- L2
        rep.status = "rejected_l2"
        kwargs = dict(p=task.p, noise_model=task.noise_model, decoder=_decoder(task), seed=int(l2_seed),
                      stop=_stop(task), num_workers=task.num_workers)
        data = list(lay.data)
        if task.boundary == "diff":
            r1 = task.boundary_options["diff_rounds"]
            res = sample_l2(code, {r1: circuits[r1], task.rounds: circuits[task.rounds]}, data, rounds=task.rounds,
                            boundary="diff", diff_rounds=r1,
                            diff_inner_boundary=task.boundary_options.get("inner", "paper"), **kwargs)
        else:
            res = sample_l2(code, circuits[task.rounds], data, rounds=task.rounds, boundary=task.boundary, **kwargs)
    except L2IntegrityError as e:
        rep.status = "integrity_error"
        rep.diagnostics.append(f"L2 integrity check failed, the run is void: {e}")
        return _finish(rep, t0)
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
    return _submit(rep, task, leaderboard_path, submit, t0)


def _submit(rep: Report, task, leaderboard_path, submit: bool, t0: float) -> Report:
    env = environment_check()
    rep.environment = env
    if not env["ok"]:
        rep.ineligible_reasons.extend(env["problems"])
    from evaluators import leaderboard as lb
    to_official = lb.is_official_path(leaderboard_path)
    if to_official and task.purpose == "score" and not (env["evaluator"].get("verified")
                                                        and env["evaluator"].get("frozen")):
        rep.ineligible_reasons.append("the evaluator is not frozen (or does not match its frozen manifest); only "
                                      "the frozen evaluator may write research results to the official leaderboard")
    if to_official and task.purpose != "score":
        rep.ineligible_reasons.append(f"task purpose {task.purpose!r} is never written to the official leaderboard")
    if not submit:
        rep.ineligible_reasons.append("submit=False")
    rep.eligible = not rep.ineligible_reasons
    if rep.eligible:
        rec = _record_distance(rep, task) if task.kind == "distance" else _record(rep, task)
        rep.leaderboard_record = lb._append(rec, leaderboard_path, _CREDENTIAL)
    return _finish(rep, t0)


def _finish(rep: Report, t0: float) -> Report:
    rep.timing["wall_s"] = round(time.time() - t0, 2)
    return rep


def _l0_summary(rep: Report) -> dict:
    return {k: {"passed": v["passed"], "d_circ": v["d_circ"], "d_circ_per_basis": v["d_circ_per_basis"],
                "checks": {c["name"]: c["status"] for c in v["checks"]}} for k, v in rep.l0.items()}


def _record(rep: Report, task) -> dict:
    """成绩单条目（只由本模块从自己的计算结果组装）。"""
    l2 = rep.l2
    inp = l2["inputs"]
    return {
        "candidate_id": rep.candidate_id,
        "task_id": task.task_id,
        "task_hash": task.hash(),
        "kind": task.kind,
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
        "l0": _l0_summary(rep),
        "distance_upper_bound": rep.distance_upper_bound,
        "score": rep.score,
        "l2": l2,
    }


def _record_distance(rep: Report, task) -> dict:
    """距离任务的成绩单条目：带每个基底的最短见证（原始故障 + 调度坐标），verify 时重新注入验证。"""
    dd = rep.distance
    return {
        "candidate_id": rep.candidate_id,
        "task_id": task.task_id,
        "task_hash": task.hash(),
        "kind": task.kind,
        "purpose": task.purpose,
        "code": rep.code,
        "schedule": rep.schedule,
        "schedule_hash": rep.schedule_hash,
        "circuit_hashes": rep.circuit_hashes,
        "rounds_verified": rep.rounds_verified,
        "noise_model": task.noise_model,
        "rounds": task.rounds,
        "seed": rep.seed,
        "distance_params": dict(task.l0),
        "l0": _l0_summary(rep),
        "distance_upper_bound": rep.distance_upper_bound,
        "distance": {"d_circ_upper_bound": dd["d_circ_upper_bound"], "low_weight_witnesses": dd["low_weight_witnesses"],
                     "per_basis": {b: {"weight": v["weight"], "min_weight_count": v.get("min_weight_count"),
                                       "low_weight_histogram": v.get("low_weight_histogram"),
                                       "method": v.get("method"), "faults": v.get("faults"),
                                       "witness_in_schedule_coordinates": [c["text"] for c in v.get("coords", [])]}
                                   for b, v in dd["per_basis"].items()}},
        "score": rep.score,
    }
