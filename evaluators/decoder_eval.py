"""解码器任务的唯一评估入口（H-005，2026-10-03）。

    from evaluators.decoder_eval import evaluate_decoder, reference_report
    rep = evaluate_decoder("bb72-dec-p3e-3", program_src, split="search")    # 搜索阶段：固定的搜索集，不写榜
    print(rep.to_text())                                                    # 给 LLM 的诊断
    rep = evaluate_decoder("bb72-dec-p3e-3", program_src, split="holdout")  # 正式：留出集，满足条件时写榜

候选提交**完整程序**：定义 `make_decoder(H, L, priors, info)`，返回 `decode(syndrome) -> k 个 observable 比特`
（mp_rule 任务提交局部更新规则，由 evaluators/decoder_mp.py 包成完整程序）。评估器：
  1. 由任务生成电路与两个 sector 的解码问题（decoder_problem.py）；
  2. 由密钥派生 split 的种子，按批（batch_size shot）在父进程里采样（候选看不到种子）；
  3. 每一轮取 W = task.num_workers 个批：先跑主参考（Relay-BP，同一沙箱、同一计时），再跑候选；
     每个 sector 各自的子进程（一个 worker 一个 Z 会话、一个 X 会话），**跑一个 sector 时另一个 sector 的
     所有子进程都被 SIGSTOP 暂停**，两个 sector 的代码不会同时运行；shot 逐个发送；
  4. 速度预算（每个 sector 每个 shot）：cap_i = K × max(参考在 shot i 上的 CPU, 参考在该批上的平均 CPU, min_shot_cap_s)；
     每批总预算 K × 参考在该批上的总 CPU（按 shot 顺序累计，超出之后的 shot 全部算失败）；墙钟超过硬上限
     shot_wall_s 的 shot 被杀（会话重启，重建时间单独计；CPU 超过 cap_i 的 shot 事后判失败、不杀）；构建 CPU 超过 build_cpu_s 则整个
     sector 失败。超时 / 异常 / 输出格式错误的 shot 都按失败计；
  5. 停止规则（holdout）：候选每个 sector ≥ min_sector_errors 次失败且 P_any ≥ max_errors，或达到 max_shots；
     search 用固定 shot 数（task.decoder.search.shots，可传更小的 shots）。
分数 = P_any（同一 shot X 或 Z 任一 sector 预测错 = 失败），附 LR=1000 似然比区间与每轮换算；次级指标 = 平均 CPU / shot。
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import numpy as np

from evaluators import decoder_problem as dp
from evaluators.decoder_refs import program_for
from evaluators.decoder_sandbox import DecoderSession, os_sandbox_available
from evaluators.stats import DEFAULT_LIKELIHOOD_FACTOR, binomial_interval
from evaluators.tasks import MIN_SECTOR_ERRORS_FOR_LEADERBOARD, get_task

__all__ = ["evaluate_decoder", "reference_report", "DecoderReport", "SectorStats", "program_hash",
           "validate_output", "near_optimal_gap", "clear_reference_cache"]

FAIL_KINDS = ("wrong", "timeout", "budget", "error", "format", "dead")


def program_hash(src: str) -> str:
    return hashlib.sha256(src.encode("utf-8")).hexdigest()


def validate_output(out, k: int) -> tuple[np.ndarray | None, str | None]:
    """严格校验候选输出：长度 k 的列表，元素只能是 0 / 1（int）或 True / False。其他一律是格式错误。"""
    if not isinstance(out, list):
        return None, f"output must be a sequence of {k} bits, got {type(out).__name__}"
    if len(out) != k:
        return None, f"output has length {len(out)}, expected k={k}"
    bits = np.zeros(k, dtype=bool)
    for i, v in enumerate(out):
        if v is True or v is False:
            bits[i] = v
        elif type(v) is int and v in (0, 1):
            bits[i] = bool(v)
        else:
            return None, f"output[{i}] = {v!r} is not 0/1"
    return bits, None


# ---------------------------------------------------------------------------
# 一次运行（一个程序在一组批上）的原始记录
# ---------------------------------------------------------------------------

@dataclass
class SectorRun:
    """一个程序在一个 sector 的若干 shot 上的逐 shot 记录（shot 按全局编号排序）。"""
    correct: np.ndarray            # bool：输出正确（未考虑预算）
    status: np.ndarray             # int8：0 ok，1 wrong，2 timeout(killed)，3 error，4 format，5 dead（会话死后没跑）
    cpu: np.ndarray                # float：每 shot CPU 秒
    build_cpu: list = field(default_factory=list)
    restarts: int = 0
    build_failed: str | None = None
    messages: list = field(default_factory=list)   # 前几条错误信息（诊断）


_ST = {"ok": 0, "wrong": 1, "timeout": 2, "error": 3, "format": 4, "dead": 5}


class _Worker:
    """一个 worker：每个 sector 一个会话（懒启动），不运行的 sector 被 SIGSTOP。"""

    def __init__(self, src, inst, task, *, use_os_sandbox, mem_mb):
        self.src, self.inst, self.task = src, inst, task
        self.sessions: dict[str, DecoderSession | None] = {"Z": None, "X": None}
        self.use_os_sandbox = use_os_sandbox
        self.mem_mb = mem_mb
        self.dead: dict[str, str | None] = {"Z": None, "X": None}
        self.build_cpu: dict[str, list] = {"Z": [], "X": []}
        self.restarts = {"Z": 0, "X": 0}

    def _start(self, sector) -> DecoderSession | None:
        speed = self.task.decoder["speed"]
        P = self.inst.sectors[sector]
        s = DecoderSession(self.src, P.to_payload(), self.inst.info(sector), mem_mb=self.mem_mb,
                           build_wall_s=max(30.0, 4 * float(speed["build_cpu_s"])), use_os_sandbox=self.use_os_sandbox)
        r = s.start()
        if not r["ok"]:
            self.dead[sector] = f"make_decoder failed: {r.get('error_type')}: {r.get('error')}\n{r.get('traceback', '')}" \
                                f"\n{r.get('stderr', '')}"[:3000]
            s.cleanup()
            return None
        self.build_cpu[sector].append(r["build_cpu_s"])
        if r["build_cpu_s"] > float(speed["build_cpu_s"]):
            self.dead[sector] = (f"make_decoder used {r['build_cpu_s']:.1f} CPU s > build budget "
                                 f"{speed['build_cpu_s']} s")
            s.cleanup()
            return None
        return s

    def pause(self, sector):
        s = self.sessions.get(sector)
        if s is not None and s.alive:
            try:
                os.killpg(s.proc.pid, signal.SIGSTOP)
            except (ProcessLookupError, PermissionError):
                pass

    def resume(self, sector):
        s = self.sessions.get(sector)
        if s is not None and s.alive:
            try:
                os.killpg(s.proc.pid, signal.SIGCONT)
            except (ProcessLookupError, PermissionError):
                pass

    def run(self, sector, shot_ids, syndromes, truth, caps, batch_budget, max_restarts=3):
        """在一个批上跑一个 sector。caps=None 表示参考运行（只有墙钟上限）。返回逐 shot 数组。"""
        speed = self.task.decoder["speed"]
        n = len(shot_ids)
        status = np.full(n, _ST["dead"], dtype=np.int8)
        correct = np.zeros(n, dtype=bool)
        cpu = np.zeros(n)
        msgs = []
        k = self.inst.sectors[sector].num_obs
        used = 0.0
        for i in range(n):
            if self.dead[sector]:
                break
            s = self.sessions[sector]
            if s is None or not s.alive:
                if s is not None:
                    s.cleanup()
                    self.restarts[sector] += 1
                    if self.restarts[sector] > max_restarts:
                        self.dead[sector] = f"session died more than {max_restarts} times; remaining shots count as failures"
                        self.sessions[sector] = None
                        break
                s = self.sessions[sector] = self._start(sector)
                if s is None:
                    break
            cap = None if caps is None else float(caps[i])
            # 墙钟只设硬上限 shot_wall_s（超过才杀进程）：CPU 超过 cap 的 shot 事后判失败而不杀，否则重尾解码器
            # （BP-OSD）会因为偶尔的慢 shot 被反复杀掉、重启次数用完而整体判死。浪费的评估时间由批预算限制。
            wall = float(speed["shot_wall_s"])
            rep = s.decode(int(shot_ids[i]), np.flatnonzero(syndromes[i]).tolist(), wall)
            cpu[i] = rep.cpu_s
            used += rep.cpu_s
            if rep.killed and rep.error and rep.error.startswith("Timeout"):
                status[i] = _ST["timeout"]
            elif rep.error is not None:
                status[i] = _ST["error"]
                if len(msgs) < 5:
                    msgs.append(rep.error[:300])
            else:
                bits, err = validate_output(rep.output, k)
                if err:
                    status[i] = _ST["format"]
                    if len(msgs) < 5:
                        msgs.append("format: " + err)
                else:
                    correct[i] = not (bits != truth[i]).any()
                    status[i] = _ST["ok"] if correct[i] else _ST["wrong"]
            if batch_budget is not None and used > batch_budget:
                # 本批预算用完：之后的 shot 不再运行（记为 dead / 预算失败）
                break
        return status, correct, cpu, msgs

    def close(self):
        for sec, s in self.sessions.items():
            if s is not None:
                self.resume(sec)
                s.cleanup()
        self.sessions = {"Z": None, "X": None}


@dataclass
class SectorStats:
    shots: int
    failures: int                  # 按打分口径的失败（错 + 超时 + 超预算 + 异常 + 格式 + 未运行）
    wrong: int
    timeout: int                   # 被杀（墙钟）或 CPU 超过 per-shot 上限
    budget: int                    # 超过本批总预算之后的 shot
    error: int
    format: int
    dead: int
    cpu_mean_s: float
    cpu_median_s: float
    cpu_p99_s: float
    cpu_max_s: float
    cpu_total_s: float
    build_cpu_s: list
    restarts: int


@dataclass
class DecoderReport:
    task_id: str
    status: str                       # "scored" | "searched" | "rejected" | "insufficient_statistics" | "error"
    split: str
    program_hash: str
    candidate_id: str | None = None
    task_hash: str | None = None
    shots: int = 0
    batches: int = 0
    counts: dict = field(default_factory=dict)        # fail_Z, fail_X, fail_any, fail_both
    rates: dict = field(default_factory=dict)         # P_Z / P_X / P_any: {best, low, high}
    per_round: dict = field(default_factory=dict)
    sectors: dict = field(default_factory=dict)       # "Z"/"X" -> SectorStats（asdict）
    reference: dict = field(default_factory=dict)     # 主参考在同一批 shot 上的计数与速度
    overlap: dict = field(default_factory=dict)       # 与参考失败的重叠
    features: dict = field(default_factory=dict)      # 失败 shot 的特征统计（search）
    speed: dict = field(default_factory=dict)
    diagnostics: list = field(default_factory=list)
    eligible: bool = False
    ineligible_reasons: list = field(default_factory=list)
    leaderboard_record: dict | None = None
    seed_commitment: str | None = None
    circuit_hash: str | None = None
    os_sandbox: bool = False
    timing: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    def score(self) -> float | None:
        r = self.rates.get("P_any")
        return None if not r else r["best"]

    def to_text(self) -> str:
        L = [f"DECODER EVALUATION {self.status.upper()} [task {self.task_id}, split {self.split}, "
             f"program {self.program_hash[:12]}]"]
        for d in self.diagnostics:
            L.append(f"  - {d}")
        if self.shots:
            c = self.counts
            ref = self.reference.get("counts") or {}
            L.append(f"shots: {self.shots}; failures Z {c.get('fail_Z')} X {c.get('fail_X')} any {c.get('fail_any')} "
                     f"(both {c.get('fail_both')}); reference Relay-BP on the same shots: Z {ref.get('fail_Z')} "
                     f"X {ref.get('fail_X')} any {ref.get('fail_any')}")
            for key in ("P_any", "P_Z", "P_X"):
                r = self.rates.get(key)
                rr = (self.reference.get("rates") or {}).get(key)
                if r:
                    L.append(f"  {key} = {r['best']:.3e} [{r['low']:.3e}, {r['high']:.3e}] (LR=1000)"
                             + (f"; reference {rr['best']:.3e}" if rr else ""))
            for s in ("Z", "X"):
                st = self.sectors.get(s)
                if not st:
                    continue
                rs = (self.reference.get("sectors") or {}).get(s) or {}
                L.append(f"  sector {s}: wrong {st['wrong']}, timeout/over-cap {st['timeout']}, over-batch-budget "
                         f"{st['budget']}, exceptions {st['error']}, bad output {st['format']}, not run {st['dead']}; "
                         f"CPU/shot mean {st['cpu_mean_s'] * 1e3:.2f} ms (median {st['cpu_median_s'] * 1e3:.2f}, "
                         f"p99 {st['cpu_p99_s'] * 1e3:.1f}, max {st['cpu_max_s'] * 1e3:.1f}); reference mean "
                         f"{rs.get('cpu_mean_s', float('nan')) * 1e3:.2f} ms; build {['%.2f' % b for b in st['build_cpu_s']]} s")
            if self.overlap:
                for s, o in self.overlap.items():
                    L.append(f"  overlap with Relay-BP failures, sector {s}: both fail {o['both']}, only candidate "
                             f"{o['only_candidate']}, only reference {o['only_reference']}")
            if self.features:
                L.append("  failing-shot features (syndrome weight = number of fired detectors):")
                for s, f in self.features.items():
                    L.append(f"    {s}: all shots mean weight {f['weight_all_mean']:.1f}; candidate failures mean "
                             f"{f['weight_fail_mean']:.1f} (quartiles {f['weight_fail_q']}); reference failures mean "
                             f"{f['weight_ref_fail_mean']:.1f}; candidate-only failures by syndrome-weight bin "
                             f"{f['only_candidate_by_weight']}; fired-detector share per round in candidate failures "
                             f"{f['fail_round_profile']} (all shots {f['all_round_profile']})")
            if self.speed:
                L.append(f"  speed: {self.speed}")
        if self.ineligible_reasons:
            L.append("not ranked: " + "; ".join(self.ineligible_reasons))
        return "\n".join(L)


# ---------------------------------------------------------------------------
# 执行：一组批、一个程序
# ---------------------------------------------------------------------------

class _ProgramRunner:
    def __init__(self, src, inst, task, *, workers, use_os_sandbox, mem_mb=2048):
        self.workers = [_Worker(src, inst, task, use_os_sandbox=use_os_sandbox, mem_mb=mem_mb) for _ in range(workers)]

    def run_round(self, sector, batches, caps=None, budgets=None):
        """batches: [(shot_ids, syndromes, truth)]，每个 worker 一个批（len(batches) ≤ workers）。"""
        other = "X" if sector == "Z" else "Z"
        for w in self.workers:
            w.pause(other)
            w.resume(sector)
        out = [None] * len(batches)

        def job(j):
            ids, syn, tru = batches[j]
            out[j] = self.workers[j].run(sector, ids, syn, tru, None if caps is None else caps[j],
                                         None if budgets is None else budgets[j])

        with ThreadPoolExecutor(max_workers=len(batches)) as ex:
            list(ex.map(job, range(len(batches))))
        for w in self.workers:
            w.pause(sector)
        return out

    def close(self):
        for w in self.workers:
            w.close()

    @property
    def dead(self):
        return {s: next((w.dead[s] for w in self.workers if w.dead[s]), None) for s in ("Z", "X")}

    def build_cpu(self, s):
        return [b for w in self.workers for b in w.build_cpu[s]]

    def restarts(self, s):
        return sum(w.restarts[s] for w in self.workers)


def _caps_for(task, ref_cpu: np.ndarray):
    sp_ = task.decoder["speed"]
    K = float(sp_["K"])
    mean = float(ref_cpu.mean()) if len(ref_cpu) else 0.0
    caps = K * np.maximum(np.maximum(ref_cpu, mean), float(sp_["min_shot_cap_s"]))
    budget = K * max(float(ref_cpu.sum()), float(sp_["min_shot_cap_s"]) * len(ref_cpu))
    return caps, budget


def _apply_budget(status, correct, cpu, caps):
    """候选的最终逐 shot 判定：超过 per-shot 上限 → timeout；（批预算超出的 shot 在运行时就没跑，status=dead→budget）。"""
    fail = ~correct.copy()
    st = status.copy()
    over = (st <= 1) & (cpu > caps)
    st[over] = _ST["timeout"]
    fail |= over
    return st, fail


# ---------------------------------------------------------------------------
# 参考缓存（search split 固定 shot，同一进程内复用）
# ---------------------------------------------------------------------------

_REF_CACHE: dict = {}
_REF_LOCK = threading.Lock()


def clear_reference_cache():
    with _REF_LOCK:
        _REF_CACHE.clear()


def _sector_stats(status, cpu, build, restarts, extra_budget_fail=None) -> dict:
    n = len(status)
    budget = int(extra_budget_fail.sum()) if extra_budget_fail is not None else 0
    st = status.copy()
    if extra_budget_fail is not None:
        st[extra_budget_fail] = 6
    c = cpu[st != _ST["dead"]] if n else cpu
    c = c if len(c) else np.zeros(1)
    return dataclasses.asdict(SectorStats(
        shots=n, failures=int((st != 0).sum()), wrong=int((st == 1).sum()), timeout=int((st == 2).sum()),
        budget=budget, error=int((st == 3).sum()), format=int((st == 4).sum()), dead=int((st == 5).sum()),
        cpu_mean_s=float(c.mean()), cpu_median_s=float(np.median(c)), cpu_p99_s=float(np.quantile(c, 0.99)),
        cpu_max_s=float(c.max()), cpu_total_s=float(cpu.sum()), build_cpu_s=[float(b) for b in build],
        restarts=int(restarts)))


def _rates(fz, fx, n, rounds, lf=DEFAULT_LIKELIHOOD_FACTOR):
    from evaluators.l2 import per_round
    fa = fz | fx
    counts = {"shots": int(n), "fail_Z": int(fz.sum()), "fail_X": int(fx.sum()), "fail_any": int(fa.sum()),
              "fail_both": int((fz & fx).sum())}
    rates, pr = {}, {}
    for key, e in (("P_Z", counts["fail_Z"]), ("P_X", counts["fail_X"]), ("P_any", counts["fail_any"])):
        iv = binomial_interval(e, n, lf)
        rates[key] = {"best": iv.best, "low": iv.low, "high": iv.high}
        pr[key] = {"best": per_round(iv.best, rounds), "low": per_round(iv.low, rounds),
                   "high": per_round(iv.high, rounds)}
    return counts, rates, pr


def _features(inst, syn_all, cand_fail, ref_fail):
    """失败 shot 的特征（给 LLM）：syndrome 权重分布、按轮次的 detector 触发比例、只有候选失败的按权重分箱。"""
    out = {}
    for s in ("Z", "X"):
        S = syn_all[s]
        w = S.sum(axis=1)
        cf, rf = cand_fail[s], ref_fail[s]
        coords = inst.sectors[s].det_coords
        rounds = np.array([c[1] for c in coords])
        R = int(rounds.max()) + 1

        def prof(mask):
            if not mask.any():
                return []
            tot = S[mask].sum()
            return [round(float(S[mask][:, rounds == r].sum() / max(tot, 1)), 3) for r in range(R)]

        bins = [0, 2, 4, 6, 8, 10, 15, 20, 1 << 30]
        only = cf & ~rf
        hist = {}
        for a, b in zip(bins[:-1], bins[1:]):
            m = (w >= a) & (w < b)
            if m.any():
                lab = f"{a}-{b - 1}" if b < (1 << 30) else f">={a}"
                hist[lab] = f"{int((only & m).sum())}/{int(m.sum())}"
        out[s] = {"weight_all_mean": float(w.mean()) if len(w) else 0.0,
                  "weight_fail_mean": float(w[cf].mean()) if cf.any() else 0.0,
                  "weight_fail_q": [int(x) for x in np.quantile(w[cf], [0.25, 0.5, 0.75])] if cf.any() else [],
                  "weight_ref_fail_mean": float(w[rf].mean()) if rf.any() else 0.0,
                  "only_candidate_by_weight": hist, "fail_round_profile": prof(cf),
                  "all_round_profile": prof(np.ones(len(w), dtype=bool))}
    return out


def _seed_commitment(task, split) -> str | None:
    if split == "public":
        return None
    root = dp.split_root(task.task_id, task.hash(), split)
    return hashlib.sha256(f"qec-decoder-commit|{root}".encode()).hexdigest()


# ---------------------------------------------------------------------------
# 公开入口
# ---------------------------------------------------------------------------

def _resolve_program(task, program_src: str, full_program: bool = False) -> tuple[str, str | None]:
    """mp_rule 任务：候选交规则，评估器包成完整程序（规则先过 AST 白名单）。"""
    if task.decoder["interface"] != "mp_rule" or full_program:
        return program_src, None
    from evaluators.decoder_mp import RuleError, wrap_rules
    try:
        return wrap_rules(program_src, task), None
    except RuleError as e:
        return "", str(e)


def _reference_program(task) -> str:
    ref = task.decoder["reference"]
    src = program_for(ref["name"], ref["params"])
    if ref["name"] == "mp_relay":
        from evaluators.decoder_mp import wrap_rules
        src = wrap_rules(src, task)
    return src


class _Reference:
    """主参考在各批上的逐 shot 结果。search / public：进程内缓存（同一批 shot 反复用）；holdout：不缓存。
    每批：{"Z": (status, correct, cpu, syndromes, truth), "X": ...}。"""

    def __init__(self, task, inst, root, split, bs, workers, use_os):
        self.task, self.inst, self.root, self.split, self.bs = task, inst, root, split, bs
        self.workers, self.use_os = workers, use_os
        self.key = None
        if split != "holdout":
            self.key = (task.task_id, task.hash(), split, hashlib.sha256(str(root).encode()).hexdigest(), bs, use_os)
            with _REF_LOCK:
                self.batches = _REF_CACHE.setdefault(self.key, {})
        else:
            self.batches = {}
        self.runner = None

    def ensure(self, first, count):
        need = [b for b in range(first, first + count) if b not in self.batches]
        if not need:
            return
        if self.runner is None:
            self.runner = _ProgramRunner(_reference_program(self.task), self.inst, self.task, workers=self.workers,
                                         use_os_sandbox=self.use_os)
        for g in range(0, len(need), self.workers):
            ids_ = need[g:g + self.workers]
            group = [(bi, np.arange(bi * self.bs, (bi + 1) * self.bs), dp.sample_batch(self.inst, self.root, bi, self.bs))
                     for bi in ids_]
            res = {}
            for s in ("Z", "X"):
                res[s] = self.runner.run_round(s, [(ids, d[s][0], d[s][1]) for _, ids, d in group])
            if any(self.runner.dead.values()):
                raise RuntimeError(f"reference decoder failed: {self.runner.dead}")
            for j, (bi, _, d) in enumerate(group):
                self.batches[bi] = {s: (res[s][j][0], res[s][j][1], res[s][j][2], d[s][0], d[s][1]) for s in ("Z", "X")}

    def close(self):
        if self.runner is not None:
            self.runner.close()
            self.runner = None


def _evaluate(task, program_src, src, *, split, shots, candidate_id, leaderboard_path, submit, num_workers,
              use_os_sandbox, with_features, t0) -> DecoderReport:
    phash = program_hash(program_src)
    rep = DecoderReport(task_id=task.task_id, status="error", split=split, program_hash=phash,
                        candidate_id=candidate_id, task_hash=task.hash())
    workers = min(int(num_workers or task.num_workers), task.num_workers, 3)
    use_os = os_sandbox_available() if use_os_sandbox is None else bool(use_os_sandbox)
    rep.os_sandbox = use_os
    if not use_os:
        rep.diagnostics.append("OS-level sandbox (sandbox-exec) not used: only the Python audit hook isolates the "
                               "candidate")
    inst = dp.build_instance(task)
    rep.circuit_hash = inst.circuit_hash
    root = dp.split_root(task.task_id, task.hash(), split)
    rep.seed_commitment = _seed_commitment(task, split)
    stop = task.stop
    if split == "holdout":
        bs = int(stop["batch_size"])
        max_batches = -(-int(stop["max_shots"]) // bs)
    else:
        bs = int(task.decoder["search"]["batch_size"])
        full = int(task.decoder["search"]["shots"])
        n = int(shots) if shots is not None else full
        if split == "search" and n > full:
            raise ValueError(f"the search split has {full} shots")
        max_batches = max(1, -(-n // bs))
    feats = (split != "holdout") if with_features is None else with_features

    ref = _Reference(task, inst, root, split, bs, workers, use_os)
    cand = _ProgramRunner(src, inst, task, workers=workers, use_os_sandbox=use_os)
    per = {s: {"st": [], "co": [], "cpu": [], "fail": [], "bfail": []} for s in ("Z", "X")}
    msgs = []
    b = 0
    try:
        while b < max_batches:
            cnt = min(workers, max_batches - b)
            ref.ensure(b, cnt)
            rb = [ref.batches[bi] for bi in range(b, b + cnt)]
            for s in ("Z", "X"):
                caps, budgets = [], []
                for r in rb:
                    c, bud = _caps_for(task, r[s][2])
                    caps.append(c)
                    budgets.append(bud)
                ids = [np.arange(bi * bs, (bi + 1) * bs) for bi in range(b, b + cnt)]
                res = cand.run_round(s, [(ids[j], rb[j][s][3], rb[j][s][4]) for j in range(cnt)], caps, budgets)
                for j, (st, co, cp, ms) in enumerate(res):
                    st2, f = _apply_budget(st, co, cp, caps[j])
                    per[s]["st"].append(st2)
                    per[s]["co"].append(co)
                    per[s]["cpu"].append(cp)
                    per[s]["fail"].append(f)
                    per[s]["bfail"].append((st == _ST["dead"]) & (cand.dead[s] is None))
                    msgs.extend(ms)
            b += cnt
            if any(cand.dead.values()):
                break
            if split == "holdout":
                fz, fx = np.concatenate(per["Z"]["fail"]), np.concatenate(per["X"]["fail"])
                if (min(fz.sum(), fx.sum()) >= int(stop.get("min_sector_errors") or 0)
                        and (fz | fx).sum() >= int(stop.get("max_errors") or 0)):
                    break
        dead = dict(cand.dead)
        build = {s: cand.build_cpu(s) for s in ("Z", "X")}
        restarts = {s: cand.restarts(s) for s in ("Z", "X")}
    finally:
        cand.close()
        ref.close()

    n = b * bs
    rep.shots, rep.batches = n, b
    cat = {s: {k: np.concatenate(v) for k, v in per[s].items()} for s in ("Z", "X")}
    fz, fx = cat["Z"]["fail"], cat["X"]["fail"]
    rep.counts, rep.rates, rep.per_round = _rates(fz, fx, n, task.rounds)
    for s in ("Z", "X"):
        rep.sectors[s] = _sector_stats(cat[s]["st"], cat[s]["cpu"], build[s], restarts[s], cat[s]["bfail"])
    for s in ("Z", "X"):
        if dead[s]:
            rep.diagnostics.append(f"sector {s}: {dead[s]}")
    for m in msgs[:5]:
        rep.diagnostics.append(f"example problem: {m}")
    rref = {s: [ref.batches[bi][s] for bi in range(b)] for s in ("Z", "X")}
    rfail = {s: np.concatenate([~r[1] | (r[0] >= 2) for r in rref[s]]) for s in ("Z", "X")}
    rcpu = {s: np.concatenate([r[2] for r in rref[s]]) for s in ("Z", "X")}
    rc, rr, rpr = _rates(rfail["Z"], rfail["X"], n, task.rounds)
    rep.reference = {"name": task.decoder["reference"]["name"], "params": task.decoder["reference"]["params"],
                     "counts": rc, "rates": rr, "per_round": rpr,
                     "sectors": {s: {"cpu_mean_s": float(rcpu[s].mean()), "cpu_total_s": float(rcpu[s].sum()),
                                     "cpu_median_s": float(np.median(rcpu[s])),
                                     "cpu_p99_s": float(np.quantile(rcpu[s], 0.99)),
                                     "cpu_max_s": float(rcpu[s].max())} for s in ("Z", "X")}}
    cf = {"Z": fz, "X": fx}
    rep.overlap = {s: {"both": int((cf[s] & rfail[s]).sum()), "only_candidate": int((cf[s] & ~rfail[s]).sum()),
                       "only_reference": int((~cf[s] & rfail[s]).sum())} for s in ("Z", "X")}
    tot_c = sum(rep.sectors[s]["cpu_total_s"] for s in ("Z", "X"))
    tot_r = sum(float(rcpu[s].sum()) for s in ("Z", "X"))
    rep.speed = {"cpu_per_shot_ms": round(1e3 * tot_c / max(n, 1), 4),
                 "reference_cpu_per_shot_ms": round(1e3 * tot_r / max(n, 1), 4),
                 "ratio_to_reference": round(tot_c / tot_r, 4) if tot_r > 0 else None,
                 "K": task.decoder["speed"]["K"]}
    if feats:
        syn_all = {s: np.concatenate([r[3] for r in rref[s]]) for s in ("Z", "X")}
        rep.features = _features(inst, syn_all, cf, rfail)
    if any(dead.values()):
        rep.status = "rejected"
        rep.ineligible_reasons.append("decoder could not be built or kept crashing: "
                                      + "; ".join(f"{s}: {v.splitlines()[0]}" for s, v in dead.items() if v))
        return rep
    if split == "holdout":
        rep.status = "scored"
        _eligibility(rep, task)
        if rep.eligible and submit:
            _submit(rep, task, program_src, leaderboard_path)
    else:
        rep.status = "searched"
        rep.ineligible_reasons.append(f"split {split!r} is never ranked (only the held-out split is)")
    return rep


def evaluate_decoder(task_id: str, program_src: str, *, split: str = "search", shots: int | None = None,
                     candidate_id: str | None = None, leaderboard_path=None, submit: bool = True,
                     num_workers: int | None = None, use_os_sandbox: bool | None = None,
                     with_features: bool | None = None, full_program: bool = False) -> DecoderReport:
    """评估一个解码程序。split="search"：固定的搜索集（task.decoder.search.shots，或更小的 shots 前缀），不写榜；
    split="holdout"：留出集，按停止规则采样，满足上榜条件且 submit=True 时写成绩单；split="public"：只给自检任务
    （公开种子，测试 / 演示）。mp_rule 任务的 program_src 是规则源码（full_program=True 时按完整程序处理，只用于
    在 mp 任务上运行官方 Relay-BP 这类次要参考，这样的结果不能上榜）。"""
    t0 = time.perf_counter()
    task = get_task(task_id)
    from evaluators.pipeline import _REGISTERED_TASK_HASHES, _assert_runtime_integrity
    _assert_runtime_integrity()
    if task.kind != "decoder":
        raise ValueError(f"task {task_id} is not a decoder task")
    if _REGISTERED_TASK_HASHES.get(task_id) != task.hash():
        raise RuntimeError("task definition changed at runtime")
    if split not in dp.SPLITS:
        raise ValueError(f"split must be one of {dp.SPLITS}")
    if split == "public" and task.purpose != "selftest":
        raise ValueError("the public split exists only for self-test tasks")
    if not isinstance(program_src, str):
        raise TypeError("program_src must be a string")
    src, err = _resolve_program(task, program_src, full_program)
    if err:
        rep = DecoderReport(task_id=task_id, status="rejected", split=split, program_hash=program_hash(program_src),
                            candidate_id=candidate_id, task_hash=task.hash())
        rep.diagnostics.append(f"rules rejected: {err}")
        rep.ineligible_reasons.append("rules rejected")
        return _finish(rep, t0)
    if full_program and task.decoder["interface"] == "mp_rule":
        submit = False
    rep = _evaluate(task, program_src, src, split=split, shots=shots, candidate_id=candidate_id,
                    leaderboard_path=leaderboard_path, submit=submit, num_workers=num_workers,
                    use_os_sandbox=use_os_sandbox, with_features=with_features, t0=t0)
    if full_program and task.decoder["interface"] == "mp_rule":
        rep.eligible = False
        rep.ineligible_reasons.append("full program on an mp_rule task (reference comparison only)")
    return _finish(rep, t0)


def _eligibility(rep: DecoderReport, task) -> None:
    R = []
    if task.purpose != "score":
        R.append("self-test task")
    if min(rep.counts.get("fail_Z", 0), rep.counts.get("fail_X", 0)) < MIN_SECTOR_ERRORS_FOR_LEADERBOARD:
        R.append(f"fewer than {MIN_SECTOR_ERRORS_FOR_LEADERBOARD} failures in a sector "
                 f"(Z {rep.counts.get('fail_Z')}, X {rep.counts.get('fail_X')})")
        rep.status = "insufficient_statistics"
    if not rep.os_sandbox:
        R.append("candidate did not run under the OS-level sandbox")
    rep.ineligible_reasons += R
    rep.eligible = not R


def _finish(rep, t0):
    rep.timing["total_s"] = round(time.perf_counter() - t0, 2)
    return rep


# ---------------------------------------------------------------------------
# 成绩单
# ---------------------------------------------------------------------------

def decoder_record(rep: DecoderReport, task, program_src: str) -> dict:
    return {"kind": "decoder", "candidate_id": rep.candidate_id, "task_id": task.task_id, "task_hash": task.hash(),
            "purpose": task.purpose, "noise_model": task.noise_model, "p": task.p, "rounds": task.rounds,
            "boundary": task.boundary, "split": rep.split, "program": program_src, "program_hash": rep.program_hash,
            "schedule_hash": rep.program_hash, "circuit_hash": rep.circuit_hash,
            "seed_commitment": rep.seed_commitment, "batch_size": int(task.stop["batch_size"]),
            "counts": rep.counts, "rates": rep.rates, "per_round": rep.per_round, "sectors": rep.sectors,
            "reference": rep.reference, "speed": rep.speed, "os_sandbox": rep.os_sandbox,
            "score": {"P_any": rep.rates["P_any"], "per_round_P_any": rep.per_round["P_any"],
                      "cpu_per_shot_ms": rep.speed["cpu_per_shot_ms"]}}


def _submit(rep, task, program_src, path):
    from evaluators import leaderboard as lb
    from evaluators.pipeline import _CREDENTIAL, environment_check
    env = environment_check()
    official = lb.is_official_path(path)
    if official and not (env["ok"] and env["evaluator"].get("frozen")):
        rep.ineligible_reasons.append("the official leaderboard needs a frozen, verified evaluator and pinned "
                                      "library versions: " + "; ".join(env["problems"][:3]))
        rep.eligible = False
        return
    rec = decoder_record(rep, task, program_src)
    rep.leaderboard_record = lb._append(rec, path, _CREDENTIAL)


# ---------------------------------------------------------------------------
# 参考报告（次要参考 + 近最优差距），不写榜
# ---------------------------------------------------------------------------

def reference_report(task_id: str, *, split: str = "search", shots: int | None = None, names=None,
                     num_workers: int | None = None, use_os_sandbox: bool | None = None) -> dict:
    """主参考与次要参考在同一组 shot 上的分数与速度（每个都按候选同样的方式运行、受同样的速度预算）。"""
    task = get_task(task_id)
    out = {}
    refs = [task.decoder["reference"]] + list(task.decoder.get("secondary_references") or [])
    for r in refs:
        if names is not None and r["name"] not in names:
            continue
        src = program_for(r["name"], r["params"])
        rep = evaluate_decoder(task_id, src, split=split, shots=shots, num_workers=num_workers,
                               use_os_sandbox=use_os_sandbox, submit=False,
                               full_program=(r["name"] != "mp_relay"))
        out[r["name"]] = {"counts": rep.counts, "rates": rep.rates, "per_round": rep.per_round,
                          "speed": rep.speed, "sectors": rep.sectors, "status": rep.status,
                          "overlap": rep.overlap, "diagnostics": rep.diagnostics,
                          "reference_counts": rep.reference.get("counts")}
    return out


def near_optimal_gap(task_id: str, *, split: str = "public", shots: int = 200, first_batch: int = 0,
                     references=None, decoder=None) -> dict:
    """小样本上：近最优（默认 CP-SAT MLE）与参考解码器在同一组 shot 上的失败对比。不打分、不写榜。
    参考程序直接在父进程里运行（不经沙箱、不计时，它们是评估器自己的代码）。split 默认 public（公开种子）。"""
    from evaluators.decoder_mle import get_near_optimal
    task = get_task(task_id)
    inst = dp.build_instance(task)
    mle = decoder or get_near_optimal(task.decoder.get("near_optimal") or {})
    root = dp.split_root(task.task_id, task.hash(), split)
    d = dp.sample_batch(inst, root, first_batch, shots)
    refs = [task.decoder["reference"]] + list(task.decoder.get("secondary_references") or [])
    if references is not None:
        refs = [r for r in refs if r["name"] in references]
    res = {}
    for s in ("Z", "X"):
        syn, tru = d[s]
        P = inst.sectors[s]
        mfail, opt, walls = np.zeros(shots, bool), 0, []
        for i in range(shots):
            r = mle.decode(P, syn[i].astype(np.uint8))
            walls.append(r.wall_s)
            opt += bool(r.optimal)
            mfail[i] = r.observables is None or bool((r.observables.astype(bool) != tru[i]).any())
        sec = {"shots": shots, "near_optimal_fail": int(mfail.sum()), "proved_optimal": opt,
               "near_optimal_wall_mean_s": float(np.mean(walls)), "references": {}}
        for r in refs:
            src = _reference_program(task) if r is task.decoder["reference"] else program_for(r["name"], r["params"])
            ns = {"__name__": "reference"}
            exec(compile(src, f"<{r['name']}>", "exec"), ns)
            dec = ns["make_decoder"](P.H, P.L, P.priors, inst.info(s))
            f = np.array([bool((np.asarray(dec(syn[i].astype(np.uint8))).astype(bool) != tru[i]).any())
                          for i in range(shots)])
            sec["references"][r["name"]] = {"fail": int(f.sum()), "fail_where_near_optimal_ok": int((f & ~mfail).sum())}
        res[s] = sec
    return {"task_id": task_id, "split": split, "first_batch": first_batch, "method": mle.name, "sectors": res}


def _main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="decoder evaluator utilities")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-secret", help="create the decoder secret file outside the repo (PI, once)")
    a = ap.parse_args(argv)
    if a.cmd == "init-secret":
        p = dp.ensure_secret()
        print(f"decoder secret at {p} (mode 0600); keep it outside the repo and never share it with search runs")


if __name__ == "__main__":
    _main()
