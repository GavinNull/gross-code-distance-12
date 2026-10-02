"""L2：逻辑错误率采样（X/Z 联合采样，sinter 多进程，显式种子，结果可逐位复现）。

公开入口：
    sample_l2(code, circuits, data_qubits, *, p, rounds, noise_model="sd6", boundary="paper",
              decoder=DecoderConfig(), seed=..., stop=StopRule(...), num_workers=4) -> L2Result
    build_joint_circuit(...) -> JointCircuit          （测试 / 诊断用）

## X/Z 联合采样的做法（对任意 CSS 码 + 任意调度）

输入是同一调度的两条**无噪声** memory 电路（Z 基底、X 基底，L0 的约定：数据比特显式复位 → 若干轮
syndrome 提取 → 数据比特在 basis 基下测量；observable 只由最终数据读出构成）。评估器把它们合成一条
“联合电路”，在同一批 shot 里同时得到两个 sector 的 detector 和 observable：

  1. 两条电路去掉数据比特的制备（首个双比特门之前的所有操作）和最终读出后，剩下的“主体”必须完全相同
     （逐层比较，层内顺序无关），否则报错——联合采样只对“两个基底只差边界”的电路成立。
  2. 主体按噪声模型加噪声（`noise.add_noise`，先对整条电路加，再切掉数据比特边界上的噪声）。
  3. 增加 k 个无噪声的参考比特 r_j。用 stim.Tableau.from_stabilizers 生成无噪声编码电路，把
     数据 + 参考比特制备成如下生成元全部为 +1 的态：HZ 的独立行、HX 的独立行、LZ_j⊗Z_{r_j}、
     LX_j⊗X_{r_j}（共 n−k+2k = n+k 个）。也就是完美码态，且每个逻辑比特与一个参考比特构成 Bell 对，
     因此 Z 型与 X 型逻辑算符（乘上参考比特）同时是确定的。
  4. 末尾对上述 n+k 个生成元做无噪声 MPP（“完美读出”）。候选电路里引用了数据读出记录的
     detector / observable，其数据部分是一个 Z 型（Z 电路）或 X 型（X 电路）Pauli，在 GF(2) 上
     展开成生成元的乘积，用对应的 MPP 记录代替。其余记录（辅助比特测量）按 (层, 比特) 映射到主体。
  5. 联合电路的 detector = Z 电路的全部 detector（sector Z，坐标 (0,)）+ X 电路的全部 detector
     （sector X，坐标 (1,)）；observable = Z 电路的 k 个 + X 电路的 k 个。
  6. 解码：把联合 DEM 的每个错误机制限制到各自 sector（Y 型故障同时出现在两个 sector，限制后各算一次，
     同 IBM / E-002 的“X、Z 分开译码”），合并相同症状后分别建 BP-OSD（或 pymatching）解码器。
     一个 shot 中 Z sector 任一 observable 预测错 = Z 失败，X 同理；P_any = 任一 sector 失败。

这是**精确的联合采样**：每个物理故障在一个 shot 里只抽一次，同时作用于两个 sector，
所以 X/Z 失败的相关性被如实保留（auditor E-002 M1）。不存在独立近似；结果里另附
`P_indep_approx = 1-(1-P_Z)(1-P_X)` 仅作对照，并标注 "reference only"。

## 边界口径 boundary
  - "paper"（默认）：完美初态（码态）+ 主体全部轮次带噪声 + 完美读出（等价于论文的“无噪声收尾 cycle”
    + 无噪声读出，arXiv:2308.07915 §6）。数据比特在其制备结束（含）之前、最终读出所在层（含）之后的
    所有噪声都被去掉；辅助比特的噪声一律保留（包括第一轮之前预先复位的辅助比特）。用于与文献比较。
  - "noisy"：数据比特的制备与读出带噪声。Z sector 的边缘分布与“带噪声的 Z memory 电路”完全相同，
    X sector 同理（测试逐机制比对 DEM）：联合电路里同时加上 Z 电路的复位后翻转 / 读出前翻转
    （X_ERROR）与 X 电路的（Z_ERROR）。这是项目内部口径（E-002 的边界），只能在同一管线内比较候选，
    不可直接与论文数字比较。要求每个数据比特的制备恰好是一个 basis 基复位（Z: R，X: RX）。

## 随机性与可复现性
  sinter 本身不接受种子：它的默认采样器调用 `circuit.compile_detector_sampler()`（系统熵），
  批大小随耗时自适应，所以“sinter 默认用法”不可复现（E-001 auditor M3）。这里用自定义
  `sinter.Sampler`：
    - 批大小固定为 `stop.batch_size`，忽略 sinter 建议的 shot 数，并关闭 sinter 的 ramp 节流；
    - 批编号 b 由一个加文件锁的计数器分配，第 b 批用 stim 种子 SeedSequence([seed, b]) 采样；
    - 每批的结果（含逐 shot 的失败位）写成一个文件；
    - sinter 返回后，按批编号从 0 起取**最短的、满足停止规则的前缀**作为正式结果，前缀里缺的批
      （例如 sinter 停止时被丢弃的在途批）在主进程里按同一种子补算。
  因此正式结果只取决于 (电路, 噪声, 解码器参数, seed, batch_size, 停止规则) 和库版本，
  与 num_workers、进程调度、耗时无关。限制：stim 文档说明同一种子在不同 stim 版本或不同 SIMD
  宽度的机器上可能给出不同样本，所以“逐位可复现”只在同一 stim 版本 + 同类 CPU 上成立；
  BP-OSD（parallel schedule、osd_cs）与 pymatching 是确定性的。
"""
from __future__ import annotations

import collections
import dataclasses
import fcntl
import hashlib
import json
import math
import os
import platform
import shutil
import tempfile
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import stim

from evaluators.codes import CSSCode, GF2Basis, bits_to_int, solve_left
from evaluators.noise import DEFAULT_MODEL, NOISE_MODELS, add_noise
from evaluators.stats import (
    DEFAULT_LIKELIHOOD_FACTOR,
    MIN_LOGICAL_ERRORS_FOR_COMPARISON,
    binomial_interval,
)

__all__ = [
    "BOUNDARIES",
    "DEFAULT_BOUNDARY",
    "IBM_BPOSD_PARAMS",
    "DecoderConfig",
    "JointCircuit",
    "L2Result",
    "StopRule",
    "build_joint_circuit",
    "circuit_hash",
    "library_versions",
    "per_round",
    "sample_l2",
]

BOUNDARIES = ("paper", "noisy")
DEFAULT_BOUNDARY = "paper"

# E-002 / IBM 仓库 decoder_run.py 的设置（arXiv:2308.07915 代码）。ms_scaling_factor=0 在 ldpc 2.x 里是
# 自适应缩放 alpha_t = 1-2^-t（auditor E-002 §3 经验确认），不是字面上的 0。
IBM_BPOSD_PARAMS = dict(max_iter=10000, bp_method="min_sum", ms_scaling_factor=0.0,
                        osd_method="osd_cs", osd_order=7, schedule="parallel")

PER_ROUND_FORMULA = "1-(1-P)^(1/rounds)  (arXiv:2308.07915 Sec. 3)"
PER_ROUND_SINTER_FORMULA = "(1-(1-2P)^(1/rounds))/2  (sinter.shot_error_rate_to_piece_error_rate; meaningful only for a single observable, do not use for k>1)"


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DecoderConfig:
    """name: "bposd"（ldpc.BpOsdDecoder，每个 sector 一个）或 "pymatching"（只适用于每个 sector
    的 DEM 都是 graphlike 的码，例如表面码）。params 覆盖默认参数。"""
    name: str = "bposd"
    params: Mapping = field(default_factory=dict)

    def resolved_params(self) -> dict:
        if self.name == "bposd":
            out = dict(IBM_BPOSD_PARAMS)
            out.update(self.params)
            return out
        if self.name == "pymatching":
            return dict(self.params)
        raise ValueError(f"unknown decoder {self.name!r}; known: 'bposd', 'pymatching'")


@dataclass(frozen=True)
class StopRule:
    """停止规则（作用于按批编号排列的前缀，见模块说明）。

    满足任一即停：
      - shots >= max_shots；
      - P_any 的失败数 >= max_errors（None = 不用），且（若给出）Z、X 两个 sector 的失败数都
        >= min_sector_errors。
    batch_size：每批 shot 数（固定；改变它会改变样本）。
    """
    max_shots: int
    max_errors: int | None = None
    min_sector_errors: int | None = None
    batch_size: int = 256

    def __post_init__(self):
        if self.max_shots <= 0 or self.batch_size <= 0:
            raise ValueError("max_shots and batch_size must be positive")

    def satisfied(self, shots: int, fail_any: int, fail_z: int, fail_x: int) -> bool:
        if shots >= self.max_shots:
            return True
        if self.max_errors is None:
            return False
        if fail_any < self.max_errors:
            return False
        if self.min_sector_errors is not None and min(fail_z, fail_x) < self.min_sector_errors:
            return False
        return True


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------

def library_versions() -> dict:
    import importlib.metadata as md
    out = {"python": platform.python_version(), "platform": platform.platform(),
           "machine": platform.machine()}
    for pkg in ("stim", "sinter", "ldpc", "pymatching", "numpy", "scipy"):
        try:
            out[pkg] = md.version(pkg)
        except md.PackageNotFoundError:
            out[pkg] = None
    return out


def circuit_hash(circuits: Mapping[str, stim.Circuit]) -> str:
    """无噪声候选电路（按基底排序）的 sha256，作为“调度哈希”。"""
    h = hashlib.sha256()
    for b in sorted(circuits):
        h.update(f"basis={b}\n".encode())
        h.update(str(circuits[b].flattened()).encode())
        h.update(b"\n")
    return h.hexdigest()


def per_round(P: float, rounds: int) -> float:
    """每轮逻辑错误率 1-(1-P)^(1/rounds)（论文 §3 的定义；P 为 rounds 轮的失败概率）。"""
    if not 0 <= P <= 1:
        raise ValueError(P)
    return 1 - (1 - P) ** (1 / rounds)


def _per_round_sinter(P: float, rounds: int) -> float | None:
    if P >= 0.5:
        return None
    return (1 - (1 - 2 * P) ** (1 / rounds)) / 2


_MEAS_NAMES = {"M": "Z", "MZ": "Z", "MX": "X", "MY": "Y", "MR": "Z", "MRZ": "Z", "MRX": "X", "MRY": "Y"}


def _is_noise(name: str) -> bool:
    gd = stim.gate_data(name)
    return gd.is_noisy_gate and not gd.produces_measurements


def _layers_with_records(circuit: stim.Circuit):
    """展开并按 TICK 分层。返回 [(layer, inst, first_record_index)]，first_record_index 是该指令产生的
    第一个测量记录的绝对编号（不产生测量则为当前计数）。"""
    out = []
    layer = 0
    rec = 0
    for inst in circuit.flattened():
        if inst.name == "TICK":
            layer += 1
            continue
        out.append((layer, inst, rec))
        rec += _num_records(inst)
    return out, rec


def _num_records(inst: stim.CircuitInstruction) -> int:
    gd = stim.gate_data(inst.name)
    if not gd.produces_measurements:
        return 0
    if inst.name == "MPP" or gd.is_two_qubit_gate:
        return len(inst.target_groups())
    return len(inst.targets_copy())


# ---------------------------------------------------------------------------
# 电路解析：数据比特边界
# ---------------------------------------------------------------------------

@dataclass
class _Parsed:
    basis: str
    prep_end: dict[int, int]          # 数据比特 -> 制备结束所在层
    prep_ops: dict[int, list[str]]    # 数据比特 -> 制备操作名
    readout_layer: dict[int, int]     # 数据比特 -> 最终读出所在层
    readout_rec: dict[int, int]       # 最终读出记录绝对编号 -> 数据列 j
    rec_key: dict[int, tuple[int, int]]   # 其他测量记录 -> (层, 比特)
    detectors: list[list[int]]        # 每个 detector 的绝对记录编号
    observables: dict[int, list[int]]
    num_layers: int


def _parse_memory(circuit: stim.Circuit, basis: str, data_qubits: list[int]) -> _Parsed:
    items, total = _layers_with_records(circuit)
    data = {q: j for j, q in enumerate(data_qubits)}
    ops: dict[int, list[tuple[int, str, int]]] = {q: [] for q in data}   # (layer, name, item idx)
    detectors: list[list[int]] = []
    observables: dict[int, list[int]] = collections.defaultdict(list)
    rec_owner: dict[int, tuple[int, int]] = {}
    for idx, (layer, inst, rec0) in enumerate(items):
        name = inst.name
        if name == "DETECTOR" or name == "OBSERVABLE_INCLUDE":
            recs = []
            for t in inst.targets_copy():
                if not t.is_measurement_record_target:
                    raise ValueError(f"{basis}: {name} with non-record target {t} is not supported")
                recs.append(rec0 + t.value)
            if name == "DETECTOR":
                detectors.append(recs)
            else:
                observables[int(inst.gate_args_copy()[0])].extend(recs)
            continue
        if name in ("QUBIT_COORDS", "SHIFT_COORDS"):
            continue
        if _is_noise(name):
            raise ValueError(f"{basis}: candidate circuit must be noiseless, found {inst}")
        gd = stim.gate_data(name)
        if gd.produces_measurements:
            if name not in _MEAS_NAMES:
                raise NotImplementedError(f"{basis}: measurement {name} not supported by L2")
            if any(a != 0 for a in inst.gate_args_copy()):
                raise ValueError(f"{basis}: noisy measurement {inst}")
            for i, t in enumerate(inst.targets_copy()):
                rec_owner[rec0 + i] = (layer, t.value)
        for t in inst.targets_copy():
            if t.is_measurement_record_target or t.is_sweep_bit_target:
                raise NotImplementedError(f"{basis}: classical control not supported: {inst}")
            if t.is_qubit_target and t.value in data:
                ops[t.value].append((layer, name, idx))
    prep_end, prep_ops, readout_layer, readout_rec = {}, {}, {}, {}
    want_meas = "M" if basis == "Z" else "MX"
    for q, lst in ops.items():
        if not lst:
            raise ValueError(f"{basis}: data qubit {q} is never used")
        two_q = [i for i, (_, nm, _) in enumerate(lst) if stim.gate_data(nm).is_two_qubit_gate]
        if not two_q:
            raise ValueError(f"{basis}: data qubit {q} takes part in no two-qubit gate")
        first2, last2 = two_q[0], two_q[-1]
        if first2 == 0 or not stim.gate_data(lst[0][1]).is_reset:
            raise ValueError(f"{basis}: data qubit {q} must start with an explicit reset (got {lst[0][1]})")
        for _, nm, _ in lst[:first2]:
            gd = stim.gate_data(nm)
            if gd.produces_measurements or not (gd.is_reset or gd.is_unitary):
                raise ValueError(f"{basis}: data qubit {q}: only resets and unitaries allowed before the first "
                                 f"two-qubit gate, got {nm}")
        prep_end[q] = lst[first2 - 1][0]
        prep_ops[q] = [nm for _, nm, _ in lst[:first2]]
        tail = lst[last2 + 1:]
        if len(tail) != 1 or tail[0][1] != want_meas:
            raise ValueError(f"{basis}: data qubit {q}: after its last two-qubit gate there must be exactly one "
                             f"{want_meas} (final readout), got {[nm for _, nm, _ in tail]}")
        mid_meas = [nm for _, nm, _ in lst[first2:last2] if stim.gate_data(nm).produces_measurements
                    or stim.gate_data(nm).is_reset]
        if mid_meas:
            raise ValueError(f"{basis}: data qubit {q} is measured/reset mid-circuit ({mid_meas}); "
                             f"not supported by joint sampling")
        readout_layer[q] = tail[0][0]
    # 最终读出记录
    for r, (layer, q) in list(rec_owner.items()):
        if q in data and layer == readout_layer[q]:
            readout_rec[r] = data[q]
            del rec_owner[r]
    for r, (layer, q) in rec_owner.items():
        if q in data:
            raise ValueError(f"{basis}: unexpected data measurement record {r}")
    return _Parsed(basis, prep_end, prep_ops, readout_layer, readout_rec, rec_owner, detectors,
                   dict(observables), num_layers=(items[-1][0] + 1 if items else 1))


def _is_boundary(parsed: _Parsed, layer: int, q: int) -> bool:
    return q in parsed.prep_end and (layer <= parsed.prep_end[q] or layer >= parsed.readout_layer[q])


def _canonical_body(circuit: stim.Circuit, parsed: _Parsed) -> list[tuple]:
    """无噪声主体的规范形式：每层的 (指令名, 参数, 目标组) 排序列表。去掉数据比特的边界操作与注释。"""
    items, _ = _layers_with_records(circuit)
    layers: dict[int, list] = collections.defaultdict(list)
    for layer, inst, _ in items:
        if inst.name in ("DETECTOR", "OBSERVABLE_INCLUDE", "QUBIT_COORDS", "SHIFT_COORDS"):
            continue
        args = tuple(inst.gate_args_copy())
        for grp in inst.target_groups():
            qs = tuple(t.value for t in grp)
            if any(_is_boundary(parsed, layer, q) for q in qs):
                if len(qs) > 1:
                    raise ValueError(f"multi-qubit operation {inst.name} {qs} touches a data qubit at its boundary")
                continue
            layers[layer].append((inst.name, args, qs))
    return [(k, tuple(sorted(v))) for k, v in sorted(layers.items()) if v]


# ---------------------------------------------------------------------------
# 联合电路
# ---------------------------------------------------------------------------

@dataclass
class JointCircuit:
    circuit: stim.Circuit
    num_detectors_z: int
    num_detectors_x: int
    num_observables_z: int
    num_observables_x: int
    boundary: str
    noise_model: str
    p: float
    ref_qubits: list[int]
    info: dict

    @property
    def sector_split(self) -> tuple[int, int]:
        return self.num_detectors_z, self.num_observables_z


def _independent_rows(H: np.ndarray) -> np.ndarray:
    basis = GF2Basis()
    keep = [i for i in range(H.shape[0]) if basis.add(bits_to_int(np.flatnonzero(H[i])))]
    return H[keep]


def _remap_circuit(c: stim.Circuit, qmap: list[int]) -> stim.Circuit:
    out = stim.Circuit()
    for inst in c.flattened():
        tg = []
        for t in inst.targets_copy():
            if t.is_qubit_target:
                tg.append(qmap[t.value])
            else:
                raise ValueError(f"unexpected target in encoder: {inst}")
        out.append(inst.name, tg, inst.gate_args_copy())
    return out


def build_joint_circuit(code: CSSCode, circuits: Mapping[str, stim.Circuit], data_qubits,
                        *, noise_model: str = DEFAULT_MODEL, p: float, boundary: str = DEFAULT_BOUNDARY,
                        noise_kwargs: Mapping | None = None) -> JointCircuit:
    """把两条无噪声 memory 电路合成为一条带噪声的联合电路（见模块说明）。"""
    if boundary not in BOUNDARIES:
        raise ValueError(f"boundary must be one of {BOUNDARIES}, got {boundary!r}")
    if noise_model not in NOISE_MODELS:
        raise ValueError(f"unknown noise model {noise_model!r}")
    if set(circuits) != {"Z", "X"}:
        raise ValueError("circuits must be {'Z': circ_z, 'X': circ_x}")
    data_qubits = [int(q) for q in data_qubits]
    n, k = code.n, code.k
    if len(data_qubits) != n or len(set(data_qubits)) != n:
        raise ValueError(f"data_qubits must list {n} distinct qubits")
    noise_kwargs = dict(noise_kwargs or {})

    parsed = {b: _parse_memory(circuits[b], b, data_qubits) for b in "ZX"}
    if _canonical_body(circuits["Z"], parsed["Z"]) != _canonical_body(circuits["X"], parsed["X"]):
        raise ValueError("the Z- and X-basis circuits differ outside the data-qubit preparation/readout; "
                         "joint X/Z sampling needs identical syndrome-extraction bodies")
    for q in data_qubits:
        if (parsed["Z"].prep_end[q] != parsed["X"].prep_end[q]
                or parsed["Z"].readout_layer[q] != parsed["X"].readout_layer[q]):
            raise ValueError(f"data qubit {q}: preparation/readout layers differ between bases")
    if boundary == "noisy":
        for b, want in (("Z", "R"), ("X", "RX")):
            for q in data_qubits:
                if parsed[b].prep_ops[q] != [want]:
                    raise ValueError(f"boundary='noisy' requires each data qubit's preparation to be a single "
                                     f"{want} in the {b} circuit; qubit {q} has {parsed[b].prep_ops[q]}")

    noisy = {b: add_noise(circuits[b], noise_model, p, **noise_kwargs) for b in "ZX"}
    pz = parsed["Z"]

    # ---- 主体（来自带噪声的 Z 电路）+ 边界噪声
    body = stim.Circuit()
    body_rec: dict[tuple[int, int], int] = {}
    nrec = 0
    boundary_noise: dict[str, list[tuple[str, int, float]]] = {"init": [], "readout": []}
    stripped = 0
    items, _ = _layers_with_records(noisy["Z"])
    cur_layer = 0
    for layer, inst, _ in items:
        while cur_layer < layer:
            body.append("TICK")
            cur_layer += 1
        name = inst.name
        if name in ("DETECTOR", "OBSERVABLE_INCLUDE", "QUBIT_COORDS", "SHIFT_COORDS"):
            continue
        args = inst.gate_args_copy()
        keep = []
        for grp in inst.target_groups():
            qs = [t.value for t in grp]
            bnd = [q for q in qs if _is_boundary(pz, layer, q)]
            if not bnd:
                keep.extend(grp)
                continue
            if len(qs) > 1:
                raise ValueError(f"multi-qubit {name} {qs} on a data qubit at its boundary (layer {layer})")
            stripped += 1
        if not keep:
            continue
        gd = stim.gate_data(name)
        if gd.produces_measurements:
            for i, t in enumerate(keep):
                body_rec[(layer, t.value)] = nrec + i
            nrec += len(keep)
        body.append(name, keep, args)
    num_body_layers = cur_layer + 1

    if boundary == "noisy":
        for b in "ZX":
            pb = parsed[b]
            its, _ = _layers_with_records(noisy[b])
            seen_reset: set[int] = set()
            for layer, inst, _ in its:
                name = inst.name
                if name in ("DETECTOR", "OBSERVABLE_INCLUDE", "QUBIT_COORDS", "SHIFT_COORDS", "TICK"):
                    continue
                gd = stim.gate_data(name)
                for grp in inst.target_groups():
                    qs = [t.value for t in grp]
                    if len(qs) != 1 or qs[0] not in pb.prep_end:
                        continue
                    q = qs[0]
                    if layer == pb.prep_end[q]:
                        if gd.is_reset:
                            seen_reset.add(q)
                        elif _is_noise(name) and q in seen_reset:
                            boundary_noise["init"].append((name, q, inst.gate_args_copy()))
                    elif layer == pb.readout_layer[q]:
                        if _is_noise(name):
                            boundary_noise["readout"].append((name, q, inst.gate_args_copy()))
                        elif gd.produces_measurements and inst.gate_args_copy() and inst.gate_args_copy()[0] > 0:
                            ch = "X_ERROR" if b == "Z" else "Z_ERROR"   # 记录翻转 == 测量前翻转（最终读出）
                            boundary_noise["readout"].append((ch, q, [inst.gate_args_copy()[0]]))
                    # 其余层（制备之前 / 读出之后）的噪声对 DEM 无影响

    # ---- 生成元
    HZi, HXi = _independent_rows(code.HZ), _independent_rows(code.HX)
    rz, rx = HZi.shape[0], HXi.shape[0]
    if rz + rx + k != n:
        raise ValueError("inconsistent code dimension")
    max_q = max([circuits[b].num_qubits for b in "ZX"]) - 1
    refs = [max_q + 1 + j for j in range(k)]
    nloc = n + k
    gens: list[stim.PauliString] = []
    gen_meta: list[tuple[str, np.ndarray, int | None]] = []   # (type, data row, ref index)
    for row in HZi:
        gens.append(_pauli("Z", row, None, nloc, n)); gen_meta.append(("Z", row, None))
    for j in range(k):
        gens.append(_pauli("Z", code.LZ[j], j, nloc, n)); gen_meta.append(("Z", code.LZ[j], j))
    for row in HXi:
        gens.append(_pauli("X", row, None, nloc, n)); gen_meta.append(("X", row, None))
    for j in range(k):
        gens.append(_pauli("X", code.LX[j], j, nloc, n)); gen_meta.append(("X", code.LX[j], j))
    tab = stim.Tableau.from_stabilizers(gens)
    qmap = data_qubits + refs
    encoder = _remap_circuit(tab.to_circuit("elimination"), qmap)

    # ---- 组装
    joint = stim.Circuit()
    joint += encoder
    joint.append("TICK")
    if boundary == "noisy":
        for name, q, args in boundary_noise["init"]:
            joint.append(name, [q], args)
    joint += body
    if boundary == "noisy":
        for name, q, args in boundary_noise["readout"]:
            joint.append(name, [q], args)
    joint.append("TICK")
    mpp_rec0 = nrec
    for typ, row, j in gen_meta:
        terms = [stim.target_x(qmap[c]) if typ == "X" else stim.target_z(qmap[c]) for c in np.flatnonzero(row)]
        if j is not None:
            terms.append(stim.target_x(refs[j]) if typ == "X" else stim.target_z(refs[j]))
        tg = []
        for i, t in enumerate(terms):
            if i:
                tg.append(stim.target_combiner())
            tg.append(t)
        joint.append("MPP", tg)
    total = nrec + len(gen_meta)
    zrows = np.array([m[1] for m in gen_meta if m[0] == "Z"], dtype=np.uint8)
    xrows = np.array([m[1] for m in gen_meta if m[0] == "X"], dtype=np.uint8)
    z_rec = [mpp_rec0 + i for i, m in enumerate(gen_meta) if m[0] == "Z"]
    x_rec = [mpp_rec0 + i for i, m in enumerate(gen_meta) if m[0] == "X"]

    def remap(b: str, recs: list[int], what: str) -> list[int]:
        pb = parsed[b]
        out: collections.Counter = collections.Counter()
        v = np.zeros(n, dtype=np.uint8)
        for r in recs:
            if r in pb.readout_rec:
                v[pb.readout_rec[r]] ^= 1
            else:
                key = pb.rec_key.get(r)
                if key is None or key not in body_rec:
                    raise ValueError(f"{b}: {what} references measurement record {r} not found in the body")
                out[body_rec[key]] += 1
        if v.any():
            G, grec = (zrows, z_rec) if b == "Z" else (xrows, x_rec)
            x = solve_left(G, v)
            if x is None:
                raise ValueError(f"{b}: {what}: its data-readout part is not a product of "
                                 f"{'Z' if b == 'Z' else 'X'}-type stabilizers/logicals (not deterministic)")
            for i in np.flatnonzero(x):
                out[grec[i]] += 1
        return sorted(r for r, c in out.items() if c % 2)

    ndet = {}
    for sector_id, b in enumerate("ZX"):
        for d_i, recs in enumerate(parsed[b].detectors):
            tg = [stim.target_rec(r - total) for r in remap(b, recs, f"detector {d_i}")]
            joint.append("DETECTOR", tg, [sector_id])
        ndet[b] = len(parsed[b].detectors)
    nobs = {}
    off = 0
    for b in "ZX":
        obs = parsed[b].observables
        if sorted(obs) != list(range(len(obs))):
            raise ValueError(f"{b}: observable indices must be 0..K-1, got {sorted(obs)}")
        for o in range(len(obs)):
            tg = [stim.target_rec(r - total) for r in remap(b, obs[o], f"observable {o}")]
            joint.append("OBSERVABLE_INCLUDE", tg, off + o)
        nobs[b] = len(obs)
        off += len(obs)

    info = {"num_body_layers": num_body_layers, "num_body_measurements": nrec,
            "num_generators_measured": len(gen_meta), "stripped_boundary_targets": stripped,
            "boundary_noise_init": len(boundary_noise["init"]),
            "boundary_noise_readout": len(boundary_noise["readout"]),
            "encoder_gates": len(encoder)}
    return JointCircuit(joint, ndet["Z"], ndet["X"], nobs["Z"], nobs["X"], boundary, noise_model, p, refs, info)


def _pauli(typ: str, row: np.ndarray, ref: int | None, nloc: int, n: int) -> stim.PauliString:
    ps = stim.PauliString(nloc)
    for c in np.flatnonzero(row):
        ps[int(c)] = typ
    if ref is not None:
        ps[n + ref] = typ
    return ps


# ---------------------------------------------------------------------------
# 按 sector 拆 DEM、解码
# ---------------------------------------------------------------------------

def split_dem(dem: stim.DetectorErrorModel, num_det_z: int, num_obs_z: int):
    """把联合 DEM 的每个机制限制到 Z / X sector，合并相同症状（独立机制的 XOR 合成）。
    返回 {"Z": {(dets, obs): p}, "X": {...}}，dets/obs 为 sector 内编号的排序元组。"""
    out = {"Z": {}, "X": {}}
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        pr = inst.args_copy()[0]
        parts = {"Z": ([], []), "X": ([], [])}
        for t in inst.targets_copy():
            if t.is_separator():
                continue
            if t.is_relative_detector_id():
                v = t.val
                if v < num_det_z:
                    parts["Z"][0].append(v)
                else:
                    parts["X"][0].append(v - num_det_z)
            elif t.is_logical_observable_id():
                v = t.val
                if v < num_obs_z:
                    parts["Z"][1].append(v)
                else:
                    parts["X"][1].append(v - num_obs_z)
        for s in "ZX":
            dets, obs = parts[s]
            if not dets and not obs:
                continue
            key = (tuple(sorted(_xor_set(dets))), tuple(sorted(_xor_set(obs))))
            if not key[0] and not key[1]:
                continue
            q = out[s].get(key, 0.0)
            out[s][key] = q * (1 - pr) + pr * (1 - q)
    return out


def sector_circuit(circuit: stim.Circuit, sector: str, num_det_z: int, num_obs_z: int) -> stim.Circuit:
    """联合电路只保留一个 sector 的 detector / observable（重新编号）。其 DEM 就是该 sector 的限制；
    pymatching 路径用它让 stim 在 sector 内做 graphlike 分解。"""
    out = stim.Circuit()
    di = 0
    for inst in circuit.flattened():
        if inst.name == "DETECTOR":
            keep = (di < num_det_z) == (sector == "Z")
            di += 1
            if keep:
                out.append(inst)
        elif inst.name == "OBSERVABLE_INCLUDE":
            o = int(inst.gate_args_copy()[0])
            if (o < num_obs_z) == (sector == "Z"):
                out.append("OBSERVABLE_INCLUDE", inst.targets_copy(), o if sector == "Z" else o - num_obs_z)
        else:
            out.append(inst)
    return out


def split_dem_graphlike(dem: stim.DetectorErrorModel, num_det_z: int, num_obs_z: int):
    """pymatching 用：输入 decompose_errors=True 的联合 DEM。每个机制按 '^' 分成分量，分量按 sector 归类
    （分量跨 sector 则报错），返回 {"Z": [(p, [(dets, obs), ...])], "X": [...]}，编号为 sector 内编号。"""
    out = {"Z": [], "X": []}
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        pr = inst.args_copy()[0]
        comps: list[list] = [[]]
        for t in inst.targets_copy():
            if t.is_separator():
                comps.append([])
            else:
                comps[-1].append(t)
        per = {"Z": [], "X": []}
        for comp in comps:
            dets = [t.val for t in comp if t.is_relative_detector_id()]
            obs = [t.val for t in comp if t.is_logical_observable_id()]
            sectors = {("Z" if v < num_det_z else "X") for v in dets}
            sectors |= {("Z" if v < num_obs_z else "X") for v in obs}
            if not sectors:
                continue
            if len(sectors) > 1:
                raise ValueError(f"decomposed error component spans both sectors: {inst}")
            s = sectors.pop()
            od, oo = (0, 0) if s == "Z" else (num_det_z, num_obs_z)
            d = tuple(sorted(_xor_set([v - od for v in dets])))
            o = tuple(sorted(_xor_set([v - oo for v in obs])))
            if len(d) > 2:
                raise ValueError(f"pymatching: non-graphlike component with {len(d)} detectors: {inst}")
            if d or o:
                per[s].append((d, o))
        for s in "ZX":
            if per[s] and any(d for d, _ in per[s]):
                out[s].append((pr, per[s]))
    return out


def _xor_set(vals):
    c = collections.Counter(vals)
    return [v for v, m in c.items() if m % 2]


class _SectorDecoder:
    def __init__(self, model: dict, num_det: int, num_obs: int, decoder: DecoderConfig):
        import scipy.sparse as sp
        self.num_det, self.num_obs = num_det, num_obs
        self.name = decoder.name
        if decoder.name == "bposd":
            cols = [(d, o, pr) for (d, o), pr in model.items() if d]   # 无症状机制不影响解码
            self.num_mechanisms = len(cols)
            from ldpc import BpOsdDecoder
            rows, cidx, orows, ocidx = [], [], [], []
            for j, (d, o, _) in enumerate(cols):
                rows.extend(d); cidx.extend([j] * len(d))
                orows.extend(o); ocidx.extend([j] * len(o))
            H = sp.csc_matrix((np.ones(len(rows), dtype=np.uint8), (rows, cidx)), shape=(num_det, len(cols)))
            self.L = sp.csr_matrix((np.ones(len(orows), dtype=np.uint8), (orows, ocidx)), shape=(num_obs, len(cols)))
            priors = [pr for _, _, pr in cols]
            self.dec = BpOsdDecoder(pcm=H, error_channel=priors, **decoder.resolved_params())
        else:
            import pymatching
            # model 是 split_dem_graphlike 的输出：[(p, [(dets, obs), ...])]，每个分量 ≤ 2 个 detector
            lines = []
            n_err = 0
            for pr, comps in model:
                parts = [" ".join([f"D{x}" for x in d] + [f"L{x}" for x in o]) for d, o in comps]
                lines.append(f"error({pr!r}) " + " ^ ".join(parts))
                n_err += 1
            self.num_mechanisms = n_err
            if num_det:
                lines.append(f"detector D{num_det - 1}")
            if num_obs:
                lines.append(f"logical_observable L{num_obs - 1}")
            sub = stim.DetectorErrorModel("\n".join(lines))
            self.matching = pymatching.Matching.from_detector_error_model(sub)

    def decode(self, dets: np.ndarray) -> np.ndarray:
        """dets: (shots, num_det) bool -> 预测的 observable 翻转 (shots, num_obs) bool。"""
        if self.name == "pymatching":
            return self.matching.decode_batch(dets.astype(np.uint8)).astype(bool)
        out = np.zeros((dets.shape[0], self.num_obs), dtype=bool)
        for s in range(dets.shape[0]):
            if not dets[s].any():
                continue
            e = self.dec.decode(dets[s].astype(np.uint8))
            out[s] = (self.L @ e) % 2 == 1
        return out

    def effective_params(self) -> dict:
        if self.name != "bposd":
            return {}
        d = self.dec
        out = {}
        for a in ("max_iter", "bp_method", "ms_scaling_factor", "osd_method", "osd_order", "schedule",
                  "omp_thread_count", "random_serial_schedule"):
            try:
                v = getattr(d, a)
                out[a] = v if isinstance(v, (int, float, str, bool)) or v is None else str(v)
            except Exception:  # noqa: BLE001 - 属性名随 ldpc 版本变化
                pass
        return out


# ---------------------------------------------------------------------------
# 批采样（确定性）与 sinter 采样器
# ---------------------------------------------------------------------------

def _batch_seed(seed: int, index: int) -> int:
    return int(np.random.SeedSequence([seed, index]).generate_state(1, dtype=np.uint64)[0])


class _BatchRunner:
    def __init__(self, circuit: stim.Circuit, num_det_z: int, num_obs_z: int, decoder: DecoderConfig):
        self.circuit = circuit
        self.nz, self.oz = num_det_z, num_obs_z
        self.ndet, self.nobs = circuit.num_detectors, circuit.num_observables
        if decoder.name == "pymatching":
            model = {}
            for sec in "ZX":
                sc = sector_circuit(circuit, sec, num_det_z, num_obs_z)
                dem = sc.detector_error_model(allow_gauge_detectors=False, decompose_errors=True)
                model[sec] = split_dem_graphlike(dem, sc.num_detectors, sc.num_observables)["Z"]
        else:
            dem = circuit.detector_error_model(allow_gauge_detectors=False)
            model = split_dem(dem, num_det_z, num_obs_z)
        self.decoders = {"Z": _SectorDecoder(model["Z"], self.nz, self.oz, decoder),
                         "X": _SectorDecoder(model["X"], self.ndet - self.nz, self.nobs - self.oz, decoder)}

    def run(self, seed: int, index: int, shots: int) -> dict:
        t0 = time.process_time()
        s = _batch_seed(seed, index)
        sampler = self.circuit.compile_detector_sampler(seed=s)
        dets, obs = sampler.sample(shots, separate_observables=True)
        pz = self.decoders["Z"].decode(dets[:, :self.nz])
        px = self.decoders["X"].decode(dets[:, self.nz:])
        fz = (pz != obs[:, :self.oz]).any(axis=1)
        fx = (px != obs[:, self.oz:]).any(axis=1)
        return {"index": index, "stim_seed": s, "shots": shots,
                "fail_Z": int(fz.sum()), "fail_X": int(fx.sum()), "fail_any": int((fz | fx).sum()),
                "fail_both": int((fz & fx).sum()),
                "bits_Z": np.packbits(fz).tobytes().hex(), "bits_X": np.packbits(fx).tobytes().hex(),
                "cpu_s": time.process_time() - t0}


def _write_json_atomic(path: Path, obj: dict) -> None:
    tmp = path.with_suffix(".tmp%d" % os.getpid())
    tmp.write_text(json.dumps(obj))
    os.replace(tmp, path)


def _next_index(state_dir: Path) -> int:
    path = state_dir / "counter"
    with open(path, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            txt = f.read().strip()
            i = int(txt) if txt else 0
            f.seek(0)
            f.truncate()
            f.write(str(i + 1))
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    return i


try:
    import sinter as _sinter

    class _JointSampler(_sinter.Sampler):
        """sinter 自定义采样器：固定批大小、按批编号设种子、每批结果落盘。"""

        def __init__(self, state_dir: str, seed: int, batch_size: int, num_det_z: int, num_obs_z: int,
                     decoder: DecoderConfig):
            self.state_dir, self.seed, self.batch_size = state_dir, seed, batch_size
            self.num_det_z, self.num_obs_z, self.decoder = num_det_z, num_obs_z, decoder

        def compiled_sampler_for_task(self, task):
            return _CompiledJointSampler(self, task)

    class _CompiledJointSampler(_sinter.CompiledSampler):
        def __init__(self, parent: _JointSampler, task):
            self.p = parent
            self.runner = _BatchRunner(task.circuit, parent.num_det_z, parent.num_obs_z, parent.decoder)

        def handles_throttling(self) -> bool:
            return True

        def sample(self, suggested_shots: int):
            t0 = time.monotonic()
            d = Path(self.p.state_dir)
            idx = _next_index(d)
            res = self.runner.run(self.p.seed, idx, self.p.batch_size)
            _write_json_atomic(d / f"batch_{idx:09d}.json", res)
            return _sinter.AnonTaskStats(
                shots=res["shots"], errors=res["fail_any"], seconds=time.monotonic() - t0,
                custom_counts=collections.Counter({"fail_Z": res["fail_Z"], "fail_X": res["fail_X"],
                                                   "fail_both": res["fail_both"]}))
except ImportError:  # pragma: no cover
    _JointSampler = None


def _load_batches(state_dir: Path) -> dict[int, dict]:
    out = {}
    for f in state_dir.glob("batch_*.json"):
        r = json.loads(f.read_text())
        out[r["index"]] = r
    return out


def _prefix(batches: dict[int, dict], stop: StopRule, upto: int | None = None):
    """从 0 起逐批累加，返回 (满足停止规则的最短前缀长度 or None, 已检查的连续长度)。"""
    shots = fa = fz = fx = 0
    b = 0
    while (upto is None or b < upto) and b in batches:
        r = batches[b]
        shots += r["shots"]; fa += r["fail_any"]; fz += r["fail_Z"]; fx += r["fail_X"]
        b += 1
        if stop.satisfied(shots, fa, fz, fx):
            return b, b
    return None, b


# ---------------------------------------------------------------------------
# 结果
# ---------------------------------------------------------------------------

@dataclass
class L2Result:
    inputs: dict
    counts: dict
    rates: dict
    per_round: dict
    joint: dict
    decoder: dict
    reproducibility: dict
    circuit: dict
    versions: dict
    timing: dict
    warnings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    def summary(self) -> str:
        r, pr = self.rates, self.per_round
        lines = [f"L2 [{self.inputs['noise_model']} p={self.inputs['p']} rounds={self.inputs['rounds']} "
                 f"boundary={self.inputs['boundary']} decoder={self.decoder['name']} seed={self.inputs['seed']}] "
                 f"shots={self.counts['shots']}"]
        for key in ("P_Z", "P_X", "P_any"):
            lines.append(f"  {key} = {r[key]['label']}")
            q = pr[key]
            lines.append(f"     per round {q['best']:.4e} [{q['low']:.4e}, {q['high']:.4e}]")
        lines.append(f"  P_indep_approx (reference only) = {r['P_indep_approx']:.4e}")
        for w in self.warnings:
            lines.append(f"  WARNING: {w}")
        return "\n".join(lines)


def _interval_dict(errors: int, shots: int, lf: float) -> dict:
    iv = binomial_interval(errors, shots, lf)
    return {"errors": errors, "shots": shots, "best": iv.best, "low": iv.low, "high": iv.high,
            "likelihood_factor": lf, "sigma": iv.sigma, "label": iv.label()}


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def sample_l2(code: CSSCode,
              circuits: Mapping[str, stim.Circuit] | Callable[[str, int], stim.Circuit],
              data_qubits,
              *,
              p: float,
              rounds: int,
              noise_model: str = DEFAULT_MODEL,
              boundary: str = DEFAULT_BOUNDARY,
              decoder: DecoderConfig | None = None,
              seed: int,
              stop: StopRule,
              num_workers: int = 4,
              noise_kwargs: Mapping | None = None,
              likelihood_factor: float = DEFAULT_LIKELIHOOD_FACTOR,
              work_dir: str | os.PathLike | None = None,
              keep_batches: bool = False) -> L2Result:
    """X/Z 联合采样的逻辑错误率。

    Args:
        code: CSSCode。
        circuits: {"Z": circ, "X": circ} 无噪声 memory 电路（同一调度、rounds 轮），或
            callable(basis, rounds) -> 无噪声电路。
        data_qubits: 码第 j 列对应的电路比特编号。
        p, noise_model, noise_kwargs: 传给 evaluators.noise.add_noise。
        rounds: 带噪声的 syndrome 提取轮数（用于每轮换算；必须与电路一致）。
        boundary: "paper"（默认）或 "noisy"，见模块说明。
        decoder: DecoderConfig，默认 BP-OSD + IBM 参数。
        seed: 整数种子（必填）。
        stop: StopRule。
        num_workers: sinter 进程数（≥1）。
        work_dir: 存放批文件的目录（默认临时目录，结束后删除，除非 keep_batches=True）。
    """
    if not isinstance(seed, (int, np.integer)) or seed < 0:
        raise ValueError("seed must be a non-negative int")
    if num_workers < 1:
        raise ValueError("num_workers must be >= 1")
    decoder = decoder or DecoderConfig()
    dparams = decoder.resolved_params()
    if callable(circuits):
        circuits = {b: circuits(b, rounds) for b in "ZX"}
    circuits = {b: circuits[b] for b in "ZX"}
    t_wall = time.time()
    jc = build_joint_circuit(code, circuits, data_qubits, noise_model=noise_model, p=p, boundary=boundary,
                             noise_kwargs=noise_kwargs)
    t_build = time.time() - t_wall

    own_dir = work_dir is None
    state_dir = Path(tempfile.mkdtemp(prefix="l2_")) if own_dir else Path(work_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    if any(state_dir.glob("batch_*.json")) or (state_dir / "counter").exists():
        raise ValueError(f"work_dir {state_dir} is not empty")
    import sinter

    sampler = _JointSampler(str(state_dir), int(seed), stop.batch_size, jc.num_detectors_z,
                            jc.num_observables_z, decoder)
    task = sinter.Task(circuit=jc.circuit, decoder="l2_joint",
                       json_metadata={"p": p, "boundary": boundary, "noise": noise_model})
    sinter_waves = []
    fill_ins = []
    runner_main = None
    try:
        while True:
            batches = _load_batches(state_dir)
            need, contiguous = _prefix(batches, stop)
            if need is not None:
                break
            # 先补齐前缀中缺的批（在主进程按同一种子计算）
            have_max = max(batches) + 1 if batches else 0
            missing = [i for i in range(contiguous, have_max) if i not in batches]
            if missing:
                if runner_main is None:
                    runner_main = _BatchRunner(jc.circuit, jc.num_detectors_z, jc.num_observables_z, decoder)
                for i in missing:
                    _write_json_atomic(state_dir / f"batch_{i:09d}.json", runner_main.run(int(seed), i, stop.batch_size))
                    fill_ins.append(i)
                continue
            done_shots = sum(r["shots"] for r in batches.values())
            done_any = sum(r["fail_any"] for r in batches.values())
            remaining = stop.max_shots - done_shots
            if remaining <= 0:
                # 前缀已达到 max_shots 应已满足；这里只是防御
                break
            wave_errors = None
            if stop.max_errors is not None:
                wave_errors = max(1, stop.max_errors - done_any)
                if stop.min_sector_errors is not None and done_any >= stop.max_errors:
                    wave_errors = None   # 只差 sector 下限：按 shots 推进
            if wave_errors is None and stop.min_sector_errors is not None:
                fz = sum(r["fail_Z"] for r in batches.values()); fx = sum(r["fail_X"] for r in batches.values())
                lo = max(1, min(fz, fx))
                est = int(math.ceil(done_shots * (stop.min_sector_errors / lo) * 1.1)) - done_shots if done_shots else stop.batch_size * num_workers
                remaining = min(remaining, max(est, stop.batch_size))
            # sinter 的 max_shots 至少一批
            wave_shots = max(stop.batch_size, remaining)
            t0 = time.time()
            stats = sinter.collect(num_workers=num_workers, tasks=[task], decoders=["l2_joint"],
                                   custom_decoders={"l2_joint": sampler}, max_shots=wave_shots,
                                   max_errors=wave_errors, print_progress=False)
            sinter_waves.append({"max_shots": wave_shots, "max_errors": wave_errors,
                                 "shots": int(sum(s.shots for s in stats)),
                                 "errors": int(sum(s.errors for s in stats)),
                                 "wall_s": round(time.time() - t0, 2)})
            if len(_load_batches(state_dir)) == len(batches):
                raise RuntimeError("sinter wave produced no new batches (worker failure?)")
        batches = _load_batches(state_dir)
        need, _ = _prefix(batches, stop)
        used = [batches[i] for i in range(need)]
        discarded = sorted(i for i in batches if i >= need)
        decoder_effective = {}
        if decoder.name == "bposd":
            probe = runner_main or _BatchRunner(jc.circuit, jc.num_detectors_z, jc.num_observables_z, decoder)
            decoder_effective = {"Z": probe.decoders["Z"].effective_params(),
                                 "X": probe.decoders["X"].effective_params(),
                                 "num_mechanisms": {s: probe.decoders[s].num_mechanisms for s in "ZX"}}
        else:
            probe = runner_main or _BatchRunner(jc.circuit, jc.num_detectors_z, jc.num_observables_z, decoder)
            decoder_effective = {"num_mechanisms": {s: probe.decoders[s].num_mechanisms for s in "ZX"}}
        cpu_all = sum(r["cpu_s"] for r in batches.values())
    finally:
        if own_dir and not keep_batches:
            shutil.rmtree(state_dir, ignore_errors=True)

    shots = sum(r["shots"] for r in used)
    fz = sum(r["fail_Z"] for r in used)
    fx = sum(r["fail_X"] for r in used)
    fa = sum(r["fail_any"] for r in used)
    fb = sum(r["fail_both"] for r in used)
    lf = likelihood_factor
    rates = {"P_Z": _interval_dict(fz, shots, lf), "P_X": _interval_dict(fx, shots, lf),
             "P_any": _interval_dict(fa, shots, lf), "P_both": fb / shots}
    PZ, PX = fz / shots, fx / shots
    rates["P_indep_approx"] = 1 - (1 - PZ) * (1 - PX)
    rates["P_indep_approx_note"] = "reference only: assumes X/Z failures independent; NOT the score"
    pr = {}
    for key in ("P_Z", "P_X", "P_any"):
        iv = rates[key]
        pr[key] = {"best": per_round(iv["best"], rounds), "low": per_round(iv["low"], rounds),
                   "high": per_round(iv["high"], rounds),
                   "sinter_formula_best": _per_round_sinter(iv["best"], rounds)}
    pr["formula"] = PER_ROUND_FORMULA
    pr["sinter_formula"] = PER_ROUND_SINTER_FORMULA
    pr["interval"] = "per-round transform of the LR interval endpoints (monotone)"
    warnings = []
    if min(fz, fx) < MIN_LOGICAL_ERRORS_FOR_COMPARISON:
        warnings.append(f"fewer than {MIN_LOGICAL_ERRORS_FOR_COMPARISON} logical errors in a sector "
                        f"(Z {fz}, X {fx}); below the comparison threshold of evaluators/stats.py")
    if boundary == "noisy":
        warnings.append("boundary='noisy' is the project-internal convention; do not compare with literature")
    if noise_model not in ("sd6", "si1000"):
        warnings.append(f"noise model {noise_model!r} is not a scoring model")

    inputs = {"code": {"name": code.name, "n": code.n, "k": code.k,
                       "HX_rows": int(code.HX.shape[0]), "HZ_rows": int(code.HZ.shape[0])},
              "noise_model": noise_model, "noise_kwargs": dict(noise_kwargs or {}), "p": p, "rounds": rounds,
              "boundary": boundary, "seed": int(seed), "stop": dataclasses.asdict(stop),
              "num_workers": num_workers, "likelihood_factor": lf}
    return L2Result(
        inputs=inputs,
        counts={"shots": shots, "fail_Z": fz, "fail_X": fx, "fail_any": fa, "fail_both": fb,
                "batches_used": need},
        rates=rates,
        per_round=pr,
        joint={"method": "exact joint X/Z sampling (one physical fault realisation per shot, both sectors)",
               "approximation": None,
               "decoding": "X and Z sectors decoded separately (joint DEM restricted per sector; "
                           "Y correlations kept in sampling, dropped in decoding)",
               "num_detectors": {"Z": jc.num_detectors_z, "X": jc.num_detectors_x},
               "num_observables": {"Z": jc.num_observables_z, "X": jc.num_observables_x},
               "info": jc.info},
        decoder={"name": decoder.name, "params": dparams, "effective": decoder_effective,
                 "library": "ldpc.BpOsdDecoder" if decoder.name == "bposd" else "pymatching.Matching"},
        reproducibility={
            "deterministic": True,
            "scheme": "fixed batch_size; batch b sampled with stim seed SeedSequence([seed, b]); official result = "
                      "shortest batch prefix satisfying the stop rule; missing prefix batches recomputed in-process",
            "independent_of": ["num_workers", "process scheduling", "timing"],
            "caveat": "bit-identical only with the same stim version and CPU SIMD width (stim seed semantics)",
            "batches_completed": len(batches), "batches_discarded_beyond_prefix": discarded,
            "batches_recomputed_in_main_process": fill_ins, "sinter_waves": sinter_waves,
        },
        circuit={"candidate_hash": circuit_hash(circuits),
                 "joint_hash": hashlib.sha256(str(jc.circuit).encode()).hexdigest(),
                 "num_qubits_joint": jc.circuit.num_qubits},
        versions=library_versions(),
        timing={"build_s": round(t_build, 2), "wall_s": round(time.time() - t_wall, 2),
                "decode_cpu_s_all_batches": round(cpu_all, 2),
                "decode_cpu_s_used_batches": round(sum(r["cpu_s"] for r in used), 2)},
        warnings=warnings,
    )
