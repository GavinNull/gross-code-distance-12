"""evaluators/l2.py 的测试：联合电路构造的正确性、表面码采样数量级、联合采样的一致性、种子可复现性。"""
from __future__ import annotations

import numpy as np
import pytest
import sinter
import stim
from memory_builder import build_memory

from evaluators.codes import CSSCode, rotated_surface_code_from_stim
from evaluators.l2 import (
    DecoderConfig,
    StopRule,
    _BatchRunner,
    build_joint_circuit,
    per_round,
    sample_l2,
    split_dem,
)
from evaluators.noise import add_noise


def _surface(d=3, rounds=None):
    code, data, cz = rotated_surface_code_from_stim(d, "Z", rounds)
    _, data_x, cx = rotated_surface_code_from_stim(d, "X", rounds)
    assert data == data_x
    return code, data, {"Z": cz, "X": cx}


def _dem_dict(dem: stim.DetectorErrorModel) -> dict:
    out = {}
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        pr = inst.args_copy()[0]
        dets = tuple(sorted(t.val for t in inst.targets_copy() if t.is_relative_detector_id()))
        obs = tuple(sorted(t.val for t in inst.targets_copy() if t.is_logical_observable_id()))
        q = out.get((dets, obs), 0.0)
        out[(dets, obs)] = q * (1 - pr) + pr * (1 - q)
    return out


def _assert_same_model(a: dict, b: dict):
    keys = set(a) | set(b)
    assert set(a) == set(b), f"{len(set(a) ^ set(b))} mechanisms differ"
    assert max(abs(a.get(k, 0) - b.get(k, 0)) for k in keys) < 1e-12


def _code_422():
    h = np.array([[1, 1, 1, 1]], dtype=np.uint8)
    return CSSCode.from_checks(h, h, name="[[4,2,2]]")


# ---------------------------------------------------------------------------
# 联合电路构造
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("model", ["sd6", "gross_sd6", "legacy_no_idle"])
def test_noisy_boundary_sector_marginals_equal_per_basis_circuits(model):
    """boundary='noisy'：联合 DEM 限制到 Z（X）sector，必须与带噪声的 Z（X）memory 电路的 DEM 逐机制相同。"""
    code, data, circs = _surface(3)
    jc = build_joint_circuit(code, circs, data, noise_model=model, p=0.004, boundary="noisy")
    m = split_dem(jc.circuit.detector_error_model(), jc.num_detectors_z, jc.num_observables_z)
    for b in "ZX":
        ref = _dem_dict(add_noise(circs[b], model, 0.004).detector_error_model())
        _assert_same_model(m[b], ref)


@pytest.mark.parametrize("rounds", [1, 3])
def test_noisy_boundary_k2_code(rounds):
    """k=2 的 [[4,2,2]] 码，测试用电路生成器（memory_builder），检查两个 observable 的映射。"""
    code = _code_422()
    cz, data = build_memory(code, "Z", rounds)
    cx, _ = build_memory(code, "X", rounds)
    circs = {"Z": cz, "X": cx}
    jc = build_joint_circuit(code, circs, data, p=0.003, boundary="noisy")
    assert jc.num_observables_z == jc.num_observables_x == 2
    m = split_dem(jc.circuit.detector_error_model(), jc.num_detectors_z, jc.num_observables_z)
    for b in "ZX":
        _assert_same_model(m[b], _dem_dict(add_noise(circs[b], "sd6", 0.003).detector_error_model()))


def test_paper_boundary_is_deterministic_and_noiseless_at_p0():
    code, data, circs = _surface(3)
    jc = build_joint_circuit(code, circs, data, p=0.0, boundary="paper")
    jc.circuit.detector_error_model()   # stim 对不确定 detector 报错
    dets, obs = jc.circuit.compile_detector_sampler(seed=1).sample(64, separate_observables=True)
    assert not dets.any() and not obs.any()
    # 参考比特与数据比特的生成元（含两类逻辑）在末尾全部被测量
    assert jc.info["num_generators_measured"] == code.n + code.k


def test_paper_boundary_strips_only_data_boundary_noise():
    """paper 口径的 sector 模型是 noisy 口径的子集：去掉的只有数据比特制备 / 读出上的机制。"""
    code, data, circs = _surface(3)
    paper = build_joint_circuit(code, circs, data, p=0.004, boundary="paper")
    noisy = build_joint_circuit(code, circs, data, p=0.004, boundary="noisy")
    assert paper.info["boundary_noise_init"] == 0 and noisy.info["boundary_noise_init"] == 2 * code.n
    assert noisy.info["boundary_noise_readout"] == 2 * code.n
    assert paper.circuit.num_detectors == noisy.circuit.num_detectors
    mp = split_dem(paper.circuit.detector_error_model(), paper.num_detectors_z, paper.num_observables_z)
    mn = split_dem(noisy.circuit.detector_error_model(), noisy.num_detectors_z, noisy.num_observables_z)
    for b in "ZX":
        assert set(mp[b]) <= set(mn[b])
        assert all(mp[b][k] <= mn[b][k] + 1e-15 for k in mp[b])
        assert any(mp[b][k] < mn[b][k] - 1e-6 for k in mp[b])


def test_mismatched_bodies_are_rejected():
    code = _code_422()
    cz, data = build_memory(code, "Z", 2)
    cx, _ = build_memory(code, "X", 2, skip={(1, "Z", 0)})
    with pytest.raises(ValueError, match="differ"):
        build_joint_circuit(code, {"Z": cz, "X": cx}, data, p=0.001)


def test_noisy_input_rejected():
    code, data, circs = _surface(3)
    noisy = stim.Circuit.generated("surface_code:rotated_memory_z", distance=3, rounds=3,
                                   after_clifford_depolarization=0.001)
    with pytest.raises(ValueError):
        build_joint_circuit(code, {"Z": noisy, "X": circs["X"]}, data, p=0.001)


def test_noisy_boundary_requires_single_reset_prep():
    code = _code_422()
    cz, data = build_memory(code, "Z", 1)
    # X 电路用 R + H 制备 |+>（L0 允许），paper 口径可以，noisy 口径拒绝
    cx, _ = build_memory(code, "X", 1)
    txt = str(cx).replace("RX 0 1 2 3\nTICK", "R 0 1 2 3\nTICK\nH 0 1 2 3\nTICK", 1)
    cx2 = stim.Circuit(txt)
    cz2 = stim.Circuit(str(cz).replace("R 0 1 2 3\nTICK", "R 0 1 2 3\nTICK\nI 0 1 2 3\nTICK", 1))
    jc = build_joint_circuit(code, {"Z": cz2, "X": cx2}, data, p=0.002, boundary="paper")
    jc.circuit.detector_error_model()
    with pytest.raises(ValueError, match="single"):
        build_joint_circuit(code, {"Z": cz2, "X": cx2}, data, p=0.002, boundary="noisy")


# ---------------------------------------------------------------------------
# 采样
# ---------------------------------------------------------------------------

def test_surface_code_magnitude_and_agreement_with_plain_sinter():
    """d=3, p=0.005, sd6：noisy 口径的 P_Z 与普通 sinter（单基底电路 + pymatching）统计一致，
    每轮错误率落在已知数量级（d=3 SD6 p=0.5% 约 1e-2 每轮，E-001 审计的含空闲噪声变体为同一量级）。"""
    code, data, circs = _surface(3)
    res = sample_l2(code, circs, data, p=0.005, rounds=3, boundary="noisy", decoder=DecoderConfig("pymatching"),
                    seed=7, stop=StopRule(max_shots=40000, max_errors=1500, batch_size=2000), num_workers=2)
    stats = sinter.collect(num_workers=2, tasks=[sinter.Task(circuit=add_noise(circs["Z"], "sd6", 0.005))],
                           decoders=["pymatching"], max_shots=40000, max_errors=800)
    s = stats[0]
    ref = s.errors / s.shots
    ours = res.rates["P_Z"]["best"]
    n1, n2 = res.counts["shots"], s.shots
    pooled = (res.counts["fail_Z"] + s.errors) / (n1 + n2)
    z = (ours - ref) / np.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    assert abs(z) < 4.5, (ours, ref, z)
    pr = res.per_round["P_any"]["best"]
    assert 3e-3 < pr < 6e-2, pr
    assert res.per_round["P_Z"]["best"] == pytest.approx(per_round(ours, 3))


def test_joint_counts_consistency_and_any_ge_max():
    code, data, circs = _surface(3)
    res = sample_l2(code, circs, data, p=0.008, rounds=3, decoder=DecoderConfig("pymatching"), seed=3,
                    stop=StopRule(max_shots=6000, batch_size=1000), num_workers=2)
    c = res.counts
    assert c["shots"] == 6000
    assert c["fail_any"] >= max(c["fail_Z"], c["fail_X"])
    assert c["fail_any"] == c["fail_Z"] + c["fail_X"] - c["fail_both"]
    r = res.rates
    assert r["P_any"]["best"] >= max(r["P_Z"]["best"], r["P_X"]["best"])
    for k in ("P_Z", "P_X", "P_any"):
        assert r[k]["low"] <= r[k]["best"] <= r[k]["high"]
        assert "LR=1000" in r[k]["label"] and "3.72σ" in r[k]["label"]
    assert res.joint["approximation"] is None
    for lib in ("stim", "sinter", "ldpc", "pymatching"):
        assert res.versions[lib]


def test_bposd_small_run_records_params():
    code, data, circs = _surface(3)
    res = sample_l2(code, circs, data, p=0.006, rounds=3,
                    decoder=DecoderConfig("bposd", {"max_iter": 50, "osd_order": 3}), seed=11,
                    stop=StopRule(max_shots=2000, batch_size=500), num_workers=2)
    eff = res.decoder["effective"]["Z"]
    assert eff["max_iter"] == 50 and eff["osd_order"] == 3 and eff["osd_method"] == "OSD_CS"
    assert res.decoder["params"]["ms_scaling_factor"] == 0.0
    assert 0 < res.rates["P_any"]["best"] < 0.5


# ---------------------------------------------------------------------------
# 可复现性
# ---------------------------------------------------------------------------

def test_batch_is_bit_reproducible():
    code, data, circs = _surface(3)
    jc = build_joint_circuit(code, circs, data, p=0.006)
    r = _BatchRunner(jc.circuit, jc.num_detectors_z, jc.num_observables_z, DecoderConfig("pymatching"))
    a, b = r.run(5, 17, 3000), r.run(5, 17, 3000)
    a.pop("cpu_s"); b.pop("cpu_s")
    assert a == b
    c = r.run(5, 18, 3000)
    assert c["bits_Z"] != a["bits_Z"] or c["bits_X"] != a["bits_X"]


def test_same_seed_same_result_independent_of_workers():
    """同 seed：1 个 worker 与 3 个 worker 的正式结果完全相同（含失败计数）；换 seed 则不同。"""
    code, data, circs = _surface(3)
    kw = dict(p=0.007, rounds=3, decoder=DecoderConfig("pymatching"),
              stop=StopRule(max_shots=50000, max_errors=400, batch_size=500))
    r1 = sample_l2(code, circs, data, seed=99, num_workers=1, **kw)
    r3 = sample_l2(code, circs, data, seed=99, num_workers=3, **kw)
    assert r1.counts == r3.counts
    assert r1.rates == r3.rates
    r_other = sample_l2(code, circs, data, seed=100, num_workers=2, **kw)
    assert r_other.counts != r1.counts


def test_stop_rule_min_sector_errors():
    code, data, circs = _surface(3)
    res = sample_l2(code, circs, data, p=0.008, rounds=3, decoder=DecoderConfig("pymatching"), seed=4,
                    stop=StopRule(max_shots=200000, max_errors=100, min_sector_errors=300, batch_size=1000),
                    num_workers=2)
    assert min(res.counts["fail_Z"], res.counts["fail_X"]) >= 300
    # 最短前缀：去掉最后一批就不满足
    assert res.counts["shots"] % 1000 == 0


def test_seed_must_be_given():
    code, data, circs = _surface(3)
    with pytest.raises(TypeError):
        sample_l2(code, circs, data, p=0.001, rounds=3, stop=StopRule(max_shots=10))   # type: ignore[call-arg]
