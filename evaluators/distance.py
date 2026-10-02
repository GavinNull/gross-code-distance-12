"""电路级距离（circuit-level / fault distance）：上界搜索 + 下界（精确）求解。

d_circ = 最少多少个故障（DEM 错误机制）组合起来不触发任何 detector、却翻转至少一个 observable。

入口：
    upper_bound(noisy_circuit, *, seed, ...) -> DistanceResult
        多路启发式搜索，取**经注入验证**的最短见证。每条路径给出的都只是上界。
        方法（按开销从小到大运行）：
          graphlike    stim shortest_graphlike_error（只看 ≤2 个 detector 的机制）
          stim_search  stim search_for_undetectable_logical_errors（截断搜索；可放进子进程限时）
          bposd        随机 η 的 BP-OSD 见证搜索（arXiv 2308.07915 Eq.(12)）：
                       min |ξ| s.t. Dξ = 0, ηᵀξ = 1，η = a·L + b·D（a ≠ 0 随机、b 随机）
          bposd_lns    对 BP-OSD 得到的低权重解做大邻域搜索（LNS）：取解的支撑及与其共享 detector
                       的所有机制（1 跳邻域），用 CP-SAT 在该子集上精确求“权重 ≤ w−1 的逻辑错误”
        见证在计入之前一律**注入验证**：去掉电路里的全部噪声，在每个故障的原位置插入概率 1 的
        Pauli 通道（测量翻转则把该次测量改成 M(1)），用 detector 采样器检查“0 个 detector 触发、
        至少一个 observable 翻转”。验证不过的见证照样报告（status="rejected"），但不计入上界。

    lower_bound(noisy_circuit, *, method, time_limit_s, seed, target=None) -> LowerBoundResult
        精确方法（同一个问题的整数规划/可满足性形式）。到时限时只给出已证明的下界。
          cpsat   OR-tools CP-SAT，原生 XOR 约束（默认）
          maxsat  stim shortest_error_sat_problem(WDIMACS) + pysat RC2（不可中断，放在子进程里限时）
          milp    HiGHS（scipy.optimize.milp），奇偶用整数松弛变量表示
        target=w 时只判定“是否存在权重 ≤ w−1 的逻辑错误”：不可行即证明 d_circ ≥ w。

所有随机性由显式 seed 给出（numpy Generator；CP-SAT 单线程 + random_seed + 确定性时间上限），
同一输入、同一参数两次运行结果相同（除非触发墙钟上限 max_seconds）。

权重口径：DEM 里症状（detector 集合, observable 集合）完全相同的机制合并成一列，一列 = 至少一个故障，
所以“最少列数”= “最少故障数”。DEM 用 decompose_errors=False 生成，超边不分解。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field

import numpy as np
import scipy.sparse as sp
import stim

__all__ = ["Fault", "Witness", "MethodResult", "DistanceResult", "LowerBoundResult", "DemColumns",
           "upper_bound", "lower_bound", "verify_faults", "dem_columns", "DEFAULT_METHODS",
           "run_in_subprocess"]

DEFAULT_METHODS = ("graphlike", "stim_search", "bposd")


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class Fault:
    """一个故障：电路里某条噪声指令的一个具体分量。"""
    tick: int                       # 前面有多少个 TICK（= 层）
    instruction_offset: int         # 在 flattened 电路里的指令序号
    gate: str                       # 噪声指令名，例如 DEPOLARIZE2、X_ERROR、M（带翻转概率的测量）
    qubits: list[int]               # 该分量作用的指令目标（比特）
    paulis: list[str]               # 翻转的 Pauli，例如 ["X8", "Y9"]；测量翻转时为空
    measurement_record: int | None = None   # 测量结果翻转：被翻转的全局测量记录编号

    def describe(self) -> str:
        what = "*".join(self.paulis) if self.paulis else f"flip of measurement record {self.measurement_record}"
        return f"tick {self.tick}: {self.gate} on {self.qubits} -> {what}"


@dataclass
class Witness:
    weight: int
    faults: list[Fault]
    method: str
    verified: bool = False
    verification: str = ""
    flipped_observables: list[int] = field(default_factory=list)

    def describe(self, limit: int = 40) -> list[str]:
        out = [f.describe() for f in self.faults[:limit]]
        if len(self.faults) > limit:
            out.append(f"... ({len(self.faults) - limit} more)")
        return out


@dataclass
class MethodResult:
    method: str
    status: str            # ok | rejected（见证没通过注入验证）| none（没找到）| error | timeout | skipped
    weight: int | None     # 本方法找到并验证通过的最短见证权重
    seconds: float
    message: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class DistanceResult:
    weight: int | None              # 所有方法中验证通过的最短见证权重（d_circ 的上界）；None = 一个都没有
    witness: Witness | None
    methods: list[MethodResult]
    seconds: float
    seed: int
    params: dict
    stopped_early: bool = False     # 因 stop_below 或 max_seconds 提前停止

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "DistanceResult":
        w = d.get("witness")
        if w is not None:
            w = Witness(**{**w, "faults": [Fault(**f) for f in w["faults"]]})
        return DistanceResult(weight=d["weight"], witness=w, methods=[MethodResult(**m) for m in d["methods"]],
                              seconds=d["seconds"], seed=d["seed"], params=d["params"],
                              stopped_early=d.get("stopped_early", False))

    def summary(self) -> str:
        parts = []
        for m in self.methods:
            if m.status == "ok":
                parts.append(f"{m.method}={m.weight}")
            else:
                parts.append(f"{m.method}:{m.status}")
        return ", ".join(parts)


@dataclass
class LowerBoundResult:
    method: str
    status: str                 # optimal | bound | infeasible_below_target | feasible_below_target | timeout | error
    lower_bound: int | None     # 已证明：d_circ >= lower_bound
    upper_bound: int | None     # 求解器顺带找到的最优可行解（未做注入验证，只作参考）
    seconds: float
    num_columns: int = 0
    num_detectors: int = 0
    message: str = ""

    @property
    def exact(self) -> bool:
        return self.lower_bound is not None and self.lower_bound == self.upper_bound


# ---------------------------------------------------------------------------
# DEM -> 稀疏矩阵
# ---------------------------------------------------------------------------

@dataclass
class DemColumns:
    D: sp.csc_matrix                 # detectors x columns, uint8
    L: sp.csc_matrix                 # observables x columns, uint8
    reps: list[stim.DemInstruction]  # 每列的一个代表性 error 指令
    num_detectors: int
    num_observables: int

    @property
    def num_columns(self) -> int:
        return len(self.reps)


def dem_columns(dem: stim.DetectorErrorModel) -> DemColumns:
    """把 DEM 的 error 指令转成 (D, L) 稀疏矩阵；症状相同的机制合并为一列；无症状机制丢弃。"""
    seen: dict[tuple, int] = {}
    reps: list[stim.DemInstruction] = []
    rows_d, cols_d, rows_l, cols_l = [], [], [], []
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        dets: set[int] = set()
        obs: set[int] = set()
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                dets ^= {t.val}
            elif t.is_logical_observable_id():
                obs ^= {t.val}
        if not dets and not obs:
            continue
        key = (tuple(sorted(dets)), tuple(sorted(obs)))
        if key in seen:
            continue
        j = len(reps)
        seen[key] = j
        reps.append(inst)
        rows_d += key[0]
        cols_d += [j] * len(key[0])
        rows_l += key[1]
        cols_l += [j] * len(key[1])
    ne = len(reps)
    D = sp.csc_matrix((np.ones(len(rows_d), dtype=np.uint8), (rows_d, cols_d)), shape=(dem.num_detectors, ne))
    L = sp.csc_matrix((np.ones(len(rows_l), dtype=np.uint8), (rows_l, cols_l)), shape=(dem.num_observables, ne))
    return DemColumns(D, L, reps, dem.num_detectors, dem.num_observables)


def _dem(flat: stim.Circuit) -> stim.DetectorErrorModel:
    return flat.detector_error_model(decompose_errors=False, allow_gauge_detectors=False)


# ---------------------------------------------------------------------------
# 故障定位与注入验证
# ---------------------------------------------------------------------------

def _fault_from_location(loc: stim.CircuitErrorLocation) -> Fault:
    if len(loc.stack_frames) != 1:
        raise ValueError("expected a flattened circuit (one stack frame per error location)")
    rng = loc.instruction_targets
    qubits = [t.gate_target.value for t in rng.targets_in_range]
    paulis = []
    for p in loc.flipped_pauli_product:
        t = p.gate_target
        letter = "X" if t.is_x_target else "Y" if t.is_y_target else "Z"
        paulis.append(f"{letter}{t.value}")
    rec = loc.flipped_measurement.record_index if loc.flipped_measurement is not None else None
    return Fault(tick=int(loc.tick_offset), instruction_offset=int(loc.stack_frames[0].instruction_offset),
                 gate=rng.gate, qubits=qubits, paulis=paulis, measurement_record=rec)


def _faults_from_explained(errs) -> list[Fault]:
    out = []
    for e in errs:
        if not e.circuit_error_locations:
            raise ValueError(f"DEM error {e.dem_error_terms} has no circuit location")
        out.append(_fault_from_location(e.circuit_error_locations[0]))
    return out


def _faults_from_columns(flat: stim.Circuit, cols: DemColumns, idx) -> list[Fault]:
    sub = stim.DetectorErrorModel()
    for j in idx:
        sub.append(cols.reps[int(j)])
    expl = flat.explain_detector_error_model_errors(dem_filter=sub, reduce_to_one_representative_error=True)
    faults = _faults_from_explained(expl)
    if len(faults) != len(idx):
        raise ValueError(f"explained {len(faults)} faults for {len(idx)} DEM columns")
    return faults


def _is_pure_noise(name: str) -> bool:
    g = stim.gate_data(name)
    return g.is_noisy_gate and not g.produces_measurements and not g.is_reset


def verify_faults(flat: stim.Circuit, faults: list[Fault], *, seed: int = 0, shots: int = 4) -> tuple[bool, str, list[int]]:
    """注入验证：flat 为带噪声的 flattened 电路。去掉所有噪声，在故障原位置以概率 1 注入，采样检查。

    返回 (是否为不可检测的逻辑错误, 说明, 翻转的 observable 列表)。
    """
    by_off: dict[int, list[Fault]] = defaultdict(list)
    for f in faults:
        by_off[f.instruction_offset].append(f)
    flip_recs = {f.measurement_record for f in faults if f.measurement_record is not None}
    for f in faults:
        if not 0 <= f.instruction_offset < len(flat) or isinstance(flat[f.instruction_offset], stim.CircuitRepeatBlock) \
                or flat[f.instruction_offset].name != f.gate:
            return False, (f"fault location does not match the circuit: instruction {f.instruction_offset} is not "
                           f"{f.gate}"), []
        if f.measurement_record is not None and not stim.gate_data(f.gate).produces_measurements:
            return False, f"fault flips measurement record {f.measurement_record} but {f.gate} measures nothing", []
    out = stim.Circuit()
    meas = 0
    for i, inst in enumerate(flat):
        if isinstance(inst, stim.CircuitRepeatBlock):
            return False, "circuit is not flattened", []
        name = inst.name
        g = stim.gate_data(name)
        if _is_pure_noise(name):
            for f in by_off.get(i, []):
                for p in f.paulis:
                    out.append(f"{p[0]}_ERROR", [int(p[1:])], 1.0)
            continue
        if g.produces_measurements:
            if name.startswith("HERALDED"):
                return False, f"{name} cannot be injected deterministically", []
            groups = inst.target_groups()
            per_group = [1] * len(groups)  # M/MX/MPP/MR...: one record per target group
            for grp, nrec in zip(groups, per_group):
                if meas in flip_recs:
                    out.append(name, grp, 1.0)
                else:
                    out.append(name, grp)
                meas += nrec
            for f in by_off.get(i, []):
                for p in f.paulis:  # 例如 MR(p) 不会有 Pauli 分量；保险起见放在测量之后
                    out.append(f"{p[0]}_ERROR", [int(p[1:])], 1.0)
            continue
        if g.is_noisy_gate and inst.gate_args_copy():  # 例如 R(p)（stim 不支持，留作保险）
            out.append(name, inst.targets_copy())
        else:
            out.append(inst)
    if meas != flat.num_measurements:
        return False, f"measurement count mismatch while rebuilding ({meas} vs {flat.num_measurements})", []
    try:
        det, obs = out.compile_detector_sampler(seed=seed).sample(shots, separate_observables=True)
    except Exception as e:  # noqa: BLE001
        return False, f"injection sampling failed: {e}", []
    if not (det == det[0]).all() or not (obs == obs[0]).all():
        return False, "injected circuit is not deterministic", []
    fired = np.nonzero(det[0])[0].tolist()
    flipped = np.nonzero(obs[0])[0].tolist()
    if fired:
        return False, f"injection fires detectors {fired[:10]}", flipped
    if not flipped:
        return False, "injection flips no observable (trivial error)", flipped
    return True, f"injected with probability 1: 0 detectors fire, observables {flipped} flip", flipped


def _make_witness(flat, faults, method, seed) -> Witness:
    faults = sorted(faults, key=lambda f: (f.tick, f.instruction_offset, f.qubits, f.paulis))
    ok, msg, flipped = verify_faults(flat, faults, seed=seed)
    return Witness(weight=len(faults), faults=faults, method=method, verified=ok, verification=msg,
                   flipped_observables=flipped)


# ---------------------------------------------------------------------------
# 子进程（stim 的 C++ 搜索、RC2 都无法在本进程内中断）
# ---------------------------------------------------------------------------

_SNIPPET = (
    "import sys, json; sys.path.insert(0, sys.argv[1]); "
    "import importlib; d = json.loads(sys.stdin.read()); "
    "m = importlib.import_module(d['module']); "
    "print(json.dumps(getattr(m, d['func'])(**d['kwargs'])))"
)


def run_in_subprocess(module: str, func: str, kwargs: dict, timeout_s: float):
    """在子进程中调用 module.func(**kwargs)（参数和返回值都必须可 JSON 序列化），超时抛 TimeoutExpired。"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.run([sys.executable, "-c", _SNIPPET, root],
                          input=json.dumps({"module": module, "func": func, "kwargs": kwargs}),
                          capture_output=True, text=True, timeout=timeout_s)
    if proc.returncode != 0:
        err = proc.stderr.strip().splitlines()
        raise RuntimeError(err[-1] if err else f"worker exited with {proc.returncode}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _stim_search_worker(circuit: str, size: int, degree: int, increasing: bool) -> dict:
    flat = stim.Circuit(circuit)
    errs = flat.search_for_undetectable_logical_errors(
        dont_explore_detection_event_sets_with_size_above=size,
        dont_explore_edges_with_degree_above=degree,
        dont_explore_edges_increasing_symptom_degree=increasing,
        canonicalize_circuit_errors=True)
    return {"faults": [asdict(f) for f in _faults_from_explained(errs)]}


# ---------------------------------------------------------------------------
# BP-OSD 随机 η + LNS（可多进程；结果只取决于 seed，与 num_workers 无关）
# ---------------------------------------------------------------------------

_BPOSD_CHUNK = 25   # 每块试验数；块的随机数流由 SeedSequence(seed).spawn 给出


def _xor_model(D: sp.spmatrix, L: sp.spmatrix, idx: np.ndarray, max_weight: int | None):
    """CP-SAT 模型：只用列子集 idx；Dξ=0，Lξ≠0，最小化 |ξ|。返回 (model, vars)。"""
    from ortools.sat.python import cp_model
    M = cp_model.CpModel()
    one = M.NewConstant(1)
    x = [M.NewBoolVar(f"x{j}") for j in idx]
    Ds = sp.csc_matrix(D)[:, idx].tocsr()
    for i in np.nonzero(np.diff(Ds.indptr))[0]:
        M.AddBoolXOr([x[k] for k in Ds.indices[Ds.indptr[i]:Ds.indptr[i + 1]]] + [one])
    Ls = sp.csc_matrix(L)[:, idx].tocsr()
    ys = []
    for i in np.nonzero(np.diff(Ls.indptr))[0]:
        y = M.NewBoolVar(f"y{i}")
        ys.append(y)
        M.AddBoolXOr([x[k] for k in Ls.indices[Ls.indptr[i]:Ls.indptr[i + 1]]] + [y, one])
    M.AddBoolOr(ys)  # ys 为空时模型不可行（子集里没有翻转 observable 的机制）
    if max_weight is not None:
        M.Add(sum(x) <= max_weight)
    M.Minimize(sum(x))
    return M, x


def _cpsat_solver(seed: int, det_time: float | None, wall: float | None, workers: int = 1):
    from ortools.sat.python import cp_model
    s = cp_model.CpSolver()
    s.parameters.num_workers = workers
    s.parameters.random_seed = int(seed) % (2 ** 31)
    if det_time is not None:
        s.parameters.max_deterministic_time = float(det_time)
    if wall is not None:
        s.parameters.max_time_in_seconds = float(wall)
    return s


def _is_logical(D, L, idx) -> bool:
    xi = np.zeros(D.shape[1], dtype=np.uint8)
    xi[np.asarray(idx, dtype=np.int64)] = 1
    return not (D @ xi % 2).any() and bool((L @ xi % 2).any())


def _neighbourhood(D: sp.csc_matrix, xi_idx, hops: int) -> np.ndarray:
    Dr = D.tocsr()
    cur = set(int(j) for j in xi_idx)
    for _ in range(hops):
        dets = np.unique(D[:, sorted(cur)].indices)
        cur |= set(Dr[dets].indices.tolist())
    return np.array(sorted(cur), dtype=np.int64)


def _lns_chain(D, L, start, hops: int, det_time: float, seed: int, max_chain: int, patience: int = 1):
    """从 start 出发反复做邻域精修：在当前解的 hops 跳邻域内，以当前解为可行提示，用 CP-SAT
    （单线程、确定性时间上限）最小化权重；有严格改进就以新解为中心继续。一共最多 max_chain 次求解，
    连续 patience 次没有改进（每次换随机种子）就停止。"""
    from ortools.sat.python import cp_model
    D = sp.csc_matrix(D)
    cur = np.asarray(start, dtype=np.int64)
    log = []
    fails = 0
    for step in range(max_chain):
        idx = _neighbourhood(D, cur, hops)
        M, x = _xor_model(D, L, idx, len(cur))
        support = set(cur.tolist())
        for k, j in enumerate(idx):
            M.AddHint(x[k], 1 if int(j) in support else 0)
        s = _cpsat_solver(seed * 7919 + step, det_time, wall=20 * det_time + 10)
        st = s.Solve(M)
        new = None
        if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            new = np.array([int(j) for k, j in enumerate(idx) if s.Value(x[k])], dtype=np.int64)
        if new is not None and len(new) < len(cur) and _is_logical(D, L, new):
            log.append([len(cur), len(new), len(idx), s.StatusName(st)])
            cur = new
            fails = 0
            continue
        if st == cp_model.OPTIMAL:  # 邻域内已证明最优，换种子也不会更好
            break
        fails += 1
        if fails >= patience:
            break
    return cur.tolist(), log


def _bposd_chunk(D, L, seedseq, n: int, osd_order: int, max_iter: int, deadline: float | None,
                 stop_below: int | None):
    """论文 Eq.(12)：每次随机 η = a·L + b·D（a≠0），BP-OSD 解 [D; ηᵀ] ξ = (0,…,0,1)。
    返回 (解列表 [(trial, 列号...)], 实际试验次数)。"""
    from ldpc import BpOsdDecoder
    rng = np.random.default_rng(seedseq)
    Dr = sp.csr_matrix(D).astype(np.uint8)
    Lr = sp.csr_matrix(L).astype(np.uint8)
    nobs, nd = Lr.shape[0], Dr.shape[0]
    syn = np.zeros(nd + 1, dtype=np.uint8)
    syn[-1] = 1
    out, done = [], 0
    for trial in range(n):
        if deadline is not None and time.time() > deadline:
            break
        a = rng.integers(0, 2, nobs)
        if not a.any():
            a[rng.integers(nobs)] = 1
        b = rng.integers(0, 2, nd)
        eta = (a @ Lr + b @ Dr) % 2
        H = sp.vstack([Dr, sp.csr_matrix(eta.astype(np.uint8))]).tocsr().astype(np.uint8)
        dec = BpOsdDecoder(H, error_rate=0.01, max_iter=max_iter, bp_method="minimum_sum",
                           osd_method="osd_cs", osd_order=osd_order)
        xi = np.asarray(dec.decode(syn), dtype=np.uint8)
        done += 1
        idx = np.nonzero(xi)[0]
        if len(idx) == 0 or not _is_logical(Dr, Lr, idx):
            continue
        out.append((trial, tuple(int(j) for j in idx)))
        if stop_below is not None and len(idx) < stop_below:
            break
    return out, done


def _call(args):
    fn, kw = args
    return fn(**kw)


def _pmap(fn, kwargs_list, num_workers: int):
    """按顺序返回结果；num_workers > 1 时用 spawn 进程池。"""
    if num_workers <= 1 or len(kwargs_list) <= 1:
        return [fn(**kw) for kw in kwargs_list]
    import concurrent.futures as cf
    import multiprocessing as mp
    with cf.ProcessPoolExecutor(max_workers=num_workers, mp_context=mp.get_context("spawn")) as ex:
        return list(ex.map(_call, [(fn, kw) for kw in kwargs_list]))


# ---------------------------------------------------------------------------
# 上界
# ---------------------------------------------------------------------------

def upper_bound(circuit_with_noise: stim.Circuit, *, seed: int = 0,
                methods=DEFAULT_METHODS,
                stim_search_size: int = 4, stim_search_degree: int = 4, stim_search_increasing: bool = False,
                stim_search_timeout_s: float | None = None,
                bposd_trials: int = 1500, bposd_osd_order: int = 2, bposd_max_iter: int = 100,
                lns_starts: int = 96, lns_hops: int = 1, lns_det_time: float = 1.0, lns_max_chain: int = 4,
                lns_max_excess: int = 3, num_workers: int = 1,
                stop_below: int | None = None, max_seconds: float | None = None) -> DistanceResult:
    """d_circ 的上界：多种方法取经注入验证的最短见证。

    Args:
        circuit_with_noise: 带噪声的 memory 电路（噪声决定故障位置；概率大小无关）。
        seed: 唯一的随机性来源（BP-OSD 的 η 抽样、CP-SAT 的随机种子、注入采样）。
        methods: graphlike / stim_search / bposd（bposd 含 LNS 精修，lns_starts=0 则关闭 LNS）。
        stim_search_*: stim 截断搜索参数；stim_search_timeout_s 给出时在子进程里限时运行（超时只记为
            该方法 timeout，其他方法照常）。
        bposd_trials, bposd_osd_order, bposd_max_iter: BP-OSD 随机 η 试验次数与解码器参数。
        lns_starts: 对多少个不同的低权重 BP-OSD 解做邻域精修；lns_hops: 邻域跳数；
        lns_det_time: 每次 CP-SAT 子问题的确定性时间上限（与机器速度无关，保证可复现）；
        lns_max_chain: 一个起点上连续改进的最多次数。
        lns_max_excess: 只用权重 ≤ (BP-OSD 最好解 + lns_max_excess) 的起点。
        num_workers: BP-OSD 块与 LNS 起点的并行进程数。结果与 num_workers 无关（每块/每个起点的种子固定）。
        stop_below: 一旦得到验证通过且权重 < stop_below 的见证就停止（门槛判定用；这时报告的权重
            只保证 < stop_below，不一定是全部预算下能找到的最小值）。
        max_seconds: 墙钟软上限（在试验之间检查；触发时结果依赖机器速度，stopped_early=True）。
    """
    t0 = time.time()
    deadline = None if max_seconds is None else t0 + max_seconds
    params = dict(methods=list(methods), stim_search_size=stim_search_size, stim_search_degree=stim_search_degree,
                  stim_search_increasing=stim_search_increasing, stim_search_timeout_s=stim_search_timeout_s,
                  bposd_trials=bposd_trials, bposd_osd_order=bposd_osd_order, bposd_max_iter=bposd_max_iter,
                  lns_starts=lns_starts, lns_hops=lns_hops, lns_det_time=lns_det_time, lns_max_chain=lns_max_chain,
                  lns_max_excess=lns_max_excess, num_workers=num_workers, stop_below=stop_below, max_seconds=max_seconds)
    unknown = set(methods) - {"graphlike", "stim_search", "bposd"}
    if unknown:
        raise ValueError(f"unknown distance methods {sorted(unknown)}")
    flat = circuit_with_noise.flattened()
    results: list[MethodResult] = []
    best: list[Witness | None] = [None]

    def hit() -> bool:
        return stop_below is not None and best[0] is not None and best[0].weight < stop_below

    def late() -> bool:
        return deadline is not None and time.time() > deadline

    def record(name: str, faults: list[Fault], t1: float, extra: dict | None = None, note: str = "") -> Witness:
        w = _make_witness(flat, faults, name, seed)
        if w.verified and (best[0] is None or w.weight < best[0].weight):
            best[0] = w
        sec = round(time.time() - t1, 3)
        if w.verified:
            results.append(MethodResult(name, "ok", w.weight, sec, (note + "; " if note else "") + w.verification,
                                        extra or {}))
        else:
            results.append(MethodResult(name, "rejected", None, sec,
                                        f"witness of weight {w.weight} failed injection: {w.verification}",
                                        {**(extra or {}), "unverified_weight": w.weight}))
        return w

    stopped = False
    for name in ("graphlike", "stim_search", "bposd"):
        if name not in methods:
            continue
        if hit() or late():
            results.append(MethodResult(name, "skipped", None, 0.0, "stopped early (stop_below reached or "
                                                                     "max_seconds exceeded)"))
            stopped = True
            continue
        t1 = time.time()
        if name == "graphlike":
            try:
                g = flat.shortest_graphlike_error(ignore_ungraphlike_errors=True, canonicalize_circuit_errors=True)
                record(name, _faults_from_explained(g), t1)
            except ValueError as e:
                results.append(MethodResult(name, "none", None, round(time.time() - t1, 3), str(e).splitlines()[0]))
        elif name == "stim_search":
            kw = dict(circuit=str(flat), size=stim_search_size, degree=stim_search_degree,
                      increasing=stim_search_increasing)
            try:
                if stim_search_timeout_s is None:
                    res = _stim_search_worker(**kw)
                else:
                    res = run_in_subprocess("evaluators.distance", "_stim_search_worker", kw, stim_search_timeout_s)
                record(name, [Fault(**f) for f in res["faults"]], t1)
            except subprocess.TimeoutExpired:
                results.append(MethodResult(name, "timeout", None, round(time.time() - t1, 3),
                                            f"did not finish within {stim_search_timeout_s}s"))
            except (ValueError, RuntimeError) as e:
                results.append(MethodResult(name, "none", None, round(time.time() - t1, 3), str(e).splitlines()[0]))
        else:
            stopped |= _run_bposd(flat, seed, params, deadline, stop_below, num_workers, results, record, hit, late)
    stopped = stopped or late()
    w = best[0]
    return DistanceResult(weight=None if w is None else w.weight, witness=w, methods=results,
                          seconds=round(time.time() - t0, 3), seed=seed, params=params, stopped_early=bool(stopped))


def _run_bposd(flat, seed, params, deadline, stop_below, num_workers, results, record, hit, late) -> bool:
    t1 = time.time()
    try:
        cols = dem_columns(_dem(flat))
    except ValueError as e:
        results.append(MethodResult("bposd", "error", None, 0.0, str(e).splitlines()[0]))
        return False
    D, L = cols.D, cols.L
    stopped = False
    trivial = [j for j in range(cols.num_columns) if D[:, j].nnz == 0]
    if trivial:  # 一个机制本身就翻转 observable 且不触发任何 detector
        pool, done = {(trivial[0],): (0, 0)}, 0
    else:
        n = params["bposd_trials"]
        seqs = np.random.SeedSequence(seed).spawn(max(1, -(-n // _BPOSD_CHUNK)))
        jobs = [dict(D=D, L=L, seedseq=ss, n=min(_BPOSD_CHUNK, n - c * _BPOSD_CHUNK),
                     osd_order=params["bposd_osd_order"], max_iter=params["bposd_max_iter"],
                     deadline=deadline, stop_below=stop_below) for c, ss in enumerate(seqs)]
        if num_workers <= 1:
            outs = []
            for jb in jobs:  # 顺序执行时命中 stop_below 就不再跑后面的块
                outs.append(_bposd_chunk(**jb))
                if stop_below is not None and any(len(k) < stop_below for _, k in outs[-1][0]):
                    stopped = True
                    break
        else:
            outs = _pmap(_bposd_chunk, jobs, num_workers)
        pool: dict[tuple, tuple[int, int]] = {}
        done = 0
        for c, (sols_c, d_c) in enumerate(outs):
            done += d_c
            for trial, key in sols_c:
                pool.setdefault(key, (c, trial))
    sols = sorted(pool, key=lambda k: (len(k), pool[k]))
    hist: dict[int, int] = {}
    for k in sols:
        hist[len(k)] = hist.get(len(k), 0) + 1
    extra = {"trials": done, "num_columns": cols.num_columns, "num_detectors": cols.num_detectors,
             "solution_weight_histogram": {int(a): b for a, b in sorted(hist.items())[:8]}}
    if not sols:
        results.append(MethodResult("bposd", "none", None, round(time.time() - t1, 3),
                                    f"no logical error found in {done} trials", extra))
        return stopped or late()
    w0 = record("bposd", _faults_from_columns(flat, cols, sols[0]), t1, extra)
    if params["lns_starts"] <= 0 or w0.weight <= 1:
        return stopped or late()
    if hit() or late():
        results.append(MethodResult("bposd_lns", "skipped", None, 0.0, "stopped early"))
        return True
    # LNS：从不同的低权重 BP-OSD 解出发，在邻域里用 CP-SAT 找更短的逻辑错误
    t2 = time.time()
    starts = [k for k in sols if len(k) <= len(sols[0]) + params["lns_max_excess"]][:params["lns_starts"]]
    jobs = [dict(D=D, L=L, start=list(k), hops=params["lns_hops"], det_time=params["lns_det_time"],
                 seed=seed * 1_000_003 + i, max_chain=params["lns_max_chain"]) for i, k in enumerate(starts)]
    if num_workers <= 1:
        outs = []
        for jb in jobs:
            if late() or (stop_below is not None and outs and min(len(o[0]) for o in outs) < stop_below):
                stopped = True
                break
            outs.append(_lns_chain(**jb))
    else:
        outs = _pmap(_lns_chain, jobs, num_workers)
    best_i = min(range(len(outs)), key=lambda i: (len(outs[i][0]), i)) if outs else None
    extra2 = {"starts": len(outs), "start_weights": [len(k) for k in starts[:len(outs)]],
              "final_weights": [len(o[0]) for o in outs],
              "improvement_chains": {i: o[1] for i, o in enumerate(outs) if o[1]}}
    if best_i is None or len(outs[best_i][0]) >= len(sols[0]):
        results.append(MethodResult("bposd_lns", "ok" if w0.verified else "rejected", w0.weight if w0.verified else None,
                                    round(time.time() - t2, 3), "no improvement over BP-OSD", extra2))
    else:
        record("bposd_lns", _faults_from_columns(flat, cols, outs[best_i][0]), t2, extra2,
               note=f"improved {len(starts[best_i])} -> {len(outs[best_i][0])} from start #{best_i}")
    return stopped or late()


def upper_bound_json(circuit: str, kwargs: dict) -> dict:
    """子进程入口：upper_bound 的 JSON 版本。"""
    return upper_bound(stim.Circuit(circuit), **kwargs).to_dict()


# ---------------------------------------------------------------------------
# 下界（精确方法）
# ---------------------------------------------------------------------------

def lower_bound(circuit_with_noise: stim.Circuit, *, method: str = "cpsat", time_limit_s: float = 60.0,
                seed: int = 0, target: int | None = None, num_workers: int = 1) -> LowerBoundResult:
    """精确求解或证明下界。

    method: "cpsat" | "maxsat" | "milp"。target=w：判定是否存在权重 ≤ w−1 的逻辑错误，
    不可行即证明 d_circ ≥ w（status="infeasible_below_target"）。
    num_workers：CP-SAT 线程数（多线程时 CP-SAT 结果不保证可复现，但证明仍然有效）。
    """
    t0 = time.time()
    flat = circuit_with_noise.flattened()
    if method == "maxsat":
        try:
            r = run_in_subprocess("evaluators.distance", "_maxsat_worker",
                                  {"circuit": str(flat), "target": target}, time_limit_s)
        except subprocess.TimeoutExpired:
            dem = _dem(flat)
            return LowerBoundResult("maxsat", "timeout", None, None, round(time.time() - t0, 3),
                                    dem.num_errors, dem.num_detectors, f"RC2 did not finish within {time_limit_s}s")
        return LowerBoundResult(**{**r, "seconds": round(time.time() - t0, 3)})
    cols = dem_columns(_dem(flat))
    nd, ne = cols.D.shape
    if method == "cpsat":
        from ortools.sat.python import cp_model
        M, x = _xor_model(cols.D, cols.L, np.arange(ne), None if target is None else target - 1)
        s = _cpsat_solver(seed, None, time_limit_s, workers=num_workers)
        st = s.Solve(M)
        name = s.StatusName(st)
        if st == cp_model.INFEASIBLE:
            lb = target if target is not None else None
            return LowerBoundResult("cpsat", "infeasible_below_target" if target is not None else "infeasible",
                                    lb, None, round(time.time() - t0, 3), ne, nd, name)
        ub = int(round(s.ObjectiveValue())) if st in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None
        lb = int(np.ceil(s.BestObjectiveBound() - 1e-6)) if st != cp_model.MODEL_INVALID else None
        if st == cp_model.OPTIMAL:
            status = "optimal" if target is None else "feasible_below_target"
            lb = ub if target is None else lb
        else:
            status = "feasible_below_target" if (target is not None and ub is not None) else "bound"
        return LowerBoundResult("cpsat", status, lb, ub, round(time.time() - t0, 3), ne, nd, name)
    if method == "milp":
        return _milp_lower(cols, time_limit_s, target, t0)
    raise ValueError(f"unknown lower-bound method {method!r}")


def _maxsat_worker(circuit: str, target: int | None) -> dict:
    from pysat.examples.rc2 import RC2
    from pysat.formula import WCNF
    flat = stim.Circuit(circuit)
    dem = flat.detector_error_model(decompose_errors=False)
    wcnf = WCNF(from_string=flat.shortest_error_sat_problem(format="WDIMACS"))
    with RC2(wcnf) as rc2:
        model = rc2.compute()
        cost = rc2.cost
    if model is None:
        return dict(method="maxsat", status="infeasible", lower_bound=None, upper_bound=None, seconds=0.0,
                    num_columns=dem.num_errors, num_detectors=dem.num_detectors, message="no logical error exists")
    return dict(method="maxsat", status="optimal", lower_bound=int(cost), upper_bound=int(cost), seconds=0.0,
                num_columns=dem.num_errors, num_detectors=dem.num_detectors, message="RC2 optimum")


def _milp_lower(cols: DemColumns, time_limit_s, target, t0) -> LowerBoundResult:
    from scipy.optimize import Bounds, LinearConstraint, milp
    D = cols.D.tocsr().astype(np.int64)
    L = cols.L.tocsr().astype(np.int64)
    nd, ne = D.shape
    no = L.shape[0]
    rw = np.asarray(D.sum(axis=1)).ravel()
    lw = np.asarray(L.sum(axis=1)).ravel()
    # 变量：ξ (ne, 0/1) | s (nd, 整数) | t (no, 整数) | y (no, 0/1)
    nv = ne + nd + 2 * no
    c = np.concatenate([np.ones(ne), np.zeros(nd + 2 * no)])
    A1 = sp.hstack([D, -2 * sp.identity(nd), sp.csr_matrix((nd, 2 * no))])
    A2 = sp.hstack([L, sp.csr_matrix((no, nd)), -2 * sp.identity(no), -sp.identity(no)])
    A3 = sp.hstack([sp.csr_matrix((1, ne + nd + no)), sp.csr_matrix(np.ones((1, no)))])
    rows = [A1, A2, A3]
    lb = [np.zeros(nd), np.zeros(no), [1]]
    ub = [np.zeros(nd), np.zeros(no), [no]]
    if target is not None:
        rows.append(sp.hstack([sp.csr_matrix(np.ones((1, ne))), sp.csr_matrix((1, nd + 2 * no))]))
        lb.append([0])
        ub.append([target - 1])
    A = sp.vstack(rows).tocsr()
    bounds = Bounds(np.zeros(nv), np.concatenate([np.ones(ne), np.floor(rw / 2), np.floor(lw / 2), np.ones(no)]))
    opts = {"time_limit": time_limit_s, "disp": False}
    r = milp(c, constraints=LinearConstraint(A, np.concatenate(lb), np.concatenate(ub)),
             integrality=np.ones(nv), bounds=bounds, options=opts)
    ubv = int(round(r.fun)) if r.x is not None else None
    dual = getattr(r, "mip_dual_bound", None)
    lbv = int(np.ceil(dual - 1e-6)) if dual is not None and np.isfinite(dual) else None
    if r.status == 0:
        status = "optimal" if target is None else "feasible_below_target"
        if target is None:
            lbv = ubv
    elif r.status == 2:  # infeasible
        status = "infeasible_below_target" if target is not None else "infeasible"
        lbv = target
    else:
        status = "bound"
    return LowerBoundResult("milp", status, lbv, ubv, round(time.time() - t0, 3), ne, nd, str(r.message))
