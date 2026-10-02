"""auditor G1 前全面攻击（research/audits/2026-10-02-evaluator-G1.md）中每个“成功的攻击”的回归测试。

每个测试对应报告 §1 表里一行，证明攻击现在被拒绝，或在结构上不可能（候选只能提交调度 JSON）。
攻击电路的构造照抄 research/audits/2026-10-02-evaluator-G1-scripts/common.py。
"""
from __future__ import annotations

import numpy as np
import pytest
import stim

from evaluators.codes import CSSCode, rotated_surface_code_from_stim
from evaluators.l0 import L0Constraints, check_l0

FAST_DIST = dict(distance_bposd_trials=100, distance_lns_starts=8)


def _edges(*circs):
    out = set()
    for c in circs:
        for i in c.flattened():
            if i.name in ("CX", "CZ"):
                for g in i.target_groups():
                    out.add(tuple(t.value for t in g))
    return out


def _honest(d, rounds):
    code, data, cz = rotated_surface_code_from_stim(d, "Z", rounds)
    _, _, cx = rotated_surface_code_from_stim(d, "X", rounds)
    return code, data, {"Z": cz, "X": cx}


def _cons(data, circs, rounds, **kw):
    allc = list(circs.values())
    base = dict(data_qubits=data, max_qubits=max(c.num_qubits for c in allc), allowed_edges=_edges(*allc),
                rounds=rounds, require_opposite_type_detectors=True, **FAST_DIST)
    base.update(kw)
    return L0Constraints(**base)


def fake_rounds(d: int, basis: str, rounds: int) -> stim.Circuit:
    """A1（auditor common.fake_rounds）：1 轮真提取（MR 改成 M）+ rounds-1 层只重测辅助比特。"""
    c = stim.Circuit.generated("surface_code:rotated_memory_" + basis.lower(), distance=d, rounds=1).flattened()
    out = stim.Circuit()
    anc = None
    pending = False
    for inst in c:
        if inst.name == "MR":
            anc = [t.value for t in inst.targets_copy()]
            out.append("M", anc)
            pending = True
            continue
        if pending and inst.name != "DETECTOR":
            na = len(anc)
            for _ in range(rounds - 1):
                out.append("TICK")
                out.append("M", anc)
                for i in range(na):
                    out.append("DETECTOR", [stim.target_rec(-na + i), stim.target_rec(-2 * na + i)])
            out.append("TICK")
            pending = False
        out.append(inst)
    return out


def fake_rounds_early_readout(d: int, basis: str, rounds: int) -> stim.Circuit:
    """A1b（auditor common.fake_rounds_early_readout）：同 A1，但数据比特在唯一一轮后立刻读出，重测放在读出之后。"""
    c = stim.Circuit.generated("surface_code:rotated_memory_" + basis.lower(), distance=d, rounds=1).flattened()
    out = stim.Circuit()
    anc = None
    for inst in c:
        if inst.name == "MR":
            anc = [t.value for t in inst.targets_copy()]
            out.append("M", anc)
        else:
            out.append(inst)
    na = len(anc)
    for r in range(rounds - 1):
        out.append("TICK")
        out.append("M", anc)
        for i in range(na):
            prev = -2 * na + i if r > 0 else -(na + d * d + na) + i
            out.append("DETECTOR", [stim.target_rec(-na + i), stim.target_rec(prev)])
    return out


# ---------------------------------------------------------------------------
# A1 / A1b 伪轮次（L0 第二道防线；pipeline 只接受调度，结构上不可能，见 test_pipeline.py）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("d,rounds", [(3, 3), (5, 10)])
def test_A1_fake_rounds_rejected(d, rounds):
    code, data, hon = _honest(d, rounds)
    fake = {b: fake_rounds(d, b, rounds) for b in "ZX"}
    cons = _cons(data, {**hon, **{f"f{b}": c for b, c in fake.items()}}, rounds, min_circuit_distance=d)
    rep = check_l0(fake, code, "both", cons)
    assert not rep.passed
    for b in "ZX":
        res = rep.get(f"{b}:stabilizer_coverage")
        assert res.status == "fail", rep.to_text()
        assert "do not re-extract the stabilizer from the data qubits" in res.message
        assert "fake" in res.message
    # 对照：同参数的诚实电路通过
    honest = check_l0(hon, code, "both", _cons(data, hon, rounds, min_circuit_distance=d))
    assert honest.passed and honest.d_circ == d, honest.to_text()


@pytest.mark.parametrize("d,rounds", [(3, 3), (5, 10)])
def test_A1b_fake_rounds_after_readout_rejected(d, rounds):
    code, data, hon = _honest(d, rounds)
    fake = {b: fake_rounds_early_readout(d, b, rounds) for b in "ZX"}
    cons = _cons(data, {**hon, **{f"f{b}": c for b, c in fake.items()}}, rounds, min_circuit_distance=d)
    rep = check_l0(fake, code, "both", cons)
    assert not rep.passed
    for b in "ZX":
        res = rep.get(f"{b}:data_layout")
        assert res.status == "fail", rep.to_text()
        assert "after the final data readout" in res.message


def test_A1b_reextraction_check_alone_also_rejects():
    """即使不看“读出之后不许测量”这一条，伪窗口本身也被重提取判据拒绝（把 A1b 的重测挪到读出之前 = A1）。"""
    code, data, hon = _honest(3, 4)
    fake = fake_rounds(3, "Z", 4)
    r = check_l0(fake, code, "Z", _cons(data, {"Z": fake, **hon}, 4))
    assert r.get("stabilizer_coverage").status == "fail"
    assert "fake" in r.get("stabilizer_coverage").message


def test_measure_twice_in_one_round_is_still_a_real_extraction():
    """语义说明：同一窗口内用新的 CNOT 再提取一次是真提取（不是伪轮次）；只重测辅助比特不是。
    这里用 memory_builder 的诚实电路验证重提取判据不误伤：表面码、Steane、[[4,2,2]] 流水电路，冗余行。"""
    from memory_builder import build_memory, build_pipelined_memory
    code0, _, _ = rotated_surface_code_from_stim(3, "Z")
    HZ = np.vstack([code0.HZ, code0.HZ[0] ^ code0.HZ[1]])
    HX = np.vstack([code0.HX, code0.HX[1] ^ code0.HX[2]])
    red = CSSCode(HX, HZ, code0.LX, code0.LZ)
    steane = CSSCode.from_checks(np.array([[1, 0, 1, 0, 1, 0, 1], [0, 1, 1, 0, 0, 1, 1], [0, 0, 0, 1, 1, 1, 1]]),
                                 np.array([[1, 0, 1, 0, 1, 0, 1], [0, 1, 1, 0, 0, 1, 1], [0, 0, 0, 1, 1, 1, 1]]))
    for code in (code0, red, steane):
        for b in "ZX":
            for builder in (build_memory, build_pipelined_memory):
                c, data = builder(code, b, 3)
                r = check_l0(c, code, b, L0Constraints(data_qubits=data, rounds=3))
                assert r.passed, r.to_text()


# ---------------------------------------------------------------------------
# N1 / N2：SI1000 的 I 门；si1000 移出打分模型
# ---------------------------------------------------------------------------

def _noise_per_qubit(c: stim.Circuit):
    from collections import Counter
    out = Counter()
    layer = 0
    for i in c.flattened():
        if i.name == "TICK":
            layer += 1
        elif stim.gate_data(i.name).is_noisy_gate and not stim.gate_data(i.name).produces_measurements:
            for t in i.targets_copy():
                out[(layer, i.name, tuple(i.gate_args_copy()), t.value)] += 1
    return out


def test_N1_identity_gate_no_longer_dodges_resonator_idle():
    """在含测量/复位的层给空闲比特写 I：si1000 下每个比特每层的噪声必须与空闲完全相同（ResonatorIdle 2p 躲不开）。"""
    from evaluators.noise import add_noise
    plain = stim.Circuit("R 0 1 2\nTICK\nH 0\nTICK\nCZ 0 1\nTICK\nM 0\nTICK\nMR 1\nTICK\nM 2")
    padded = stim.Circuit("R 0 1 2\nTICK\nH 0\nI 1 2\nTICK\nCZ 0 1\nI 2\nTICK\nM 0\nI 1 2\nTICK\nMR 1\nI 0 2\nTICK\nM 2")
    for model in ("si1000", "sd6"):
        a, b = add_noise(plain, model, 1e-3), add_noise(padded, model, 1e-3)
        assert _noise_per_qubit(a) == _noise_per_qubit(b), model


def test_N2_si1000_not_a_scoring_model():
    from evaluators.noise import SCORING_MODELS
    assert SCORING_MODELS == ("sd6",)


# ---------------------------------------------------------------------------
# L2-1：paper 边界只把复位算作制备
# ---------------------------------------------------------------------------

def _pad_identity(c: stim.Circuit, data):
    """auditor a_l2_identity_prep.pad_identity：每个数据比特第一个双比特门的前一层（它本来空闲）放一个 I。"""
    layers = [[]]
    for inst in c.flattened():
        if inst.name == "TICK":
            layers.append([])
        else:
            layers[-1].append(inst)
    first2 = {}
    for li, L in enumerate(layers):
        for inst in L:
            if stim.gate_data(inst.name).is_two_qubit_gate:
                for g in inst.target_groups():
                    for t in g:
                        if t.value in data and t.value not in first2:
                            first2[t.value] = li
    touched = [set(t.value for inst in L for t in inst.targets_copy() if t.is_qubit_target
                   and inst.name not in ("DETECTOR", "OBSERVABLE_INCLUDE", "QUBIT_COORDS")) for L in layers]
    add = {}
    for q, li in first2.items():
        if li - 1 >= 0 and q not in touched[li - 1]:
            add.setdefault(li - 1, []).append(q)
    out = stim.Circuit()
    for li, L in enumerate(layers):
        if li:
            out.append("TICK")
        for inst in L:
            out.append(inst)
        if li in add:
            out.append("I", sorted(add[li]))
    return out, sum(len(v) for v in add.values())


def _total_prior(jc):
    return sum(i.args_copy()[0] for i in jc.circuit.detector_error_model(allow_gauge_detectors=False).flattened()
               if i.type == "error")


def test_L2_1_identity_before_first_cnot_no_longer_removes_noise():
    from evaluators.l2 import build_joint_circuit
    code, data, hon = _honest(5, 5)
    pad = {}
    for b in "ZX":
        pad[b], nadd = _pad_identity(hon[b], set(data))
    assert nadd > 0
    a = build_joint_circuit(code, hon, data, p=0.005, boundary="paper")
    b = build_joint_circuit(code, pad, data, p=0.005, boundary="paper")
    assert abs(_total_prior(a) - _total_prior(b)) < 1e-9          # 旧版：I 填充后 Σ先验降 2.4%


def test_L2_1_structurally_impossible_in_template():
    """模板电路里没有 I 门，候选也无法加入任何指令。"""
    from evaluators.candidate import build_circuits
    from schedule_helpers import surface_schedule
    code, spec = surface_schedule(3)
    for c in build_circuits(spec, code, 3).values():
        assert {i.name for i in c.flattened()} <= {"R", "RX", "CX", "M", "MX", "TICK", "DETECTOR",
                                                    "OBSERVABLE_INCLUDE"}


# ---------------------------------------------------------------------------
# L0-2：冗余校验行（PI 未裁决前一律要求每轮都测）
# ---------------------------------------------------------------------------

def test_L0_2_redundant_rows_must_be_scheduled_every_round():
    """原始电路上 L0 仍会接受“冗余行从不测”（README 已知局限）；但候选只能提交调度，而模板要求每一行（含冗余行）
    都有自己的辅助比特、每轮测一次，少列一行就被拒。"""
    from evaluators.candidate import ScheduleSpec, validate_schedule
    from schedule_helpers import surface_schedule
    code0, spec0 = surface_schedule(3)
    HZ = np.vstack([code0.HZ, code0.HZ[0] ^ code0.HZ[1]])
    HX = np.vstack([code0.HX, code0.HX[1] ^ code0.HX[2]])
    red = CSSCode(HX, HZ, code0.LX, code0.LZ)
    probs = validate_schedule(ScheduleSpec(spec0.period, spec0.x_checks, spec0.z_checks), red)
    assert any("every row (including redundant rows)" in p for p in probs)
