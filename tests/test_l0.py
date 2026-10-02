"""evaluators/l0.py 的测试：正面（合法电路通过、电路级距离正确）与反面（攻击/作弊必须被拒绝）。"""
from __future__ import annotations

import numpy as np
import pytest
import stim

from evaluators.codes import CSSCode, rotated_surface_code_from_stim
from evaluators.l0 import L0Constraints, check_l0
from memory_builder import build_memory

ANNOT = ("TICK", "DETECTOR", "OBSERVABLE_INCLUDE", "QUBIT_COORDS", "SHIFT_COORDS")
# 小电路的距离搜索用轻量预算（默认预算是为 gross code 定的，见 tests/test_distance.py）
FAST_DIST = dict(distance_bposd_trials=100, distance_lns_starts=8)


def _edges(c: stim.Circuit):
    return {tuple(t.value for t in g) for i in c.flattened() if i.name in ("CX", "CZ") for g in i.target_groups()}


def _surface(d: int, basis: str = "Z", rounds: int | None = None):
    code, data, c = rotated_surface_code_from_stim(d, basis, rounds)
    cons = L0Constraints(data_qubits=data, max_qubits=c.num_qubits, allowed_edges=_edges(c),
                         rounds=d if rounds is None else rounds, **FAST_DIST)
    return code, data, c, cons


def _with(cons: L0Constraints, **kw) -> L0Constraints:
    from dataclasses import replace
    return replace(cons, **kw)


def _filtered(c: stim.Circuit, keep) -> stim.Circuit:
    out = stim.Circuit()
    for i, inst in enumerate(c.flattened()):
        if keep(i, inst):
            out.append(inst)
    return out


def _assert_rejected(report, check: str, *keywords: str):
    assert not report.passed, report.to_text()
    res = report.get(check)
    assert res.status == "fail", report.to_text()
    assert res.message and len(res.message) > 20
    for kw in keywords:
        assert kw.lower() in res.message.lower(), res.message
    text = report.to_text()
    assert f"[FAIL] {check}" in text


# ---------------------------------------------------------------------------
# 正面
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("basis", ["Z", "X"])
@pytest.mark.parametrize("d", [3, 5])
def test_stim_surface_code_passes_with_correct_circuit_distance(d, basis):
    code, data, c, cons = _surface(d, basis)
    cons = _with(cons, min_circuit_distance=d, require_opposite_type_detectors=True)
    r = check_l0(c, code, basis, cons)
    assert r.passed, r.to_text()
    assert r.d_circ == d
    assert [x.status for x in r.checks] == ["pass"] * len(r.checks)
    assert set(r.to_dict()) >= {"passed", "d_circ", "checks"}


def test_noise_stripped_stim_circuit_passes():
    code, data, c, cons = _surface(3)
    noisy = stim.Circuit.generated("surface_code:rotated_memory_z", distance=3, rounds=3,
                                   after_clifford_depolarization=1e-3, before_measure_flip_probability=1e-3,
                                   after_reset_flip_probability=1e-3, before_round_data_depolarization=1e-3)
    r = check_l0(noisy.without_noise(), code, "Z", _with(cons, min_circuit_distance=3))
    assert r.passed, r.to_text()


@pytest.mark.parametrize("name,HX,HZ,basis", [
    ("[[4,2,2]]", [[1, 1, 1, 1]], [[1, 1, 1, 1]], "Z"),
    ("[[4,2,2]]", [[1, 1, 1, 1]], [[1, 1, 1, 1]], "X"),
    ("Steane [[7,1,3]]", [[1, 0, 1, 0, 1, 0, 1], [0, 1, 1, 0, 0, 1, 1], [0, 0, 0, 1, 1, 1, 1]],
     [[1, 0, 1, 0, 1, 0, 1], [0, 1, 1, 0, 0, 1, 1], [0, 0, 0, 1, 1, 1, 1]], "Z"),
])
def test_generic_css_codes_pass(name, HX, HZ, basis):
    """接口对任意 CSS 码适用（含 k>1）。"""
    code = CSSCode.from_checks(np.array(HX), np.array(HZ), name=name)
    c, data = build_memory(code, basis, 3, detectors="both")
    r = check_l0(c, code, basis, L0Constraints(data_qubits=data, rounds=3, require_opposite_type_detectors=True,
                                                compute_distance=True))
    assert r.passed, r.to_text()
    assert r.d_circ is not None and r.d_circ >= 1


def test_redundant_stabilizer_rows_are_supported():
    """BB 码的校验矩阵有冗余行：每一行都必须被测量，冗余不影响判定。"""
    code0, _, _ = rotated_surface_code_from_stim(3, "Z")
    HZ = np.vstack([code0.HZ, code0.HZ[0] ^ code0.HZ[1]])
    HX = np.vstack([code0.HX, code0.HX[1] ^ code0.HX[2]])
    code = CSSCode(HX, HZ, code0.LX, code0.LZ)
    assert code.k == 1
    for basis in "ZX":
        c, data = build_memory(code, basis, 3, detectors="both")
        r = check_l0(c, code, basis, L0Constraints(data_qubits=data, rounds=3, require_opposite_type_detectors=True))
        assert r.passed, r.to_text()


# ---------------------------------------------------------------------------
# 反面：攻击测试
# ---------------------------------------------------------------------------

def test_attack_no_observable():
    code, data, c, cons = _surface(3)
    bad = _filtered(c, lambda i, inst: inst.name != "OBSERVABLE_INCLUDE")
    _assert_rejected(check_l0(bad, code, "Z", cons), "observables", "0 observable", "expected 1")


def test_attack_empty_observable():
    code, data, _, _ = _surface(3)
    c, data = build_memory(code, "Z", 3, observable_rows=[[]])
    _assert_rejected(check_l0(c, code, "Z", L0Constraints(data_qubits=data, rounds=3)), "observables", "empty")


def test_attack_observable_is_a_stabilizer():
    code, data, c, cons = _surface(3)
    n = code.n
    stab_cols = np.flatnonzero(code.HZ[0]).tolist()
    bad = _filtered(c, lambda i, inst: inst.name != "OBSERVABLE_INCLUDE")
    bad.append("OBSERVABLE_INCLUDE", [stim.target_rec(j - n) for j in stab_cols], 0)
    r = check_l0(bad, code, "Z", cons)
    _assert_rejected(r, "observables", "product of z-stabilizers", "trivial")
    _assert_rejected(r, "logical_injection", "not flipped")


def test_attack_observable_padded_with_ancilla_record():
    """observable = 真逻辑算符 ⊕ 一个确定的辅助比特测量（Z 型辅助比特 18 的最后一轮测量）。"""
    code, data, c, cons = _surface(3)
    bad = c.flattened()
    bad.append("OBSERVABLE_INCLUDE", [stim.target_rec(-(code.n + 2))], 0)  # MR 列表倒数第 2 个 = Z 型辅助比特 18
    assert bad.detector_error_model() is not None  # 仍然确定
    _assert_rejected(check_l0(bad, code, "Z", cons), "observables", "not final z-basis data readouts")


def test_attack_observable_uses_pauli_target():
    code, data, c, cons = _surface(3)
    bad = _filtered(c, lambda i, inst: inst.name != "OBSERVABLE_INCLUDE")
    bad.append(stim.CircuitInstruction("OBSERVABLE_INCLUDE", [stim.target_z(1)], [0]))
    _assert_rejected(check_l0(bad, code, "Z", cons), "instructions", "measurement records")


def test_attack_duplicate_observables():
    code, data, c, cons = _surface(3)
    bad = c.flattened()
    obs = [i for i in bad if i.name == "OBSERVABLE_INCLUDE"][0]
    bad.append(stim.CircuitInstruction("OBSERVABLE_INCLUDE", obs.targets_copy(), [1]))
    _assert_rejected(check_l0(bad, code, "Z", cons), "observables", "expected 1")
    _assert_rejected(check_l0(bad, code, "Z", _with(cons, num_observables=2)), "observables", "linearly dependent")


def test_attack_skip_one_stabilizer_in_one_round():
    """跳过某轮某个稳定子（detector 改为跨轮比较，仍全部确定）——必须被覆盖检查抓住。"""
    code, _, _ = rotated_surface_code_from_stim(3, "Z")
    c, data = build_memory(code, "Z", 3, skip={(1, "Z", 0)})
    r = check_l0(c, code, "Z", L0Constraints(data_qubits=data, rounds=3))
    assert r.get("determinism").passed and r.get("observables").passed
    _assert_rejected(r, "stabilizer_coverage", "z-stabilizer #0", "measured 2 time(s), required 3")


def test_attack_never_measure_opposite_type():
    """Z memory 只测 Z 型稳定子（退化成重复码，噪声更少）——必须被拒绝。"""
    code, _, _ = rotated_surface_code_from_stim(3, "Z")
    c, data = build_memory(code, "Z", 3, skip_type="X")
    _assert_rejected(check_l0(c, code, "Z", L0Constraints(data_qubits=data, rounds=3)),
                     "stabilizer_coverage", "x-stabilizer", "measured 0 time(s)")


def test_attack_fewer_rounds_than_required():
    code, data, c, cons = _surface(3, rounds=2)
    _assert_rejected(check_l0(c, code, "Z", _with(cons, rounds=3)), "stabilizer_coverage", "required 3")


def test_attack_nondeterministic_detector():
    code, data, c, cons = _surface(3)
    bad = c.flattened()
    bad.append("DETECTOR", [stim.target_rec(-(code.n + 1))])  # 最后一轮 X 型辅助比特（Z memory 中随机）
    _assert_rejected(check_l0(bad, code, "Z", cons), "determinism", "non-deterministic")


def test_attack_missing_final_detectors():
    """删掉最后一轮与数据读出的比较 detector：仍确定，但译码器拿不到这部分症状。"""
    code, data, c, cons = _surface(3)
    flat = c.flattened()
    last_m = max(i for i, inst in enumerate(flat) if inst.name == "M")
    bad = _filtered(flat, lambda i, inst: not (inst.name == "DETECTOR" and i > last_m))
    _assert_rejected(check_l0(bad, code, "Z", cons), "detector_coverage", "last round vs. final data readout")


@pytest.mark.parametrize("gate_text", ["MPP Z1*Z3", "SQRT_Y 1"])
def test_attack_disallowed_gate(gate_text):
    code, data, c, cons = _surface(3)
    bad = c.flattened()
    bad.append("TICK")
    bad += stim.Circuit(gate_text)
    _assert_rejected(check_l0(bad, code, "Z", cons), "instructions", "not in the allowed gate set")


def test_attack_mpad_fake_measurement():
    code, data, c, cons = _surface(3)
    bad = c.flattened()
    bad.append("MPAD", [0])
    bad.append("OBSERVABLE_INCLUDE", [stim.target_rec(-1)], 0)
    _assert_rejected(check_l0(bad, code, "Z", cons), "instructions", "MPAD")


def test_attack_classical_feedback():
    code, data, c, cons = _surface(3)
    bad = c.flattened()
    bad.append("TICK")
    bad.append("CX", [stim.target_rec(-1), 1])
    _assert_rejected(check_l0(bad, code, "Z", cons), "instructions", "classically controlled")


def test_attack_connectivity_violation():
    code, data, c, cons = _surface(3)
    bad = c.flattened()
    bad += stim.Circuit("TICK\nCX 1 19\nTICK\nCX 1 19")  # 两次抵消，语义不变，只是越过了耦合图
    _assert_rejected(check_l0(bad, code, "Z", cons), "connectivity", "(1, 19)")


def test_attack_too_many_qubits():
    code, data, c, cons = _surface(3)
    _assert_rejected(check_l0(c, code, "Z", _with(cons, max_qubits=c.num_qubits - 1)), "qubit_count", "limit is")


@pytest.mark.parametrize("noisy", [
    stim.Circuit.generated("surface_code:rotated_memory_z", distance=3, rounds=3, after_clifford_depolarization=1e-3),
    stim.Circuit.generated("surface_code:rotated_memory_z", distance=3, rounds=3, before_measure_flip_probability=1e-3),
])
def test_attack_circuit_brings_its_own_noise(noisy):
    code, data, _, cons = _surface(3)
    _assert_rejected(check_l0(noisy, code, "Z", cons), "instructions", "noise")


def test_attack_zero_probability_noise_instruction():
    code, data, c, cons = _surface(3)
    bad = c.flattened()
    bad.append("DEPOLARIZE1", [1], 0.0)
    _assert_rejected(check_l0(bad, code, "Z", cons), "instructions", "noise channel")


def test_attack_no_ticks():
    """去掉所有 TICK（把整个电路塞进一个时间步，逃避空闲噪声与深度计量）。"""
    code, data, c, cons = _surface(3)
    bad = _filtered(c, lambda i, inst: inst.name != "TICK")
    _assert_rejected(check_l0(bad, code, "Z", cons), "tick_structure", "tick")


def test_attack_merge_two_layers():
    """删掉两层 CX 之间的一个 TICK：同一比特在一个时间步里做两次门。"""
    code, data, c, cons = _surface(3)
    flat = c.flattened()
    cx_idx = [i for i, inst in enumerate(flat) if inst.name == "CX"]
    tick_between = cx_idx[0] + 1
    assert flat[tick_between].name == "TICK"
    bad = _filtered(flat, lambda i, inst: i != tick_between)
    _assert_rejected(check_l0(bad, code, "Z", cons), "tick_structure", "more than once")


def test_attack_destroy_logical_mid_circuit():
    """中途测量并重置数据比特：detector 与 observable 都还确定，但逻辑信息已被摧毁。"""
    code, _, _ = rotated_surface_code_from_stim(3, "Z")
    c, data = build_memory(code, "Z", 3, destroy_after_round=1)
    r = check_l0(c, code, "Z", L0Constraints(data_qubits=data, rounds=3))
    assert r.get("determinism").passed and r.get("observables").passed
    _assert_rejected(r, "logical_injection", "do not track the encoded information")


def test_attack_data_not_reset():
    """依赖 stim 的隐式 |0> 初态而不显式复位数据比特。"""
    code, _, _ = rotated_surface_code_from_stim(3, "Z")
    c, data = build_memory(code, "Z", 3)
    bad = _filtered(c, lambda i, inst: i != 0)
    _assert_rejected(check_l0(bad, code, "Z", L0Constraints(data_qubits=data, rounds=3)), "data_layout",
                     "explicitly reset")


def test_attack_wrong_readout_basis():
    """X memory 的数据比特却按 Z 基读出（observable 不再是 X 逻辑算符）。"""
    code, data, c, cons = _surface(3, "Z")
    _assert_rejected(check_l0(c, code, "X", cons), "data_layout", "x-basis measurement")


def test_attack_bad_schedule_lowers_circuit_distance():
    """合法但调度很差的电路（hook 错误方向随意）：其他检查都通过，只有电路级距离不达标。"""
    code, _, _ = rotated_surface_code_from_stim(5, "X")
    c, data = build_memory(code, "X", 5)
    r = check_l0(c, code, "X", L0Constraints(data_qubits=data, rounds=5, min_circuit_distance=5))
    assert all(x.passed for x in r.checks if x.name != "circuit_distance"), r.to_text()
    _assert_rejected(r, "circuit_distance", "distance too low", "tick")
    assert r.d_circ is not None and r.d_circ < 5


def test_distance_timeout_is_a_failure():
    code, data, c, cons = _surface(5)
    r = check_l0(c, code, "Z", _with(cons, min_circuit_distance=5, distance_timeout_s=1e-3))
    _assert_rejected(r, "circuit_distance", "did not finish")


def test_semantic_checks_skipped_after_syntax_failure():
    code, data, c, cons = _surface(3)
    r = check_l0(c, code, "Z", _with(cons, max_qubits=3))
    assert r.get("determinism").status == "skipped"
    assert "[SKIPPED] circuit_distance" in r.to_text()


# ---------------------------------------------------------------------------
# 两个基底（评估器默认口径 basis="both"）
# ---------------------------------------------------------------------------

def _surface_pair(d: int):
    code, data, cz, cons = _surface(d, "Z")
    _, _, cx, _ = _surface(d, "X")
    cons = _with(cons, allowed_edges=_edges(cz) | _edges(cx), min_circuit_distance=d)
    return code, {"Z": cz, "X": cx}, cons


@pytest.mark.parametrize("d", [3, 5])
def test_both_bases_pass(d):
    code, pair, cons = _surface_pair(d)
    r = check_l0(pair, code, "both", cons)
    assert r.passed, r.to_text()
    assert r.d_circ == d and set(r.per_basis) == {"Z", "X"}
    assert r.get("Z:observables").passed and r.get("X:circuit_distance").passed
    assert r.to_dict()["d_circ_per_basis"] == {"Z": d, "X": d}


def test_attack_sacrifice_one_basis():
    """Z 基底电路很好，X 基底电路调度差（距离掉到 3）：basis="both" 必须拒绝并指出是 X 基底。"""
    code, _, _ = rotated_surface_code_from_stim(5, "Z")
    # 两个基底用同一个构造器布局（与 stim 的比特编号不同），Z 基底的调度恰好保住距离 5
    cx, data = build_memory(code, "X", 5)
    cz, _ = build_memory(code, "Z", 5)
    cons = L0Constraints(data_qubits=data, rounds=5, min_circuit_distance=5, **FAST_DIST)
    assert check_l0(cz, code, "Z", cons).passed  # 单看 Z 基底是合格的
    r = check_l0({"Z": cz, "X": cx}, code, "both", cons)
    assert not r.passed and r.per_basis["Z"].passed and not r.per_basis["X"].passed
    _assert_rejected(r, "X:circuit_distance", "distance too low")
    assert r.d_circ < 5


def test_both_requires_two_circuits():
    code, pair, cons = _surface_pair(3)
    with pytest.raises(ValueError):
        check_l0(pair["Z"], code, "both", cons)


def test_report_is_deterministic():
    """L0 不含随机性：同一输入两次结果完全相同（除耗时）。"""
    code, pair, cons = _surface_pair(3)
    a = check_l0(pair, code, "both", cons).to_dict()
    b = check_l0(pair, code, "both", cons).to_dict()
    a.pop("elapsed_s"), b.pop("elapsed_s")
    assert a == b


def test_attack_huge_repeat_block_is_rejected_without_expanding():
    code, data, c, cons = _surface(3)
    bad = c.copy()
    bad += stim.Circuit("REPEAT 1000000000 {\n  TICK\n}")
    _assert_rejected(check_l0(bad, code, "Z", cons), "instructions", "too large")
