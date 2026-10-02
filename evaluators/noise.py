"""命名噪声模型：把**无噪声**的 stim 电路变成带噪声电路。

接口：
    add_noise(circuit, model, p, *, idle=None, si1000_resonator_on_gate_qubits=False) -> stim.Circuit

约定（所有模型共用）：
  - 电路必须用 TICK 分时间步（“层”= 相邻两个 TICK 之间的所有指令）。
    同一层内每个比特最多被一个操作作用（否则噪声语义不清，直接报错）。
  - 输入电路不得含任何噪声：噪声通道（DEPOLARIZE*/X_ERROR/PAULI_CHANNEL*/E/
    ELSE_CORRELATED_ERROR/HERALDED_*/I_ERROR…，即使概率为 0 也拒绝），以及带非零翻转
    概率参数的测量（如 M(0.01)）、带参数的 MPAD。发现即抛 NoisyCircuitError。
  - REPEAT 会被展开（输出是展开后的电路）。
  - 支持的操作：单比特 Clifford 酉门（含 I）、双比特 Clifford 酉门（不得带 rec/sweep 经典控制目标）、
    单比特复位 R/RX/RY、单比特测量 M/MX/MY、测量-复位 MR/MRX/MRY，以及注释类指令
    DETECTOR / OBSERVABLE_INCLUDE / QUBIT_COORDS / SHIFT_COORDS / MPAD（无参数）。
    多比特 Pauli 乘积测量（MPP/MXX/MZZ…）等其他指令一律 NotImplementedError。
  - “测量前翻转”(pre_flip) 实现为测量前插入 X_ERROR（Z/Y 基测量）或 Z_ERROR（X 基测量），
    与 stim.Circuit.generated 的 before_measure_flip_probability 口径一致；它也会翻转测量后的
    比特状态（对不复位而复用的比特，这与只翻转记录的 M(p) 不同）。
    “记录翻转”(record_flip) 用 M(p) 的参数实现，只翻转经典结果（gross_sd6 使用）。
  - “复位后翻转”：R/RY 后 X_ERROR，RX 后 Z_ERROR。MR 系列同时有测量噪声与复位后翻转。
  - 隐式空闲噪声：每一层中**未被任何操作作用**的比特（取电路中出现过的全部比特）施加
    DEPOLARIZE1。比特在第一次复位之前 / 最后一次测量之后的空闲噪声对 DEM 没有影响
    （被复位抹掉或不再被读出），因此不做生命期裁剪。

模型（系数与出处见 research/literature/noise-models.md，lit-scout 2026-10-02 核对全文）：
  uniform_depolarizing(p, idle=True|False)：
      单比特门后 DEPOLARIZE1(p)；双比特门后 DEPOLARIZE2(p)；测量前翻转 p；复位后翻转 p；
      idle=True（默认）时每层未被操作的比特 DEPOLARIZE1(p)；idle=False 时无空闲噪声。
      idle=True 即 SD6（arXiv:2108.10457 表 1、表 2 的 SD6 列）。
      idle=False 时与 stim.Circuit.generated(after_clifford_depolarization=p,
      before_measure_flip_probability=p, after_reset_flip_probability=p,
      before_round_data_depolarization=0) 的 DEM 完全一致（见 tests/test_noise.py）。
      注意 E-001 用的 stim 口径（STIM_UNIFORM_4P）还多一项 before_round_data_depolarization=p，
      没有空闲噪声；它需要知道“轮”的边界，本模块不实现。
  sd6(p)：uniform_depolarizing(p, idle=True) 的别名（不接受 idle=False）。**评估器默认口径。**
  legacy_no_idle(p)：uniform_depolarizing(p, idle=False) 的别名。只用于与 E-001 / stim 生成器口径
      对照（LEGACY_MODELS），不得用于给候选打分。
  si1000(p)：arXiv:2108.10457（Gidney, Newman, Fowler, Broughton）表 2 的 SI1000 列，
      arXiv:2202.11845（Gidney, Newman, McEwen）表 3 沿用：
        CZ 后 DEPOLARIZE2(p)；单比特 Clifford 后 DEPOLARIZE1(p/10)；复位后翻转 2p；
        测量前翻转 5p；空闲 DEPOLARIZE1(p/10)；
        ResonatorIdle：某层只要有比特在测量或复位，则该层中既没被测量也没被复位的比特
        再叠加 DEPOLARIZE1(2p)（表 1 脚注：噪声规则相互叠加，所以空闲比特同时有 p/10 与 2p）。
      原生双比特门只有 CZ：电路里出现其他双比特门（如 CX）直接报错——SI1000 的电路要用 CZ+H 搭，
      不能沿用 CX 电路只改系数（noise-models.md §1.3）。
      歧义（待负责人裁决）：ResonatorIdle 是否也作用于该层正在做门的比特。表 1 字面没有排除，
      物理上不应作用。默认 si1000_resonator_on_gate_qubits=False（不作用），可切换。
  gross_sd6(p)：arXiv:2308.07915（Bravyi et al.）第 6 节的电路噪声：
        双比特门后 DEPOLARIZE2(p)；复位后翻转 p（制备正交态）；测量结果经典翻转 p（M(p)）；
        **只有显式的 I 门**才有空闲噪声 DEPOLARIZE1(p)，没有隐式空闲噪声。
        论文电路没有其他单比特门；若出现（如 H），本实现同样施加 DEPOLARIZE1(p)（论文未定义，自行约定）。
        **警告**：空闲噪声只来自显式 I 门，候选电路只要不写 I 就能躲开空闲噪声。所以 gross_sd6 只用于
        复现 IBM 论文的 baseline 电路（其 I 门位置按论文表 5 写好），不在 SCORING_MODELS 中，
        不得用于给搜索候选打分。
"""
from __future__ import annotations

import stim

__all__ = [
    "NoisyCircuitError",
    "NOISE_MODELS",
    "SI1000_SPEC",
    "SI1000_SPEC_STATUS",
    "SCORING_MODELS",
    "DEFAULT_MODEL",
    "LEGACY_MODELS",
    "add_noise",
    "find_noise_instructions",
    "split_layers",
]


class NoisyCircuitError(ValueError):
    """输入电路已经含噪声指令。"""


ANNOTATIONS = {"DETECTOR", "OBSERVABLE_INCLUDE", "QUBIT_COORDS", "SHIFT_COORDS", "MPAD"}

# SI1000 系数（乘以 p）。出处：arXiv:2108.10457 表 2 SI1000 列；arXiv:2202.11845 表 3。
# 核对：research/literature/noise-models.md §1.3（lit-scout 2026-10-02，读全文核对）。
# 我起初凭记忆写下的值与该核对结果一致；本评估器作者未独立阅读原文。
SI1000_SPEC = {
    "two_qubit_gate_depolarize2": 1.0,     # CZ 后（原生门只有 CZ）
    "single_qubit_gate_depolarize1": 0.1,
    "measurement_flip": 5.0,               # 测量前翻转
    "reset_flip": 2.0,                     # 复位后翻转
    "idle_depolarize1": 0.1,
    "resonator_idle_depolarize1": 2.0,     # 与 idle 叠加
}
SI1000_SPEC_STATUS = ("checked against research/literature/noise-models.md §1.3 (lit-scout, full-text); "
                      "ResonatorIdle-on-gate-qubits ambiguity unresolved")

NOISE_MODELS = ("sd6", "si1000", "gross_sd6", "uniform_depolarizing", "legacy_no_idle")
# 评估器打分/比较的默认口径：必须含逐层空闲噪声（auditor E-001 H1：无空闲噪声会让调度搜索白拿深度）。
# 评估器 v2（2026-10-02）：si1000 移出打分模型。N1（I 门躲 ResonatorIdle）已修，但 N2（SI1000 原生 CZ+H 电路被
# L0 / L2 误拒）未修，且评估器的模板电路只用 CX；在 N2 修好、并约定 CX 调度如何编译成 CZ+H 之前不得用于打分。
SCORING_MODELS = ("sd6",)
DEFAULT_MODEL = "sd6"
# 只用于与 E-001 / stim 生成器对照，不得用于给候选打分。
LEGACY_MODELS = ("legacy_no_idle",)


def _basis_of(name: str) -> str:
    if name.endswith("X"):
        return "X"
    if name.endswith("Y"):
        return "Y"
    return "Z"


def _flip_channel(basis: str) -> str:
    # 使 basis 本征态翻转的 Pauli 误差
    return "Z_ERROR" if basis == "X" else "X_ERROR"


def find_noise_instructions(circuit: stim.Circuit) -> list[str]:
    """列出电路里所有噪声相关指令（字符串描述）。空列表 = 无噪声。"""
    found: list[str] = []
    for i, inst in enumerate(circuit.flattened()):
        name = inst.name
        if name == "TICK":
            continue
        gd = stim.gate_data(name)
        args = inst.gate_args_copy()
        if gd.is_noisy_gate and (not gd.produces_measurements or name.startswith("HERALDED")):
            found.append(f"#{i} {inst} (noise channel)")
        elif (gd.produces_measurements or name == "MPAD") and any(a != 0 for a in args):
            found.append(f"#{i} {inst} (measurement with flip probability {args})")
    return found


def _qubits_of(inst: stim.CircuitInstruction) -> list[int]:
    return [t.value for t in inst.targets_copy() if t.is_qubit_target]


def split_layers(circuit: stim.Circuit) -> list[list[stim.CircuitInstruction]]:
    """展开 REPEAT，按 TICK 切成层。返回每层的指令列表（不含 TICK）。"""
    layers: list[list[stim.CircuitInstruction]] = [[]]
    for inst in circuit.flattened():
        if inst.name == "TICK":
            layers.append([])
        else:
            layers[-1].append(inst)
    return layers


def _classify(inst: stim.CircuitInstruction) -> str:
    name = inst.name
    if name in ANNOTATIONS:
        return "annotation"
    gd = stim.gate_data(name)
    for t in inst.targets_copy():
        if t.is_measurement_record_target or t.is_sweep_bit_target:
            raise NotImplementedError(f"classically controlled gate not supported: {inst}")
        if not t.is_qubit_target:
            raise NotImplementedError(f"non-qubit target not supported: {inst}")
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
    raise NotImplementedError(f"instruction {name} not supported by the noise module")


def _model_params(model: str, p: float, idle: bool | None) -> dict:
    """返回各通道概率。idle 只对 uniform_depolarizing 可选；其他模型的口径是固定的。"""
    base = dict(p1=p, p2=p, pm=p, pr=p, idle=p, resonator=0.0, meas_mode="pre_flip",
                implicit_idle=True, native_2q=None)
    if model == "uniform_depolarizing":
        base["implicit_idle"] = True if idle is None else bool(idle)
        return base
    if model == "legacy_no_idle":
        if idle is True:
            raise ValueError("legacy_no_idle has no idle noise by definition")
        base["implicit_idle"] = False
        return base
    if model == "sd6":
        if idle is False:
            raise ValueError("sd6 always has idle noise; use uniform_depolarizing(idle=False) instead")
        return base
    if model == "si1000":
        if idle is False:
            raise ValueError("si1000 always has idle noise")
        s = SI1000_SPEC
        return dict(p1=s["single_qubit_gate_depolarize1"] * p, p2=s["two_qubit_gate_depolarize2"] * p,
                    pm=s["measurement_flip"] * p, pr=s["reset_flip"] * p, idle=s["idle_depolarize1"] * p,
                    resonator=s["resonator_idle_depolarize1"] * p, meas_mode="pre_flip",
                    implicit_idle=True, native_2q={"CZ"})
    if model == "gross_sd6":
        if idle is True:
            raise ValueError("gross_sd6 has idle noise only on explicit I gates (arXiv:2308.07915 Sec. 6)")
        return dict(p1=p, p2=p, pm=p, pr=p, idle=0.0, resonator=0.0, meas_mode="record_flip",
                    implicit_idle=False, native_2q=None)
    raise ValueError(f"unknown noise model {model!r}; known: {NOISE_MODELS}")


def add_noise(circuit: stim.Circuit, model: str, p: float, *, idle: bool | None = None,
              si1000_resonator_on_gate_qubits: bool = False) -> stim.Circuit:
    """按命名模型给无噪声电路插入噪声。

    Args:
        circuit: 无噪声、按 TICK 分层的电路。
        model: NOISE_MODELS 之一："uniform_depolarizing" / "sd6" / "si1000" / "gross_sd6"。
        p: 物理错误率参数（各通道概率 = 模型系数 × p，必须合法）。
        idle: 只对 uniform_depolarizing 有意义：是否对每层中未被操作的比特加 DEPOLARIZE1(p)。
            None = 模型默认（uniform_depolarizing / sd6 / si1000 有，gross_sd6 无）。
            对其他模型传入与其口径冲突的值会报错（命名模型的口径是冻结的）。
        si1000_resonator_on_gate_qubits: SI1000 的 ResonatorIdle 是否也作用于测量/复位层中
            正在做门的比特（论文歧义，默认 False）。

    Raises:
        NoisyCircuitError: 输入已含噪声。
        ValueError: 未知模型、p 不合法、没有 TICK、同一层同一比特被多次作用、非原生双比特门。
        NotImplementedError: 不支持的指令。
    """
    if not (0 <= p <= 1):
        raise ValueError(f"p must be in [0, 1], got {p}")
    noise = find_noise_instructions(circuit)
    if noise:
        raise NoisyCircuitError("input circuit already contains noise:\n  " + "\n  ".join(noise[:10]))
    prm = _model_params(model, p, idle)
    limits = {"p1": 0.75, "idle": 0.75, "resonator": 0.75, "p2": 15 / 16, "pm": 1.0, "pr": 1.0}
    for k, lim in limits.items():
        if prm[k] > lim:
            raise ValueError(f"{model} at p={p} gives invalid probability {k}={prm[k]}")
    layers = split_layers(circuit)
    if len(layers) == 1 and any(_classify(i) != "annotation" for i in layers[0]):
        raise ValueError("circuit has no TICK instructions; time steps must be delimited by TICK")

    all_qubits: set[int] = set()
    for layer in layers:
        for inst in layer:
            if inst.name not in ANNOTATIONS:
                all_qubits.update(_qubits_of(inst))

    out = stim.Circuit()
    for li, layer in enumerate(layers):
        if li > 0:
            out.append("TICK")
        touched: set[int] = set()
        explicit_idle: set[int] = set()
        measured_or_reset: set[int] = set()
        for inst in layer:
            kind = _classify(inst)
            qs = _qubits_of(inst)
            if kind != "annotation":
                dup = touched.intersection(qs) | {q for q in qs if qs.count(q) > 1} | explicit_idle.intersection(qs)
                if dup:
                    raise ValueError(
                        f"layer {li}: qubit(s) {sorted(dup)} acted on more than once in the same time step "
                        f"(instruction {inst}); insert TICKs")
            if (kind == "1q" and inst.name == "I" and prm["implicit_idle"]
                    and (prm["resonator"] > 0 or prm["p1"] != prm["idle"])):
                # 评估器 v2（auditor G1 N1）：有隐式空闲噪声的模型里，I 门就是空闲——按空闲比特处理
                # （空闲噪声 + si1000 的 ResonatorIdle），不能当作“门”来躲开 ResonatorIdle。
                # sd6 / uniform_depolarizing 里 I 门噪声与空闲噪声相同（都是 DEPOLARIZE1(p)），输出保持原样。
                out.append(inst)
                explicit_idle.update(qs)
                continue
            if kind != "annotation":
                touched.update(qs)
            if kind == "annotation":
                out.append(inst)
            elif kind == "1q":
                out.append(inst)
                if prm["p1"] > 0:
                    out.append("DEPOLARIZE1", qs, prm["p1"])
            elif kind == "2q":
                if prm["native_2q"] is not None and inst.name not in prm["native_2q"]:
                    raise ValueError(f"{model}: two-qubit gate {inst.name} is not native "
                                     f"(allowed: {sorted(prm['native_2q'])}); rebuild the circuit with native gates")
                out.append(inst)
                if prm["p2"] > 0:
                    out.append("DEPOLARIZE2", qs, prm["p2"])
            elif kind == "reset":
                measured_or_reset.update(qs)
                out.append(inst)
                if prm["pr"] > 0:
                    out.append(_flip_channel(_basis_of(inst.name)), qs, prm["pr"])
            elif kind in ("measure", "measure_reset"):
                measured_or_reset.update(qs)
                ch = _flip_channel(_basis_of(inst.name))
                if prm["meas_mode"] == "pre_flip":
                    if prm["pm"] > 0:
                        out.append(ch, qs, prm["pm"])
                    out.append(inst)
                else:
                    out.append(inst.name, qs, prm["pm"]) if prm["pm"] > 0 else out.append(inst)
                if kind == "measure_reset" and prm["pr"] > 0:
                    out.append(ch, qs, prm["pr"])
        idle_q = sorted(all_qubits - touched)
        if prm["implicit_idle"] and idle_q and prm["idle"] > 0:
            out.append("DEPOLARIZE1", idle_q, prm["idle"])
        if measured_or_reset and prm["resonator"] > 0:
            pool = all_qubits - measured_or_reset if si1000_resonator_on_gate_qubits else set(idle_q)
            if pool:
                out.append("DEPOLARIZE1", sorted(pool), prm["resonator"])
    return out
