"""evaluators/noise.py 的测试。"""
from __future__ import annotations

import pytest
import stim

from evaluators.noise import (
    SI1000_SPEC,
    NoisyCircuitError,
    add_noise,
    find_noise_instructions,
    split_layers,
)

P = 1e-3


def _gen(basis: str, d: int, **noise) -> stim.Circuit:
    return stim.Circuit.generated(f"surface_code:rotated_memory_{basis.lower()}", distance=d, rounds=d, **noise)


def _canon_dem(dem: stim.DetectorErrorModel) -> dict[frozenset, float]:
    """把 DEM 归一化为 {症状集合: 合并概率}（独立机制按 XOR 合并），便于比较不同指令顺序的 DEM。"""
    out: dict[frozenset, float] = {}
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        key = frozenset(str(t) for t in inst.targets_copy() if not t.is_separator())
        p = inst.args_copy()[0]
        q = out.get(key, 0.0)
        out[key] = q * (1 - p) + p * (1 - q)
    return out


SMALL = stim.Circuit("""
    R 0 1 2
    TICK
    H 0
    TICK
    CX 0 1
    TICK
    M 0
    TICK
    I 2
    MR 1
    TICK
    MX 2
""")


# ---------------------------------------------------------------------------
# 输入校验
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "R 0\nTICK\nDEPOLARIZE1(0) 0\nTICK\nM 0",          # 概率为 0 的噪声通道也拒绝
    "R 0\nTICK\nX_ERROR(0.1) 0\nTICK\nM 0",
    "R 0\nTICK\nM(0.01) 0",                            # 测量自带翻转概率
    "R 0\nTICK\nPAULI_CHANNEL_1(0.1, 0, 0) 0\nTICK\nM 0",
    "R 0 1\nTICK\nE(0.1) X0 X1\nTICK\nM 0 1",
    "R 0\nTICK\nHERALDED_ERASE(0.1) 0\nTICK\nM 0",
    "R 0\nTICK\nI_ERROR(0.1) 0\nTICK\nM 0",
    "MPAD(0.2) 0\nTICK\nR 0",
    "R 0\nTICK\nREPEAT 2 {\n  DEPOLARIZE1(0.1) 0\n  TICK\n}\nM 0",  # 藏在 REPEAT 里
])
def test_rejects_circuits_that_already_have_noise(text):
    c = stim.Circuit(text)
    assert find_noise_instructions(c)
    with pytest.raises(NoisyCircuitError):
        add_noise(c, "uniform_depolarizing", P)


def test_rejects_stim_generated_noisy_circuit():
    with pytest.raises(NoisyCircuitError):
        add_noise(_gen("Z", 3, after_clifford_depolarization=P), "uniform_depolarizing", P)


def test_requires_ticks():
    with pytest.raises(ValueError, match="TICK"):
        add_noise(stim.Circuit("R 0 1\nCX 0 1\nM 0 1"), "uniform_depolarizing", P)


def test_rejects_qubit_used_twice_in_one_time_step():
    with pytest.raises(ValueError, match="more than once"):
        add_noise(stim.Circuit("R 0 1\nTICK\nH 0\nCX 0 1\nTICK\nM 0 1"), "uniform_depolarizing", P)


@pytest.mark.parametrize("text", ["R 0 1\nTICK\nMPP Z0*Z1", "R 0 1\nTICK\nM 0\nTICK\nCX rec[-1] 1"])
def test_unsupported_instructions(text):
    with pytest.raises(NotImplementedError):
        add_noise(stim.Circuit(text), "uniform_depolarizing", P)


def test_unknown_model_and_bad_p():
    with pytest.raises(ValueError):
        add_noise(SMALL, "made_up", P)
    with pytest.raises(ValueError):
        add_noise(SMALL, "uniform_depolarizing", -0.1)
    with pytest.raises(ValueError):
        add_noise(SMALL, "si1000", 0.5)  # 5p > 1


# ---------------------------------------------------------------------------
# uniform_depolarizing：指令数量与位置
# ---------------------------------------------------------------------------

def test_uniform_exact_placement_with_idle():
    p = 0.01
    expected = stim.Circuit(f"""
        R 0 1 2
        X_ERROR({p}) 0 1 2
        TICK
        H 0
        DEPOLARIZE1({p}) 0
        DEPOLARIZE1({p}) 1 2
        TICK
        CX 0 1
        DEPOLARIZE2({p}) 0 1
        DEPOLARIZE1({p}) 2
        TICK
        X_ERROR({p}) 0
        M 0
        DEPOLARIZE1({p}) 1 2
        TICK
        I 2
        DEPOLARIZE1({p}) 2
        X_ERROR({p}) 1
        MR 1
        X_ERROR({p}) 1
        DEPOLARIZE1({p}) 0
        TICK
        Z_ERROR({p}) 2
        MX 2
        DEPOLARIZE1({p}) 0 1
    """)
    assert add_noise(SMALL, "uniform_depolarizing", p) == expected


def test_uniform_without_idle_has_no_idle_noise():
    p = 0.01
    expected = stim.Circuit(f"""
        R 0 1 2
        X_ERROR({p}) 0 1 2
        TICK
        H 0
        DEPOLARIZE1({p}) 0
        TICK
        CX 0 1
        DEPOLARIZE2({p}) 0 1
        TICK
        X_ERROR({p}) 0
        M 0
        TICK
        I 2
        DEPOLARIZE1({p}) 2
        X_ERROR({p}) 1
        MR 1
        X_ERROR({p}) 1
        TICK
        Z_ERROR({p}) 2
        MX 2
    """)
    assert add_noise(SMALL, "uniform_depolarizing", p, idle=False) == expected


def _count_targets(c: stim.Circuit, name: str) -> int:
    return sum(len(i.targets_copy()) for i in c.flattened() if i.name == name)


@pytest.mark.parametrize("basis", ["Z", "X"])
def test_uniform_idle_noise_count_on_surface_code(basis):
    clean = _gen(basis, 3)
    used = set()
    for inst in clean.flattened():
        if inst.name not in ("TICK", "DETECTOR", "OBSERVABLE_INCLUDE", "QUBIT_COORDS", "SHIFT_COORDS"):
            used.update(t.value for t in inst.targets_copy())
    expected_idle = 0
    expected_1q = 0
    expected_2q_pairs = 0
    for layer in split_layers(clean):
        touched = set()
        for inst in layer:
            if inst.name in ("DETECTOR", "OBSERVABLE_INCLUDE", "QUBIT_COORDS", "SHIFT_COORDS"):
                continue
            qs = [t.value for t in inst.targets_copy()]
            touched.update(qs)
            if inst.name == "H":
                expected_1q += len(qs)
            if inst.name == "CX":
                expected_2q_pairs += len(qs) // 2
        expected_idle += len(used - touched)
    with_idle = add_noise(clean, "uniform_depolarizing", P, idle=True)
    no_idle = add_noise(clean, "uniform_depolarizing", P, idle=False)
    assert _count_targets(no_idle, "DEPOLARIZE1") == expected_1q
    assert _count_targets(with_idle, "DEPOLARIZE1") == expected_1q + expected_idle
    assert _count_targets(with_idle, "DEPOLARIZE2") == 2 * expected_2q_pairs
    n_meas = clean.num_measurements
    n_mr = sum(len(i.targets_copy()) for i in clean.flattened() if i.name == "MR")
    n_r = sum(len(i.targets_copy()) for i in clean.flattened() if i.name in ("R", "RX"))
    flips = _count_targets(with_idle, "X_ERROR") + _count_targets(with_idle, "Z_ERROR")
    assert flips == n_meas + n_mr + n_r  # 每次测量前一次 + 每次复位（含 MR 的复位）后一次
    assert with_idle.without_noise() == clean.flattened()


@pytest.mark.parametrize("basis", ["Z", "X"])
@pytest.mark.parametrize("d", [3, 5])
def test_uniform_no_idle_dem_equals_stim_generated(basis, d):
    """idle=False 的 uniform_depolarizing 与 stim 生成器（三个参数取 p，before_round_data_depolarization=0）
    给出完全相同的 DEM（逐机制比较概率）。"""
    ref = _gen(basis, d, after_clifford_depolarization=P, before_measure_flip_probability=P,
               after_reset_flip_probability=P)
    mine = add_noise(_gen(basis, d), "uniform_depolarizing", P, idle=False)
    a = _canon_dem(ref.detector_error_model())
    b = _canon_dem(mine.detector_error_model())
    assert a.keys() == b.keys()
    assert max(abs(a[k] - b[k]) for k in a) < 1e-15


def test_difference_from_e001_noise_model_is_before_round_data_depolarization():
    """E-001 用的 stim 口径还有 before_round_data_depolarization=p（每轮开始数据比特 DEPOLARIZE1）。
    我们的 idle=False 模型没有这一项，因此 DEM 中每个机制的概率都不大于 E-001 口径，且至少有一个严格更小。"""
    e001 = _gen("Z", 3, after_clifford_depolarization=P, before_measure_flip_probability=P,
                after_reset_flip_probability=P, before_round_data_depolarization=P)
    mine = add_noise(_gen("Z", 3), "uniform_depolarizing", P, idle=False)
    a = _canon_dem(e001.detector_error_model())
    b = _canon_dem(mine.detector_error_model())
    assert set(b) <= set(a)
    assert all(b[k] <= a[k] + 1e-15 for k in b)
    assert any(b.get(k, 0.0) < a[k] - 1e-6 for k in a)


def test_idle_noise_makes_dem_strictly_noisier():
    clean = _gen("Z", 3)
    a = _canon_dem(add_noise(clean, "uniform_depolarizing", P, idle=True).detector_error_model())
    b = _canon_dem(add_noise(clean, "uniform_depolarizing", P, idle=False).detector_error_model())
    assert set(b) <= set(a) and sum(a.values()) > sum(b.values())


def test_sd6_is_uniform_with_idle():
    assert add_noise(SMALL, "sd6", P) == add_noise(SMALL, "uniform_depolarizing", P, idle=True)
    with pytest.raises(ValueError):
        add_noise(SMALL, "sd6", P, idle=False)


# ---------------------------------------------------------------------------
# si1000
# ---------------------------------------------------------------------------

SMALL_CZ = stim.Circuit("""
    R 0 1 2
    TICK
    H 0
    TICK
    CZ 0 1
    TICK
    M 0
    TICK
    MR 1
""")


def test_si1000_rejects_non_native_two_qubit_gates():
    with pytest.raises(ValueError, match="not native"):
        add_noise(SMALL, "si1000", P)


def test_si1000_exact_placement():
    p = 0.001
    s = SI1000_SPEC
    p1, p2, pm, pr, pi, pres = (s["single_qubit_gate_depolarize1"] * p, s["two_qubit_gate_depolarize2"] * p,
                                s["measurement_flip"] * p, s["reset_flip"] * p, s["idle_depolarize1"] * p,
                                s["resonator_idle_depolarize1"] * p)
    assert (p1, p2, pm, pr, pi, pres) == pytest.approx((p / 10, p, 5 * p, 2 * p, p / 10, 2 * p))
    expected = stim.Circuit(f"""
        R 0 1 2
        X_ERROR({pr}) 0 1 2
        TICK
        H 0
        DEPOLARIZE1({p1}) 0
        DEPOLARIZE1({pi}) 1 2
        TICK
        CZ 0 1
        DEPOLARIZE2({p2}) 0 1
        DEPOLARIZE1({pi}) 2
        TICK
        X_ERROR({pm}) 0
        M 0
        DEPOLARIZE1({pi}) 1 2
        DEPOLARIZE1({pres}) 1 2
        TICK
        X_ERROR({pm}) 1
        MR 1
        X_ERROR({pr}) 1
        DEPOLARIZE1({pi}) 0 2
        DEPOLARIZE1({pres}) 0 2
    """)
    # 第 0 层是复位层：R 作用于全部比特，没有空闲比特，所以没有 ResonatorIdle
    assert add_noise(SMALL_CZ, "si1000", p) == expected


def test_si1000_resonator_idle_on_gate_qubits_option():
    c = stim.Circuit("R 0 1 2\nTICK\nCZ 0 1\nM 2")
    off = add_noise(c, "si1000", P)
    on = add_noise(c, "si1000", P, si1000_resonator_on_gate_qubits=True)
    assert _count_targets(off, "DEPOLARIZE1") == 0
    assert _count_targets(on, "DEPOLARIZE1") == 2


# ---------------------------------------------------------------------------
# gross_sd6
# ---------------------------------------------------------------------------

def test_gross_sd6_explicit_idle_and_record_flip():
    p = 0.01
    expected = stim.Circuit(f"""
        R 0 1 2
        X_ERROR({p}) 0 1 2
        TICK
        H 0
        DEPOLARIZE1({p}) 0
        TICK
        CX 0 1
        DEPOLARIZE2({p}) 0 1
        TICK
        M({p}) 0
        TICK
        I 2
        DEPOLARIZE1({p}) 2
        MR({p}) 1
        X_ERROR({p}) 1
        TICK
        MX({p}) 2
    """)
    assert add_noise(SMALL, "gross_sd6", p) == expected
    with pytest.raises(ValueError):
        add_noise(SMALL, "gross_sd6", p, idle=True)


def test_output_is_accepted_by_stim_and_preserves_noiseless_part():
    for model in ("uniform_depolarizing", "sd6", "gross_sd6"):
        noisy = add_noise(_gen("X", 3), model, P)
        noisy.detector_error_model()
        assert noisy.without_noise() == _gen("X", 3).flattened().without_noise()


def test_scoring_models_have_idle_noise_and_legacy_does_not():
    from evaluators.noise import DEFAULT_MODEL, LEGACY_MODELS, SCORING_MODELS

    c = stim.Circuit("R 0 1\nTICK\nCZ 0 1\nTICK\nH 0\nTICK\nM 0 1")  # 第 2 层比特 1 空闲
    assert DEFAULT_MODEL in SCORING_MODELS and "gross_sd6" not in SCORING_MODELS
    for m in SCORING_MODELS:
        layer2 = split_layers(add_noise(c, m, P))[2]
        assert any(i.name == "DEPOLARIZE1" and 1 in [t.value for t in i.targets_copy()] for i in layer2), m
    for m in LEGACY_MODELS:
        layer2 = split_layers(add_noise(c, m, P))[2]
        assert not any(1 in [t.value for t in i.targets_copy()] for i in layer2), m
    assert add_noise(SMALL, "legacy_no_idle", P) == add_noise(SMALL, "uniform_depolarizing", P, idle=False)
