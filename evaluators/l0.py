"""L0 合法性检查：候选 syndrome 提取（memory 实验）电路是否“合法、可打分”。

入口：
    check_l0(circuit, code, basis, constraints=None) -> L0Report
    basis="both"（评估器默认口径）时 circuit = {"Z": z_memory, "X": x_memory}，两个基底都要通过，
    d_circ 取较小值；检查项名前加 "Z:" / "X:" 前缀（auditor E-001 H2：调度可能牺牲一个基底）。

输入是**无噪声**候选电路（memory 实验：数据比特初始化 → 若干轮 syndrome 提取 → 数据比特
在 basis 下读出）。返回逐项检查结果和可读诊断（L0Report.to_text() 可直接喂给 LLM）。

检查项与方法（详见 evaluators/README.md）：
  语法层（总是运行）：
    instructions       只用允许的门；无噪声；无经典控制/sweep；DETECTOR/OBSERVABLE 只引用测量记录
    qubit_count        circuit.num_qubits <= max_qubits
    connectivity       每个双比特门的比特对在允许的边集中
    tick_structure     有 TICK；同一层（TICK 之间）每个比特至多被一个操作作用
  语义层（语法层全部通过才运行）：
    determinism        无噪声电路 detector_error_model(allow_gauge_detectors=False) 不报错
    data_layout        每个数据比特：先复位（双比特门之前），最后一次操作是 basis 基测量
    observables        observable 只由数据比特的最终读出构成；对应向量 v ∈ ker(H_other)，
                       v ∉ rowspace(H_basis)，模稳定子线性无关，数量 = k（或声明值）
    logical_injection  用 detecting_regions 在“数据制备完成后”与“最终读出前”两个时刻注入
                       每个逻辑算符（Z memory 注入 LX），要求不触发任何 detector、且对
                       observable 的翻转矩阵满秩
    stabilizer_coverage 默认（coverage_method="flows"）：对去掉数据制备与读出的整条电路求
                       flow_generators，得到每个稳定子生成元 s 的“测量集合陪集” A_s = M_s + D；
                       s 的测量次数 = 时间上不重叠、各含 A_s 一个元素的层区间的最大个数（最小跨度基 +
                       区间调度），不需要干净切口，支持辅助比特跨轮流水（README §3.2）；
                       必须 = rounds（或全部相等）。旧方法 "segments"（在干净切口处切段）只为对照保留
    detector_coverage  basis 型生成元相邻两次测量的比较、首轮、末轮与数据读出的比较
                       都必须落在 detector 记录集合的 GF(2) 张成里（模掉单个窗口内的确定奇偶）
  距离层（以上全部通过才运行）：
    circuit_distance   对 add_noise 后的电路调用 distance.upper_bound：stim 截断搜索、
                       shortest_graphlike_error、BP-OSD 随机 η 见证搜索 + CP-SAT 邻域精修，
                       取经注入验证的最短逻辑错误（上界），要求 >= min_circuit_distance
"""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

import numpy as np
import stim

from evaluators import distance
from evaluators.codes import CSSCode, GF2Basis, bits_to_int, in_rowspace, rank
from evaluators.noise import add_noise, find_noise_instructions

__all__ = ["L0Constraints", "CheckResult", "L0Report", "check_l0", "DEFAULT_ALLOWED_GATES"]

DEFAULT_ALLOWED_GATES = frozenset({"R", "RX", "M", "MX", "MR", "MRX", "H", "CX", "CZ", "I"})
_ALWAYS_ALLOWED = frozenset({"TICK", "DETECTOR", "OBSERVABLE_INCLUDE", "QUBIT_COORDS", "SHIFT_COORDS"})
_RESET_BASIS = {"R": "Z", "RZ": "Z", "RX": "X", "RY": "Y", "MR": "Z", "MRZ": "Z", "MRX": "X", "MRY": "Y"}
_MEAS_BASIS = {"M": "Z", "MZ": "Z", "MX": "X", "MY": "Y", "MR": "Z", "MRZ": "Z", "MRX": "X", "MRY": "Y"}
_RESET_OF = {"Z": "R", "X": "RX", "Y": "RY"}


@dataclass
class L0Constraints:
    """L0 的可配置约束。所有字段由评估任务（不是候选）给定。"""

    allowed_gates: Iterable[str] = DEFAULT_ALLOWED_GATES
    max_qubits: int | None = None
    # 允许的双比特门作用对（无序）。None = 不限连接。
    allowed_edges: Iterable[tuple[int, int]] | None = None
    # data_qubits[j] = 码第 j 列对应的电路比特编号。None = 0..n-1。
    data_qubits: Sequence[int] | None = None
    # 要求的 syndrome 提取轮数（每个稳定子生成元恰好被测量 rounds 次）。None = 只要求全部相等且 >= 1。
    rounds: int | None = None
    # observable 数量。None = 码的 k。
    num_observables: int | None = None
    # 是否要求非 basis 型稳定子（Z memory 中的 X 型）的相邻轮比较也在 detector 张成里
    require_opposite_type_detectors: bool = False
    # 电路级距离下限。None = 不检查（除非 compute_distance=True，则只报告）。
    min_circuit_distance: int | None = None
    compute_distance: bool = False
    # 默认 SD6（含逐层空闲噪声）。距离只取决于噪声机制的结构，不取决于 p。
    distance_noise_model: str = "sd6"
    distance_noise_p: float = 1e-3
    distance_noise_idle: bool | None = None  # None = 模型默认（uniform_depolarizing 默认有空闲噪声）
    # 距离上界搜索（evaluators/distance.py 的 upper_bound；多种方法取经注入验证的最短见证）
    distance_methods: tuple[str, ...] = ("graphlike", "stim_search", "bposd")
    distance_seed: int = 0
    # search_for_undetectable_logical_errors 的截断参数（启发式；见 README）
    dont_explore_detection_event_sets_with_size_above: int = 4
    dont_explore_edges_with_degree_above: int = 4
    dont_explore_edges_increasing_symptom_degree: bool = False
    use_graphlike_bound: bool = True
    # BP-OSD 随机 η 见证搜索 + CP-SAT 邻域精修（LNS）的预算（试验次数/确定性时间，结果只取决于 seed）
    distance_bposd_trials: int = 1500
    distance_lns_starts: int = 96
    distance_lns_det_time: float = 1.0
    distance_num_workers: int = 1
    # True：一旦找到权重 < min_circuit_distance 的见证就停止（判定不变，省时间；报告的 d_circ 只保证低于门槛）
    distance_early_stop: bool = True
    # 距离计算的硬超时（秒，子进程）。None = 在本进程直接计算（无超时）。超时 = 不通过。
    # gross code 3 轮单基底在默认预算下单进程约 3–5 分钟。
    distance_timeout_s: float | None = 1800.0
    # 规模保护：展开后的指令数上限
    max_flat_instructions: int = 2_000_000
    # 覆盖检查（stabilizer_coverage / detector_coverage）的方法（2026-10-02 新增）：
    #   "flows"（默认）：对整条电路求 stim flow 生成元，不切段，支持辅助比特跨轮流水（README §3.2）；
    #   "segments"：旧方法，在“干净切口”处切段（流水电路会被误拒），只为对照保留。
    coverage_method: str = "flows"


@dataclass
class CheckResult:
    name: str
    status: str  # "pass" | "fail" | "skipped"
    message: str
    details: dict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == "pass"


@dataclass
class L0Report:
    passed: bool
    checks: list[CheckResult]
    d_circ: int | None = None  # basis="both" 时为两个基底的较小值（取较差者）
    elapsed_s: float = 0.0
    basis: str = ""
    per_basis: dict[str, "L0Report"] = field(default_factory=dict)

    def get(self, name: str) -> CheckResult:
        for c in self.checks:
            if c.name == name:
                return c
        raise KeyError(name)

    @property
    def failures(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status == "fail"]

    def to_text(self) -> str:
        lines = [f"L0 {'PASS' if self.passed else 'FAIL'} [basis {self.basis}]"
                 + (f" (d_circ upper bound = {self.d_circ}"
                    + (", per basis " + ", ".join(f"{b}: {r.d_circ}" for b, r in self.per_basis.items())
                       if self.per_basis else "") + ")" if self.d_circ is not None else "")]
        for c in self.checks:
            lines.append(f"[{c.status.upper()}] {c.name}: {c.message}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "basis": self.basis,
            "d_circ": self.d_circ,
            "d_circ_per_basis": {b: r.d_circ for b, r in self.per_basis.items()},
            "elapsed_s": self.elapsed_s,
            "checks": [{"name": c.name, "status": c.status, "message": c.message} for c in self.checks],
        }


# ---------------------------------------------------------------------------
# 电路解析
# ---------------------------------------------------------------------------

@dataclass
class _Op:
    layer: int
    name: str
    kind: str  # 1q / 2q / reset / measure / measure_reset / other
    qubits: tuple[int, ...]
    meas: tuple[int, ...]  # 全局测量记录编号


@dataclass
class _Parsed:
    flat: stim.Circuit
    ops: list[_Op]
    num_layers: int
    num_measurements: int
    meas_op: dict[int, _Op]
    detectors: list[frozenset[int]]
    observables: dict[int, frozenset[int]]


def _kind(name: str) -> str:
    gd = stim.gate_data(name)
    if gd.is_unitary and gd.is_single_qubit_gate:
        return "1q"
    if gd.is_unitary and gd.is_two_qubit_gate:
        return "2q"
    if gd.is_single_qubit_gate and gd.produces_measurements and gd.is_reset:
        return "measure_reset"
    if gd.is_single_qubit_gate and gd.produces_measurements:
        return "measure"
    if gd.is_single_qubit_gate and gd.is_reset:
        return "reset"
    return "other"


def _parse(flat: stim.Circuit) -> _Parsed:
    ops: list[_Op] = []
    layer = 0
    m = 0
    meas_op: dict[int, _Op] = {}
    detectors: list[frozenset[int]] = []
    obs: dict[int, set[int]] = {}
    for inst in flat:
        name = inst.name
        if name == "TICK":
            layer += 1
            continue
        if name in ("QUBIT_COORDS", "SHIFT_COORDS"):
            continue
        if name == "DETECTOR":
            s: set[int] = set()
            for t in inst.targets_copy():
                if t.is_measurement_record_target:
                    s ^= {m + t.value}
            detectors.append(frozenset(s))
            continue
        if name == "OBSERVABLE_INCLUDE":
            k = int(inst.gate_args_copy()[0])
            s = obs.setdefault(k, set())
            for t in inst.targets_copy():
                if t.is_measurement_record_target:
                    s ^= {m + t.value}
            continue
        kind = _kind(name)
        if kind in ("1q", "reset", "measure", "measure_reset"):
            for t in inst.targets_copy():
                mm: tuple[int, ...] = ()
                if kind in ("measure", "measure_reset"):
                    mm = (m,)
                    m += 1
                op = _Op(layer, name, kind, (t.value,), mm)
                ops.append(op)
                for x in mm:
                    meas_op[x] = op
        elif kind == "2q":
            for grp in inst.target_groups():
                ops.append(_Op(layer, name, kind, tuple(t.value for t in grp), ()))
        else:
            tmp = stim.Circuit()
            tmp.append(inst)
            nm = tmp.num_measurements
            qs = tuple(sorted({t.value for t in inst.targets_copy() if t.is_qubit_target or t.is_x_target
                               or t.is_y_target or t.is_z_target}))
            op = _Op(layer, name, "other", qs, tuple(range(m, m + nm)))
            ops.append(op)
            for x in op.meas:
                meas_op[x] = op
            m += nm
    return _Parsed(flat, ops, layer + 1, m, meas_op, detectors, {k: frozenset(v) for k, v in obs.items()})


def _flat_size(circuit: stim.Circuit, cap: int) -> int:
    """展开 REPEAT 后的指令数（超过 cap 立即返回），在 flattened() 之前防止 REPEAT 1e9 之类的 DoS。"""
    total = 0
    for inst in circuit:
        if isinstance(inst, stim.CircuitRepeatBlock):
            total += inst.repeat_count * _flat_size(inst.body_copy(), cap)
        else:
            total += 1
        if total > cap:
            return total
    return total


def _fmt_list(xs, limit: int = 12) -> str:
    xs = list(xs)
    s = ", ".join(str(x) for x in xs[:limit])
    return s + (f", ... (+{len(xs) - limit} more)" if len(xs) > limit else "")


# ---------------------------------------------------------------------------
# 语法层检查
# ---------------------------------------------------------------------------

def _check_instructions(flat: stim.Circuit, allowed: frozenset[str]) -> CheckResult:
    issues: list[str] = []
    noise = find_noise_instructions(flat)
    for n in noise[:10]:
        issues.append(f"noise instruction present: {n}")
    if len(noise) > 10:
        issues.append(f"... and {len(noise) - 10} more noise instructions")
    layer = 0
    bad_gates: dict[str, int] = {}
    for i, inst in enumerate(flat):
        name = inst.name
        if name == "TICK":
            layer += 1
            continue
        gd = stim.gate_data(name)
        noisy_channel = gd.is_noisy_gate and (not gd.produces_measurements or name.startswith("HERALDED"))
        if name not in _ALWAYS_ALLOWED and name not in allowed and not noisy_channel:
            if name not in bad_gates:
                bad_gates[name] = layer
        for t in inst.targets_copy():
            if name in ("DETECTOR", "OBSERVABLE_INCLUDE"):
                if not t.is_measurement_record_target:
                    issues.append(f"#{i} (layer {layer}) {inst}: {name} may only reference measurement records "
                                  f"(rec[-k]); Pauli/qubit targets are not allowed")
                    break
            elif name in ("QUBIT_COORDS",):
                continue
            elif t.is_measurement_record_target or t.is_sweep_bit_target:
                issues.append(f"#{i} (layer {layer}) {inst}: classically controlled / sweep-controlled gates are "
                              f"not allowed")
                break
    for g, l in bad_gates.items():
        issues.append(f"gate {g} is not in the allowed gate set {sorted(allowed)} (first used in layer {l})")
    if issues:
        return CheckResult("instructions", "fail", "; ".join(issues[:15]), {"issues": issues})
    return CheckResult("instructions", "pass", "only allowed, noiseless instructions")


def _check_qubit_count(circuit: stim.Circuit, max_qubits: int | None) -> CheckResult:
    nq = circuit.num_qubits
    if max_qubits is None:
        return CheckResult("qubit_count", "pass", f"{nq} qubits (no limit)", {"num_qubits": nq})
    if nq > max_qubits:
        return CheckResult("qubit_count", "fail",
                           f"circuit uses {nq} qubits (max index {nq - 1}), limit is {max_qubits}",
                           {"num_qubits": nq})
    return CheckResult("qubit_count", "pass", f"{nq} <= {max_qubits} qubits", {"num_qubits": nq})


def _check_connectivity(parsed: _Parsed, edges: set[frozenset[int]] | None) -> CheckResult:
    if edges is None:
        return CheckResult("connectivity", "pass", "no connectivity constraint")
    bad: dict[frozenset[int], tuple[int, str]] = {}
    for op in parsed.ops:
        if op.kind == "2q" or (op.kind == "other" and len(op.qubits) >= 2):
            if op.kind == "2q":
                pairs = [frozenset(op.qubits)]
            else:
                pairs = [frozenset((a, b)) for i, a in enumerate(op.qubits) for b in op.qubits[i + 1:]]
            for e in pairs:
                if e not in edges and e not in bad:
                    bad[e] = (op.layer, op.name)
    if bad:
        desc = [f"{op_name} on {tuple(sorted(e))} (layer {l})" for e, (l, op_name) in bad.items()]
        return CheckResult("connectivity", "fail",
                           f"{len(bad)} two-qubit interaction(s) outside the allowed coupling graph: "
                           + _fmt_list(desc, 8), {"violations": desc})
    return CheckResult("connectivity", "pass", "all two-qubit gates on allowed edges")


def _check_ticks(parsed: _Parsed) -> CheckResult:
    if parsed.num_layers <= 1 and parsed.ops:
        return CheckResult("tick_structure", "fail",
                           "circuit has no TICK instructions; every time step must be delimited by TICK")
    seen: dict[tuple[int, int], str] = {}
    clashes: list[str] = []
    for op in parsed.ops:
        for q in op.qubits:
            key = (op.layer, q)
            if key in seen:
                if len(clashes) < 10:
                    clashes.append(f"qubit {q} in layer {op.layer}: {seen[key]} and {op.name}")
                continue
            seen[key] = op.name
    if clashes:
        return CheckResult("tick_structure", "fail",
                           "qubits acted on more than once within a single time step (between TICKs); "
                           "each operation must get its own time step: " + "; ".join(clashes),
                           {"clashes": clashes})
    return CheckResult("tick_structure", "pass", f"{parsed.num_layers} time steps, <=1 op per qubit per step")


# ---------------------------------------------------------------------------
# 语义层检查
# ---------------------------------------------------------------------------

def _check_determinism(circuit: stim.Circuit) -> CheckResult:
    try:
        circuit.detector_error_model(allow_gauge_detectors=False)
    except ValueError as e:
        msg = str(e).splitlines()[0]
        detail = ""
        try:
            circuit.detecting_regions()
        except ValueError as e2:
            lines = [ln.strip() for ln in str(e2).splitlines() if " vs " in ln]
            if lines:
                detail = (" Anticommutations found while back-propagating (target vs reset/measurement): "
                          + _fmt_list(lines, 6))
        return CheckResult("determinism", "fail",
                           f"noiseless circuit has non-deterministic detectors/observables: {msg}.{detail}",
                           {"stim_error": str(e)})
    return CheckResult("determinism", "pass",
                       f"all {circuit.num_detectors} detectors and {circuit.num_observables} observables deterministic")


@dataclass
class _Layout:
    data: list[int]
    final_rec: dict[int, int]  # data qubit -> final readout measurement index
    final_ops: set[int]  # id() of final readout ops
    t_start: int  # tick index for injection after preparation
    t_end: int | None  # tick index for injection before final readout
    first_data_2q_layer: int | None


def _check_data_layout(parsed: _Parsed, data: list[int], basis: str) -> tuple[CheckResult, _Layout | None]:
    dset = set(data)
    per_q: dict[int, list[_Op]] = {q: [] for q in data}
    first_2q: int | None = None
    last_2q: int | None = None
    for op in parsed.ops:
        on_data = [q for q in op.qubits if q in dset]
        for q in on_data:
            per_q[q].append(op)
        if on_data and (op.kind == "2q" or (op.kind == "other" and len(op.qubits) > 1)):
            first_2q = op.layer if first_2q is None else first_2q
            last_2q = op.layer
    issues: list[str] = []
    final_rec: dict[int, int] = {}
    final_ops: set[int] = set()
    reset_layers = []
    final_layers = []
    for j, q in enumerate(data):
        ops = per_q[q]
        if not ops:
            issues.append(f"data qubit {q} (code column {j}) is never used")
            continue
        first = ops[0]
        if first.kind not in ("reset", "measure_reset"):
            issues.append(f"data qubit {q} (column {j}): first operation is {first.name} in layer {first.layer}; "
                          f"data qubits must be explicitly reset before use")
        else:
            reset_layers.append(first.layer)
        if first_2q is not None:
            pre = [o for o in ops if o.layer < first_2q]
            bad = [o for o in pre if o.kind not in ("reset", "1q")]
            if not pre or bad:
                issues.append(f"data qubit {q} (column {j}) is not cleanly prepared (reset + single-qubit gates) "
                              f"before the first data two-qubit gate in layer {first_2q}")
        last = ops[-1]
        if last.kind not in ("measure", "measure_reset") or _MEAS_BASIS.get(last.name) != basis:
            issues.append(f"data qubit {q} (column {j}): last operation is {last.name} in layer {last.layer}; "
                          f"a {basis}-memory must end with a {basis}-basis measurement of every data qubit "
                          f"({'M/MR' if basis == 'Z' else 'MX/MRX'})")
        else:
            final_rec[q] = last.meas[0]
            final_ops.add(id(last))
            final_layers.append(last.layer)
    if issues:
        return CheckResult("data_layout", "fail", "; ".join(issues[:8]), {"issues": issues}), None
    if first_2q is not None:
        t_start = first_2q - 1
    else:
        t_start = max(reset_layers)
    t_end = None
    if final_layers and (last_2q is None or last_2q < min(final_layers)) and min(final_layers) >= 1:
        t_end = min(final_layers) - 1
    lay = _Layout(list(data), final_rec, final_ops, t_start, t_end, first_2q)
    return CheckResult("data_layout", "pass",
                       f"{len(data)} data qubits reset before first entangling layer {first_2q} and read out in "
                       f"{basis} basis at the end"), lay


def _check_observables(parsed: _Parsed, code: CSSCode, basis: str, layout: _Layout,
                       expected: int) -> CheckResult:
    H_basis = code.HZ if basis == "Z" else code.HX
    H_other = code.HX if basis == "Z" else code.HZ
    L_dual = code.LX if basis == "Z" else code.LZ
    rec_to_col = {r: layout.data.index(q) for q, r in layout.final_rec.items()}
    issues: list[str] = []
    obs_ids = sorted(parsed.observables)
    if len(obs_ids) != expected:
        issues.append(f"circuit declares {len(obs_ids)} observable(s) {obs_ids}, expected {expected} "
                      f"(code k={code.k})")
    if obs_ids and obs_ids != list(range(len(obs_ids))):
        issues.append(f"observable indices must be 0..{len(obs_ids) - 1}, got {obs_ids}")
    vecs = []
    coeffs = {}
    for k in obs_ids:
        recs = parsed.observables[k]
        if not recs:
            issues.append(f"observable L{k} is empty (includes no measurements)")
            continue
        bad = sorted(r for r in recs if r not in rec_to_col)
        if bad:
            desc = []
            for r in bad[:6]:
                op = parsed.meas_op.get(r)
                desc.append(f"rec#{r} = {op.name} on qubit(s) {list(op.qubits)} in layer {op.layer}"
                            if op else f"rec#{r}")
            issues.append(f"observable L{k} includes measurements that are not final {basis}-basis data readouts: "
                          + _fmt_list(desc, 6))
            continue
        v = np.zeros(code.n, dtype=np.uint8)
        for r in recs:
            v[rec_to_col[r]] ^= 1
        synd = (H_other.astype(np.int64) @ v) % 2
        if synd.any():
            issues.append(f"observable L{k} (data columns {np.flatnonzero(v).tolist()}) anticommutes with "
                          f"{'X' if basis == 'Z' else 'Z'}-stabilizer rows {np.flatnonzero(synd).tolist()[:10]}: "
                          f"not a logical operator")
            continue
        if in_rowspace(v, H_basis):
            issues.append(f"observable L{k} (data columns {_fmt_list(np.flatnonzero(v).tolist())}) is a product of "
                          f"{basis}-stabilizers: it is trivial and carries no logical information")
            continue
        vecs.append(v)
        coeffs[k] = ((L_dual.astype(np.int64) @ v) % 2).tolist()
    if vecs and rank(np.vstack([H_basis] + vecs)) != rank(H_basis) + len(vecs):
        issues.append("observables are linearly dependent modulo the stabilizer group "
                      f"(they encode fewer than {len(vecs)} independent logical operators): logical coordinates "
                      f"{coeffs}")
    if issues:
        return CheckResult("observables", "fail", "; ".join(issues), {"issues": issues})
    return CheckResult("observables", "pass",
                       f"{len(vecs)} independent nontrivial logical-{basis} observables; coordinates in the "
                       f"L{basis} basis: {coeffs}", {"logical_coordinates": coeffs})


def _logical_pauli(code: CSSCode, basis: str, j: int, data: list[int], nq: int) -> stim.PauliString:
    # Z memory: 能翻转逻辑 Z 的是 LX；X memory 则是 LZ。
    row = code.LX[j] if basis == "Z" else code.LZ[j]
    ps = stim.PauliString(nq)
    p = 1 if basis == "Z" else 3  # stim: 1=X, 2=Y, 3=Z
    for c in np.flatnonzero(row):
        ps[data[c]] = p
    return ps


def _check_logical_injection(circuit: stim.Circuit, code: CSSCode, basis: str, layout: _Layout,
                             num_obs: int) -> CheckResult:
    nq = circuit.num_qubits
    err = "X" if basis == "Z" else "Z"
    ticks = {"after data preparation": layout.t_start}
    if layout.t_end is not None:
        ticks["before final readout"] = layout.t_end
    issues: list[str] = []
    info = {}
    for label, t in ticks.items():
        if t < 0 or t >= circuit.num_ticks:
            issues.append(f"no TICK available {label} (tick {t}); add a TICK between preparation and the rounds")
            continue
        regions = circuit.detecting_regions(ticks=[t])
        F = np.zeros((num_obs, code.k), dtype=np.uint8)
        for j in range(code.k):
            P = _logical_pauli(code, basis, j, layout.data, nq)
            flipped_dets = []
            for tgt, reg in regions.items():
                ps = reg.get(t)
                if ps is None:
                    continue
                if len(ps) < nq:
                    ps = ps + stim.PauliString(nq - len(ps))
                if not ps.commutes(P):
                    if tgt.is_relative_detector_id():
                        flipped_dets.append(tgt.val)
                    elif tgt.is_logical_observable_id() and tgt.val < num_obs:
                        F[tgt.val, j] = 1
            if flipped_dets:
                issues.append(f"injecting logical {err}_{j} {label} (tick {t}) triggers detectors "
                              f"{_fmt_list(sorted(flipped_dets), 8)}: the circuit does not preserve the encoded "
                              f"logical state (a logical operator should be invisible to detectors)")
        r = rank(F) if F.size else 0
        info[label] = {"tick": t, "flip_matrix": F.tolist()}
        if r < num_obs:
            dead = [i for i in range(num_obs) if not F[i].any()]
            issues.append(f"{label} (tick {t}): logical-{err} injections flip the observables with a rank-{r} "
                          f"matrix {F.tolist()} (need rank {num_obs}); observables {dead} are not flipped by any "
                          f"logical operator, i.e. they do not track the encoded information through the circuit")
    if issues:
        return CheckResult("logical_injection", "fail", "; ".join(issues[:6]), {"issues": issues, **info})
    return CheckResult("logical_injection", "pass",
                       f"logical {err} operators injected at ticks {list(ticks.values())} are undetected and flip "
                       f"the observables with full rank", info)


def _segments(parsed: _Parsed, layout: _Layout, nq: int):
    """在干净切口处把电路切段。返回 [(layer_lo, layer_hi, stim.Circuit, local->global meas)]。

    辅助比特状态：idle（未用/测量后未复位）、prepped（复位后只有单比特门，可重放）、
    busy（复位后参与过双比特门且尚未测量）。切口干净 = 没有 busy 的非数据比特。
    """
    dset = set(layout.data)
    start_layer = layout.first_data_2q_layer
    if start_layer is None:
        return [], "no two-qubit gate ever touches a data qubit"
    status: dict[int, tuple[str, list[_Op]]] = {}
    by_layer: dict[int, list[_Op]] = {}
    for op in parsed.ops:
        by_layer.setdefault(op.layer, []).append(op)

    def update(op: _Op):
        anc = [q for q in op.qubits if q not in dset]
        for q in anc:
            st, rp = status.get(q, ("idle", []))
            if op.kind == "reset":
                status[q] = ("prepped", [op])
            elif op.kind == "measure_reset":
                status[q] = ("prepped", [_Op(op.layer, _RESET_OF[_RESET_BASIS[op.name]], "reset", (q,), ())])
            elif op.kind == "measure":
                status[q] = ("idle", [])
            elif op.kind == "1q":
                status[q] = (st, rp + [op]) if st == "prepped" else (st, rp)
            else:
                status[q] = ("busy", [])

    for layer in range(start_layer):
        for op in by_layer.get(layer, []):
            update(op)
    segs = []
    cur_ops: list[_Op] = []
    cur_lo = start_layer
    replay: list[_Op] = []

    def snapshot():
        return [o for st, rp in status.values() if st == "prepped" for o in rp]

    def is_clean():
        return all(st != "busy" for st, _ in status.values())

    if not is_clean():
        return [], f"some ancilla is still entangled at the start of layer {start_layer}"
    replay = snapshot()
    for layer in range(start_layer, parsed.num_layers):
        if layer > start_layer and is_clean():
            if any(o.meas for o in cur_ops):
                segs.append((cur_lo, layer, replay, cur_ops))
            cur_ops, cur_lo, replay = [], layer, snapshot()
        for op in by_layer.get(layer, []):
            if id(op) in layout.final_ops:
                continue
            cur_ops.append(op)
            update(op)
    if any(o.meas for o in cur_ops):
        if not is_clean():
            return [], "circuit ends with ancillas still entangled"
        segs.append((cur_lo, parsed.num_layers, replay, cur_ops))
    out = []
    for lo, hi, rp, ops in segs:
        c = stim.Circuit()
        local: list[int] = []
        for o in rp:
            c.append(o.name, list(o.qubits))
        for o in ops:
            if o.kind == "2q":
                c.append(o.name, list(o.qubits))
            elif o.kind == "other":
                return [], f"unsupported instruction {o.name} for segment analysis"
            else:
                c.append(o.name, list(o.qubits))
            local.extend(o.meas)
        if c.num_qubits < nq:
            c.append("I", [nq - 1])
        out.append((lo, hi, c, local))
    return out, None


def _check_coverage(parsed: _Parsed, code: CSSCode, basis: str, layout: _Layout, rounds: int | None,
                    require_opposite: bool, nq: int, method: str = "flows") -> tuple[CheckResult, CheckResult]:
    if method == "flows":
        return _check_coverage_flows(parsed, code, basis, layout, rounds, require_opposite, nq)
    if method != "segments":
        raise ValueError(f"unknown coverage_method {method!r} (use 'flows' or 'segments')")
    return _check_coverage_segments(parsed, code, basis, layout, rounds, require_opposite, nq)


# ---------------------------------------------------------------------------
# 覆盖检查（flow 方法，不切段；README §3.2）
# ---------------------------------------------------------------------------

def _lowbit(v: int) -> int:
    return (v & -v).bit_length() - 1


def _pauli_int(ps: stim.PauliString, nq: int) -> int:
    xs, zs = ps.to_numpy()
    arr = np.zeros(2 * nq, dtype=np.uint8)
    arr[0:2 * len(xs):2] = xs
    arr[1:2 * len(zs):2] = zs
    return int.from_bytes(np.packbits(arr, bitorder="little").tobytes(), "little")


def _int_bits(v: int) -> list[int]:
    out = []
    while v:
        b = _lowbit(v)
        out.append(b)
        v ^= 1 << b
    return out


class _MinSpanBasis:
    """GF(2) 子空间的“最小跨度”基（trellis 理论里的 MSGM）：所有基向量的最低位互不相同、最高位也互不相同。

    性质：任意非零组合 c 的最低位 = 所用基向量最低位的最小值，最高位 = 最高位的最大值（两端都不会被消掉）。
    所以“子空间里支撑落在区间 [a, b] 内的向量” = 跨度落在 [a, b] 内的基向量张成的子空间。
    phi 标记每个基向量是否含奇数个“额外向量”（用于陪集 M + D：phi=1 的向量属于陪集）。
    """

    def __init__(self) -> None:
        self.ends: dict[int, int] = {}   # 最高位 -> 向量
        self.phi: set[int] = set()       # phi=1 的向量的最高位

    def copy(self) -> "_MinSpanBasis":
        b = _MinSpanBasis()
        b.ends = dict(self.ends)
        b.phi = set(self.phi)
        return b

    def _put(self, e: int, v: int, p: int) -> None:
        self.ends[e] = v
        if p:
            self.phi.add(e)
        else:
            self.phi.discard(e)

    def insert_left_reduced(self, x: int, px: int) -> None:
        """插入一个最低位与现有基向量都不同的向量，按最高位去重（只改动最低位较小者，最低位保持不变）。"""
        while True:
            e = x.bit_length() - 1
            y = self.ends.get(e)
            if y is None:
                self._put(e, x, px)
                return
            py = 1 if e in self.phi else 0
            if _lowbit(x) < _lowbit(y):
                x ^= y
                px ^= py
            else:
                self._put(e, x, px)
                x, px = y ^ x, py ^ px

    def starts(self) -> dict[int, int]:
        return {_lowbit(v): v for v in self.ends.values()}

    @classmethod
    def from_vectors(cls, vecs: Iterable[int]) -> "_MinSpanBasis":
        starts: dict[int, int] = {}
        for v in vecs:
            while v:
                s = _lowbit(v)
                w = starts.get(s)
                if w is None:
                    starts[s] = v
                    break
                v ^= w
        b = cls()
        for v in starts.values():
            b.insert_left_reduced(v, 0)
        return b

    def with_coset(self, m: int) -> "_MinSpanBasis | None":
        """D + span{m} 的最小跨度基，phi=1 的基向量属于陪集 m + D。m ∈ D 时返回 None。"""
        st = self.starts()
        while m:
            w = st.get(_lowbit(m))
            if w is None:
                break
            m ^= w
        if not m:
            return None
        b = self.copy()
        b.insert_left_reduced(m, 1)
        return b


@dataclass
class _Body:
    circuit: stim.Circuit
    local_to_global: list[int]   # body 测量序号 -> 全局测量记录序号
    rec_layer: list[int]         # body 测量序号 -> 所在层


def _build_body(parsed: _Parsed, layout: _Layout, nq: int) -> tuple[_Body | None, str | None]:
    """去掉数据比特的制备（首个数据双比特门所在层之前作用在数据比特上的复位/单比特门）和最终读出后的电路。

    数据比特的输入因此是自由的；辅助比特的复位全部保留。
    """
    dset = set(layout.data)
    first = layout.first_data_2q_layer
    if first is None:
        return None, "no two-qubit gate ever touches a data qubit"
    c = stim.Circuit()
    l2g: list[int] = []
    rec_layer: list[int] = []
    layer = 0
    for op in parsed.ops:
        if id(op) in layout.final_ops:
            continue
        if op.layer < first and any(q in dset for q in op.qubits):
            continue
        if op.kind == "other":
            return None, f"unsupported instruction {op.name} (layer {op.layer}) for flow analysis"
        while layer < op.layer:
            c.append("TICK")
            layer += 1
        c.append(op.name, list(op.qubits))
        for m in op.meas:
            l2g.append(m)
            rec_layer.append(op.layer)
    if c.num_qubits < nq:
        c.append("I", [nq - 1])
    return _Body(c, l2g, rec_layer), None


def _check_coverage_flows(parsed: _Parsed, code: CSSCode, basis: str, layout: _Layout, rounds: int | None,
                          require_opposite: bool, nq: int) -> tuple[CheckResult, CheckResult]:
    """不依赖切段的覆盖检查（适用于辅助比特跨轮流水的电路）。

    1. body = 去掉数据制备和最终读出的电路（数据输入自由）。用 stim `flow_generators()` 求出全部 flow，
       在 GF(2) 上消元得到：D = 所有“输入输出都为恒等”的测量奇偶（与数据输入无关的确定奇偶），以及每个
       稳定子生成元 s 的一个特解 M_s（flow  s_in -> 1，即这组测量的奇偶 = 输入时刻 s 的值）。
       所有“测量了 s”的测量集合恰好是陪集 A_s = M_s + D。
    2. 计数：s 被测了 r 次 = 能找到 r 个时间上互不重叠的层区间，每个区间里都有 A_s 的一个元素
       （区间只限制“用哪些测量记录”，区间之前的门全部算在内，所以不需要干净切口）。
       用 D + span{M_s} 的最小跨度基求解：区间里有 A_s 的元素 ⇔ 有一个 phi=1 的基向量的跨度落在区间内，
       于是最大不相交区间数 = 区间调度的贪心解（按结束层排序）。
    3. detector 覆盖：取每个区间里选中的代表 c_1..c_r，要求首轮 c_1（basis 型）、相邻轮 c_j ⊕ c_{j+1}、
       末轮与读出 c_r ⊕ readout(s) 都在 detector 张成里，允许模掉“落在 s 的某一个区间之内的确定奇偶”
       （D 中跨度在单个区间内的部分，例如冗余行的 meta-check；它们不跨轮，不会让检查变成空话）。
    """
    body, why = _build_body(parsed, layout, nq)
    if body is None:
        r = CheckResult("stabilizer_coverage", "fail", f"cannot analyse the syndrome-extraction circuit: {why}")
        return r, CheckResult("detector_coverage", "skipped", "stabilizer coverage failed")
    Mb = len(body.local_to_global)
    P2 = 2 * nq
    # flow -> 位向量：低 Mb 位 = 测量；之上 2nq 位 = 输入 Pauli；再之上 2nq 位 = 输出 Pauli
    basis_vecs: dict[int, int] = {}
    for f in body.circuit.flow_generators():
        v = (_pauli_int(f.output_copy(), nq) << (Mb + P2)) | (_pauli_int(f.input_copy(), nq) << Mb)
        for m in f.measurements_copy():
            v ^= 1 << m
        while v:
            hb = v.bit_length() - 1
            w = basis_vecs.get(hb)
            if w is None:
                basis_vecs[hb] = v
                break
            v ^= w
    D = _MinSpanBasis.from_vectors(v for hb, v in basis_vecs.items() if hb < Mb)

    gens = [("X", i, code.HX[i]) for i in range(code.HX.shape[0])] + \
           [("Z", i, code.HZ[i]) for i in range(code.HZ.shape[0])]
    gens = [g for g in gens if g[2].any()]
    layer_of = body.rec_layer

    def span_layers(v: int) -> tuple[int, int]:
        return layer_of[_lowbit(v)], layer_of[v.bit_length() - 1]

    instances: list[list[tuple[int, int, int]]] = []   # 每个生成元：[(起始层, 结束层, 代表向量)]
    never: list[str] = []
    for typ, idx, row in gens:
        ps = stim.PauliString(nq)
        for c in np.flatnonzero(row):
            ps[layout.data[c]] = 1 if typ == "X" else 3
        x = _pauli_int(ps, nq) << Mb
        while x.bit_length() - 1 >= Mb:
            w = basis_vecs.get(x.bit_length() - 1)
            if w is None:
                break
            x ^= w
        if x.bit_length() - 1 >= Mb:
            instances.append([])   # 没有任何测量组合确定 s 的值
            continue
        Bs = D.with_coset(x)
        if Bs is None:
            never.append(f"{typ}-stabilizer #{idx}")
            instances.append([])
            continue
        cands = sorted((span_layers(Bs.ends[e]) + (Bs.ends[e],) for e in Bs.phi), key=lambda t: (t[1], t[0]))
        chosen: list[tuple[int, int, int]] = []
        last_end = -1
        for lo, hi, v in cands:
            if lo > last_end:
                chosen.append((lo, hi, v))
                last_end = hi
        instances.append(chosen)

    counts = [len(m) for m in instances]
    target = rounds if rounds is not None else (max(counts) if counts else 0)
    issues: list[str] = []
    if never:
        issues.append("internal: deterministic stabilizer measurement for " + _fmt_list(never, 4))
    if target < 1:
        issues.append("no stabilizer is ever measured")
    bad = []
    for gi, (typ, idx, row) in enumerate(gens):
        if counts[gi] != target:
            where = [hi for _, hi, _ in instances[gi]]
            bad.append(f"{typ}-stabilizer #{idx} (data cols {np.flatnonzero(row).tolist()}) measured "
                       f"{counts[gi]} time(s), required {target} (measurements completed in layers "
                       f"{where or 'none'})")
    if bad:
        issues.append(f"{len(bad)} stabilizer generator(s) not measured every round: " + "; ".join(bad[:6])
                      + (f"; ... (+{len(bad) - 6} more)" if len(bad) > 6 else ""))
    details = {"method": "flows", "counts": {f"{t}{i}": c for (t, i, _), c in zip(gens, counts)},
               "measurement_layers": {f"{t}{i}": [hi for _, hi, _ in inst]
                                      for (t, i, _), inst in zip(gens, instances)}}
    if issues:
        cov = CheckResult("stabilizer_coverage", "fail",
                          "; ".join(issues) + ". (A generator counts as measured once per time-disjoint window of "
                          "layers whose measurements determine its value; see README §3.2)", details)
        return cov, CheckResult("detector_coverage", "skipped", "stabilizer coverage failed")
    cov = CheckResult("stabilizer_coverage", "pass",
                      f"all {len(gens)} stabilizer generators measured exactly {target} time(s) in time-disjoint "
                      f"windows (flow analysis of the whole circuit, no clean cuts needed)", details)

    # ---- detector coverage
    l2g = body.local_to_global

    def to_global(v: int) -> int:
        out = 0
        for b in _int_bits(v):
            out ^= 1 << l2g[b]
        return out

    span = GF2Basis()
    for d in parsed.detectors:
        span.add(bits_to_int(d))
    D_rows = [(span_layers(v), v) for v in D.ends.values()]
    in_span_cache: dict[int, bool] = {}
    missing = []
    slack_vecs: set[int] = set()
    for gi, (typ, idx, row) in enumerate(gens):
        is_basis = typ == basis
        if not is_basis and not require_opposite:
            continue
        inst = instances[gi]
        bounds = []
        prev = -1
        for _, hi, _ in inst:
            bounds.append((prev, hi))   # 窗口 = (prev, hi]
            prev = hi
        local_span = span
        extra = []
        for (lo, hi), v in D_rows:
            if any(a < lo and hi <= b for a, b in bounds):
                key = v
                if key not in in_span_cache:
                    in_span_cache[key] = span.contains(to_global(v))
                if not in_span_cache[key]:
                    extra.append(to_global(v))
        if extra:
            local_span = GF2Basis()
            local_span._basis = dict(span._basis)
            for v in extra:
                if local_span.add(v):
                    slack_vecs.add(v)
        reps = [to_global(v) for _, _, v in inst]
        expect: list[tuple[str, int]] = []
        if is_basis:
            expect.append(("first round vs. preparation", reps[0]))
        for r in range(1, len(reps)):
            expect.append((f"round {r - 1} vs. round {r}", reps[r - 1] ^ reps[r]))
        if is_basis:
            fin = bits_to_int(layout.final_rec[layout.data[c]] for c in np.flatnonzero(row))
            expect.append(("last round vs. final data readout", reps[-1] ^ fin))
        for label, s in expect:
            if not local_span.contains(s):
                missing.append(f"{typ}-stabilizer #{idx} ({label})")
    if missing:
        det = CheckResult("detector_coverage", "fail",
                          f"{len(missing)} expected syndrome comparison(s) are not in the span of the declared "
                          f"detectors, so the decoder never sees them: " + _fmt_list(missing, 8),
                          {"missing": missing})
    else:
        det = CheckResult("detector_coverage", "pass",
                          f"all expected {basis}-type comparisons"
                          + (" and opposite-type comparisons" if require_opposite else "")
                          + f" lie in the span of the {len(parsed.detectors)} detectors"
                          + (f" (allowing {len(slack_vecs)} undeclared window-local deterministic parities such as "
                             f"meta-checks of redundant rows)" if slack_vecs else ""), {"slack": len(slack_vecs)})
    return cov, det


def _check_coverage_segments(parsed: _Parsed, code: CSSCode, basis: str, layout: _Layout, rounds: int | None,
                             require_opposite: bool, nq: int) -> tuple[CheckResult, CheckResult]:
    """旧方法（干净切口切段），只为对照保留：coverage_method="segments"。"""
    segs, why = _segments(parsed, layout, nq)
    if why is not None:
        r = CheckResult("stabilizer_coverage", "fail",
                        f"cannot split the circuit into syndrome-extraction segments: {why}. L0 requires clean "
                        f"cuts (no ancilla entangled) between rounds")
        return r, CheckResult("detector_coverage", "skipped", "stabilizer coverage failed")
    gens = [("X", i, code.HX[i]) for i in range(code.HX.shape[0])] + \
           [("Z", i, code.HZ[i]) for i in range(code.HZ.shape[0])]
    gens = [g for g in gens if g[2].any()]
    flows = []
    for typ, _, row in gens:
        ps = stim.PauliString(nq)
        for c in np.flatnonzero(row):
            ps[layout.data[c]] = 1 if typ == "X" else 3
        flows.append(stim.Flow(input=ps, output=stim.PauliString(nq)))
    measured: list[list[tuple[int, frozenset[int]]]] = [[] for _ in gens]
    destroyed: list[str] = []
    for si, (lo, hi, c, local) in enumerate(segs):
        sols = c.solve_flow_measurements(flows)
        for gi, sol in enumerate(sols):
            if sol is None:
                continue
            if len(sol) == 0:
                typ, idx, _ = gens[gi]
                destroyed.append(f"{typ}-stabilizer #{idx} is erased by a reset in layers {lo}-{hi - 1}")
                continue
            measured[gi].append((si, frozenset(local[x] for x in sol)))
    counts = [len(m) for m in measured]
    target = rounds if rounds is not None else (max(counts) if counts else 0)
    issues: list[str] = []
    if destroyed:
        issues.append(_fmt_list(destroyed, 4))
    if target < 1:
        issues.append("no stabilizer is ever measured")
    seg_desc = [f"S{i}=layers {lo}-{hi - 1}" for i, (lo, hi, _, _) in enumerate(segs)]
    bad = []
    for gi, (typ, idx, row) in enumerate(gens):
        if counts[gi] != target:
            where = [f"S{si}" for si, _ in measured[gi]]
            bad.append(f"{typ}-stabilizer #{idx} (data cols {np.flatnonzero(row).tolist()}) measured "
                       f"{counts[gi]} time(s), required {target} (measured in segments {where or 'none'})")
    if bad:
        issues.append(f"{len(bad)} stabilizer generator(s) not measured every round: " + "; ".join(bad[:6])
                      + (f"; ... (+{len(bad) - 6} more)" if len(bad) > 6 else ""))
    details = {"segments": seg_desc, "counts": {f"{t}{i}": c for (t, i, _), c in zip(gens, counts)}}
    if issues:
        cov = CheckResult("stabilizer_coverage", "fail",
                          "; ".join(issues) + f". Segments between clean cuts: {_fmt_list(seg_desc, 8)}", details)
        return cov, CheckResult("detector_coverage", "skipped", "stabilizer coverage failed")
    cov = CheckResult("stabilizer_coverage", "pass",
                      f"all {len(gens)} stabilizer generators measured exactly {target} time(s) "
                      f"({len(segs)} segments)", details)

    # detector coverage
    span = GF2Basis()
    for d in parsed.detectors:
        span.add(bits_to_int(d))
    # solve_flow_measurements 的解不唯一：可以相差一个“段内确定的测量组合”（例如冗余稳定子行的
    # meta-check：BB 码 HX 有 72 行、秩 66）。这些组合不要求声明为 detector，所以在比较时模掉它们。
    slack = 0
    for lo, hi, c, local in segs:
        for f in c.flow_generators():
            if f.input_copy().weight == 0 and f.output_copy().weight == 0 and f.measurements_copy():
                if span.add(bits_to_int(local[x] for x in f.measurements_copy())):
                    slack += 1
    missing = []
    for gi, (typ, idx, row) in enumerate(gens):
        is_basis = typ == basis
        if not is_basis and not require_opposite:
            continue
        ms = [m for _, m in measured[gi]]
        expect: list[tuple[str, frozenset[int]]] = []
        if is_basis:
            expect.append(("first round vs. preparation", ms[0]))
        for r in range(1, len(ms)):
            expect.append((f"round {r - 1} vs. round {r}", ms[r - 1] ^ ms[r]))
        if is_basis:
            fin = frozenset(layout.final_rec[layout.data[c]] for c in np.flatnonzero(row))
            expect.append(("last round vs. final data readout", ms[-1] ^ fin))
        for label, s in expect:
            if not span.contains(bits_to_int(s)):
                missing.append(f"{typ}-stabilizer #{idx} ({label})")
    if missing:
        det = CheckResult("detector_coverage", "fail",
                          f"{len(missing)} expected syndrome comparison(s) are not in the span of the declared "
                          f"detectors, so the decoder never sees them: " + _fmt_list(missing, 8),
                          {"missing": missing})
    else:
        det = CheckResult("detector_coverage", "pass",
                          f"all expected {basis}-type comparisons"
                          + (" and opposite-type comparisons" if require_opposite else "")
                          + f" lie in the span of the {len(parsed.detectors)} detectors"
                          + (f" (modulo {slack} segment-local deterministic parities such as meta-checks)"
                             if slack else ""), {"slack": slack})
    return cov, det


# ---------------------------------------------------------------------------
# 电路级距离
# ---------------------------------------------------------------------------

def _distance_kwargs(cons: L0Constraints) -> dict:
    methods = [m for m in cons.distance_methods if cons.use_graphlike_bound or m != "graphlike"]
    stop = cons.min_circuit_distance if (cons.distance_early_stop and cons.min_circuit_distance is not None) else None
    return dict(seed=cons.distance_seed, methods=methods,
                stim_search_size=cons.dont_explore_detection_event_sets_with_size_above,
                stim_search_degree=cons.dont_explore_edges_with_degree_above,
                stim_search_increasing=cons.dont_explore_edges_increasing_symptom_degree,
                bposd_trials=cons.distance_bposd_trials, lns_starts=cons.distance_lns_starts,
                lns_det_time=cons.distance_lns_det_time, num_workers=cons.distance_num_workers,
                stop_below=stop)


def _check_distance(circuit: stim.Circuit, cons: L0Constraints) -> tuple[CheckResult, int | None]:
    try:
        noisy = add_noise(circuit, cons.distance_noise_model, cons.distance_noise_p, idle=cons.distance_noise_idle)
        noisy.detector_error_model(allow_gauge_detectors=False)
    except Exception as e:  # noqa: BLE001
        return CheckResult("circuit_distance", "fail", f"could not build noisy DEM: {e}"), None
    kwargs = _distance_kwargs(cons)
    t0 = time.time()
    try:
        if cons.distance_timeout_s is None:
            res = distance.upper_bound(noisy, **kwargs)
        else:
            res = distance.DistanceResult.from_dict(distance.run_in_subprocess(
                "evaluators.distance", "upper_bound_json", {"circuit": str(noisy), "kwargs": kwargs},
                cons.distance_timeout_s))
    except subprocess.TimeoutExpired:
        return CheckResult("circuit_distance", "fail",
                           f"distance search did not finish within {cons.distance_timeout_s}s; cannot certify "
                           f"d_circ >= {cons.min_circuit_distance}"), None
    except Exception as e:  # noqa: BLE001
        return CheckResult("circuit_distance", "fail", f"distance search failed: {e}"), None
    noise_desc = f"{cons.distance_noise_model}(p={cons.distance_noise_p}, idle={cons.distance_noise_idle})"
    detail = {**res.to_dict(), "wall_seconds": round(time.time() - t0, 3), "noise": noise_desc}
    rejected = [m for m in res.methods if m.status == "rejected"]
    rej = ("; WARNING: unverified witnesses discarded: "
           + ", ".join(f"{m.method} (weight {m.extra.get('unverified_weight')})" for m in rejected)) if rejected else ""
    if res.weight is None:
        return CheckResult("circuit_distance", "fail",
                           f"no method found an injection-verified undetectable logical error under {noise_desc} "
                           f"({res.summary()}); cannot bound d_circ" + rej, detail), None
    d = res.weight
    w = res.witness
    early = (" (search stopped as soon as a witness below the threshold was found)"
             if res.stopped_early and cons.min_circuit_distance is not None and d < cons.min_circuit_distance else "")
    msg = (f"d_circ upper bound = {d} under {noise_desc} [{res.summary()}]{early}; shortest undetectable logical "
           f"error (weight {d}, found by {w.method}, injection-verified: 0 detectors fire, observables "
           f"{w.flipped_observables} flip): " + "; ".join(w.describe(limit=24)) + rej)
    if cons.min_circuit_distance is not None and d < cons.min_circuit_distance:
        return CheckResult("circuit_distance", "fail",
                           f"circuit-level distance too low (< {cons.min_circuit_distance}): " + msg, detail), d
    return CheckResult("circuit_distance", "pass",
                       msg + " (this is an upper bound from heuristic search, not a proof of d_circ)", detail), d


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def check_l0(circuit, code: CSSCode, basis: str, constraints: L0Constraints | None = None) -> L0Report:
    """对无噪声候选 memory 电路做 L0 合法性检查。

    Args:
        circuit: basis 为 "Z"/"X" 时是一条 stim.Circuit；basis="both"（推荐，评估器默认口径）时是
            {"Z": z_memory_circuit, "X": x_memory_circuit}。两个基底都必须通过，d_circ 取较小值。
        code: CSSCode。
        basis: "Z" | "X" | "both"。
        constraints: L0Constraints（由评估任务给定）。
    """
    if basis == "both":
        if not isinstance(circuit, Mapping) or set(circuit) != {"X", "Z"}:
            raise ValueError('basis="both" requires circuit={"Z": stim.Circuit, "X": stim.Circuit}')
        t0 = time.time()
        subs = {b: _check_l0_single(circuit[b], code, b, constraints) for b in ("Z", "X")}
        checks = [CheckResult(f"{b}:{c.name}", c.status, c.message, c.details)
                  for b, r in subs.items() for c in r.checks]
        ds = [r.d_circ for r in subs.values()]
        d = min(ds) if all(x is not None for x in ds) else None
        return L0Report(all(r.passed for r in subs.values()), checks, d, round(time.time() - t0, 3), "both", subs)
    if basis not in ("X", "Z"):
        raise ValueError("basis must be 'X', 'Z' or 'both'")
    return _check_l0_single(circuit, code, basis, constraints)


def _check_l0_single(circuit: stim.Circuit, code: CSSCode, basis: str,
                     constraints: L0Constraints | None) -> L0Report:
    t0 = time.time()
    cons = constraints or L0Constraints()
    data = list(cons.data_qubits) if cons.data_qubits is not None else list(range(code.n))
    if len(data) != code.n or len(set(data)) != code.n:
        raise ValueError(f"constraints.data_qubits must list {code.n} distinct qubits")
    allowed = frozenset(cons.allowed_gates)
    edges = None if cons.allowed_edges is None else {frozenset(e) for e in cons.allowed_edges}
    expected_obs = cons.num_observables if cons.num_observables is not None else code.k

    checks: list[CheckResult] = []

    def finish(d=None):
        passed = bool(checks) and all(c.status != "fail" for c in checks)
        return L0Report(passed, checks, d, round(time.time() - t0, 3), basis)

    size = _flat_size(circuit, cons.max_flat_instructions)
    if size > cons.max_flat_instructions:
        checks.append(CheckResult("instructions", "fail",
                                  f"circuit too large: > {cons.max_flat_instructions} instructions after expanding "
                                  f"REPEAT blocks"))
        return finish()
    flat = circuit.flattened()

    checks.append(_check_instructions(flat, allowed))
    checks.append(_check_qubit_count(circuit, cons.max_qubits))
    if max(data) >= circuit.num_qubits:
        checks.append(CheckResult("data_layout", "fail",
                                  f"data qubit {max(data)} does not exist in the circuit "
                                  f"({circuit.num_qubits} qubits)"))
        return finish()
    parsed = _parse(flat)
    checks.append(_check_connectivity(parsed, edges))
    checks.append(_check_ticks(parsed))
    semantic = ["determinism", "data_layout", "observables", "logical_injection", "stabilizer_coverage",
                "detector_coverage", "circuit_distance"]
    if not all(c.passed for c in checks):
        for n in semantic:
            checks.append(CheckResult(n, "skipped", "syntactic checks failed"))
        return finish()

    det = _check_determinism(circuit)
    checks.append(det)
    lay_res, layout = _check_data_layout(parsed, data, basis)
    checks.append(lay_res)
    if layout is None:
        for n in semantic[2:]:
            checks.append(CheckResult(n, "skipped", "data layout check failed"))
        return finish()
    checks.append(_check_observables(parsed, code, basis, layout, expected_obs))
    if det.passed:
        checks.append(_check_logical_injection(circuit, code, basis, layout, expected_obs))
    else:
        checks.append(CheckResult("logical_injection", "skipped", "requires deterministic detectors"))
    cov, dcov = _check_coverage(parsed, code, basis, layout, cons.rounds, cons.require_opposite_type_detectors,
                                circuit.num_qubits, cons.coverage_method)
    checks.extend([cov, dcov])

    d = None
    if cons.min_circuit_distance is None and not cons.compute_distance:
        checks.append(CheckResult("circuit_distance", "skipped", "no minimum distance configured"))
    elif not all(c.passed for c in checks):
        checks.append(CheckResult("circuit_distance", "skipped", "earlier checks failed"))
    else:
        res, d = _check_distance(circuit, cons)
        checks.append(res)
    return finish(d)
