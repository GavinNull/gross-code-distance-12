"""evaluators/l2.py 的测试：联合电路构造的正确性、表面码采样数量级、联合采样的一致性、种子可复现性。"""
from __future__ import annotations

import numpy as np
import pytest
import sinter
import stim
from memory_builder import build_memory, build_pipelined_memory

from evaluators.codes import CSSCode, rotated_surface_code_from_stim
from evaluators.l2 import (
    DecoderConfig,
    StopRule,
    _BatchRunner,
    build_joint_circuit,
    diff_per_round,
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
    # 制备 = 复位 + I（L0 允许），paper 口径可以，noisy 口径拒绝。
    # 评估器 v2（auditor G1 L2-1）：复位之后的单比特门属于主体（带噪声），所以两个基底复位之后的门必须相同；
    # 旧测试里 X 用 R + H、Z 用 R + I 的组合现在被“主体不同”拒绝（见下）。
    cx, _ = build_memory(code, "X", 1)
    cx2 = stim.Circuit(str(cx).replace("RX 0 1 2 3\nTICK", "RX 0 1 2 3\nTICK\nI 0 1 2 3\nTICK", 1))
    cx3 = stim.Circuit(str(cx).replace("RX 0 1 2 3\nTICK", "R 0 1 2 3\nTICK\nH 0 1 2 3\nTICK", 1))
    cz2 = stim.Circuit(str(cz).replace("R 0 1 2 3\nTICK", "R 0 1 2 3\nTICK\nI 0 1 2 3\nTICK", 1))
    jc = build_joint_circuit(code, {"Z": cz2, "X": cx2}, data, p=0.002, boundary="paper")
    jc.circuit.detector_error_model()
    with pytest.raises(ValueError, match="single"):
        build_joint_circuit(code, {"Z": cz2, "X": cx2}, data, p=0.002, boundary="noisy")
    with pytest.raises(ValueError, match="differ"):
        build_joint_circuit(code, {"Z": cz2, "X": cx3}, data, p=0.002, boundary="paper")


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



# ---------------------------------------------------------------------------
# boundary="flat" 与 boundary="diff"（README §7.2）
# ---------------------------------------------------------------------------

def test_flat_boundary_strips_data_idle_outside_cnot_window():
    """flat ⊂ paper：只多去掉数据比特在第一个双比特门之前、最后一个之后的单比特噪声；流水电路去掉得更多。"""
    code, _, _ = rotated_surface_code_from_stim(3, "Z")
    circs = {b: build_pipelined_memory(code, b, 3)[0] for b in "ZX"}
    data = list(range(code.n))
    paper = build_joint_circuit(code, circs, data, p=0.004, boundary="paper")
    flat = build_joint_circuit(code, circs, data, p=0.004, boundary="flat")
    assert paper.info["stripped_flat_noise_targets"] == 0 and flat.info["stripped_flat_noise_targets"] > 0
    flat.circuit.detector_error_model()
    mp = split_dem(paper.circuit.detector_error_model(), paper.num_detectors_z, paper.num_observables_z)
    mf = split_dem(flat.circuit.detector_error_model(), flat.num_detectors_z, flat.num_observables_z)
    for b in "ZX":
        assert sum(mf[b].values()) < sum(mp[b].values())
        assert set(mf[b]) <= set(mp[b])


def test_flat_boundary_reproduces_auditor_trim_on_gross():
    """auditor E-003 §3 的“拉平”变体：Strikis 去掉 720 个数据空闲位置、IBM 288 个，Z 基底 DEM Σ先验
    62.02 → 58.28、60.22 → 57.85（noisy 口径 → 拉平）。"""
    pytest.importorskip("baselines.bb_code")
    from baselines.bb_code import BBCode
    from baselines.circuit import memory_circuit, pipelined_memory_circuit
    from baselines.gross import parse_poly
    from baselines.schedule import ibm_depth8
    from baselines.strikis import strikis_fig12
    code = BBCode(12, 6, parse_poly(["x^3", "y", "y^2"]), parse_poly(["y^3", "x", "x^2"]))
    css = CSSCode.from_checks(code.HX, code.HZ)
    expect = {"ibm": (288, 60.22, 57.85), "strikis": (720, 62.02, 58.28)}
    for name, (sched, gen) in {"ibm": (ibm_depth8(code), memory_circuit),
                               "strikis": (strikis_fig12(code)[0], pipelined_memory_circuit)}.items():
        circs = {b: gen(sched, code.HX, code.HZ, code.logical_z() if b == "Z" else code.logical_x(), 12, b, 0.0)
                 for b in "ZX"}
        mass = {}
        for bnd in ("noisy", "flat"):
            jc = build_joint_circuit(css, circs, sched.data, p=0.005, boundary=bnd)
            mass[bnd] = sum(split_dem(jc.circuit.detector_error_model(), jc.num_detectors_z,
                                      jc.num_observables_z)["Z"].values())
            if bnd == "flat":
                assert jc.info["stripped_flat_noise_targets"] == expect[name][0]
        assert mass["noisy"] == pytest.approx(expect[name][1], abs=0.006)
        assert mass["flat"] == pytest.approx(expect[name][2], abs=0.006)


def test_diff_per_round_closed_form_and_interval():
    """k=1：eps 满足 (log(1-2P2) - log(1-2P1))/(r2-r1) = log(1-2eps)；95% 剖面似然区间与 delta 法接近；
    K 很大时退化为存活率之比。"""
    import math
    d = diff_per_round(100, 1000, 4, 200, 1000, 12, likelihood_factor=math.exp(1.96 ** 2 / 2))
    D = math.log(1 - 0.4) - math.log(1 - 0.2)
    assert d["best"] == pytest.approx((1 - math.exp(D / 8)) / 2, rel=1e-12)
    s = math.sqrt((2 / 0.6) ** 2 * 0.2 * 0.8 / 1000 + (2 / 0.8) ** 2 * 0.1 * 0.9 / 1000)
    assert d["low"] == pytest.approx((1 - math.exp((D + 1.96 * s) / 8)) / 2, rel=0.05)
    assert d["high"] == pytest.approx((1 - math.exp((D - 1.96 * s) / 8)) / 2, rel=0.05)
    big = diff_per_round(100, 1000, 4, 200, 1000, 12, num_observables=24)
    assert big["best"] == pytest.approx(1 - (0.8 / 0.9) ** (1 / 8), rel=1e-6)
    assert big["low"] < big["best"] < big["high"]
    neg = diff_per_round(50, 1000, 4, 40, 1000, 12)
    assert neg["best"] < 0 and neg["low"] == 0 and "negative" in neg["warning"]
    # 评估器 v2（auditor G1 L2-2）：区间不再倒置，负估计标记为无效
    assert neg["low"] <= neg["high"] and neg["valid"] is False and d["valid"] is True
    assert neg["high_unclipped"] < 0 or neg["high"] == neg["high_unclipped"]
    with pytest.raises(ValueError):
        diff_per_round(1, 10, 5, 1, 10, 5)


def test_diff_per_round_interval_coverage():
    """模拟：真实 eps 与边界因子已知时，95% 区间的覆盖率约 95%。"""
    import math
    rng = np.random.default_rng(1)
    eps, B, r1, r2, n = 0.01, 0.97, 4, 12, 2000
    P = lambda r: (1 - B * (1 - 2 * eps) ** r) / 2   # noqa: E731
    lf = math.exp(1.96 ** 2 / 2)
    hits = 0
    T = 200
    for _ in range(T):
        d = diff_per_round(int(rng.binomial(n, P(r1))), n, r1, int(rng.binomial(n, P(r2))), n, r2,
                           likelihood_factor=lf)
        hits += d["low_unclipped"] <= eps <= d["high"]
    assert 0.90 <= hits / T <= 0.99


def test_diff_boundary_agrees_with_paper_long_memory_on_surface_code():
    """表面码 d=3、sd6、p=0.005：diff(3, 9) 的体内每轮错误率与 paper 口径 27 轮单次实验的每轮错误率一致
    （k=1，用 (1-(1-2P)^(1/r))/2；27 轮时边界的影响已被稀释，见 README §7.2.1 的表）。"""
    code, data, _ = _surface(3)
    circ = lambda b, r: rotated_surface_code_from_stim(3, b, r)[2]   # noqa: E731
    stop = StopRule(max_shots=10 ** 6, max_errors=1500, min_sector_errors=1500, batch_size=2000)
    rd = sample_l2(code, circ, data, p=0.005, rounds=9, boundary="diff", diff_rounds=3,
                   decoder=DecoderConfig("pymatching"), seed=5, stop=stop, num_workers=2)
    assert rd.inputs["boundary"] == "diff" and rd.inputs["diff_rounds"] == [3, 9]
    assert set(rd.components) == {"3", "9"}
    rp = sample_l2(code, circ, data, p=0.005, rounds=27, boundary="paper", decoder=DecoderConfig("pymatching"),
                   seed=6, stop=stop, num_workers=2)
    for key in ("P_Z", "P_X"):
        a = rd.per_round[key]
        iv = rp.rates[key]
        f = lambda P: (1 - (1 - 2 * P) ** (1 / 27)) / 2   # noqa: E731
        lo, best, hi = f(iv["low"]), f(iv["best"]), f(iv["high"])
        assert a["low"] <= a["best"] <= a["high"]
        assert a["low"] <= hi and lo <= a["high"], (key, a, (lo, best, hi))   # 3.72σ 区间重叠
        assert 0.85 < a["best"] / best < 1.15, (key, a["best"], best)
        assert 0.01 < a["best"] < 0.03
    assert rd.per_round["P_any"]["best"] > max(rd.per_round["P_Z"]["best"], rd.per_round["P_X"]["best"])


def test_diff_boundary_argument_errors():
    code, data, circs = _surface(3)
    stop = StopRule(max_shots=100, batch_size=100)
    with pytest.raises(ValueError, match="diff_rounds"):
        sample_l2(code, circs, data, p=0.001, rounds=3, boundary="diff", seed=1, stop=stop)
    with pytest.raises(ValueError, match="two round counts"):
        sample_l2(code, circs, data, p=0.001, rounds=3, boundary="diff", diff_rounds=1, seed=1, stop=stop)
    with pytest.raises(ValueError, match="0 < diff_rounds < rounds"):
        sample_l2(code, lambda b, r: circs[b], data, p=0.001, rounds=3, boundary="diff", diff_rounds=3, seed=1,
                  stop=stop)
    with pytest.raises(ValueError, match="two sample_l2 runs"):
        build_joint_circuit(code, circs, data, p=0.001, boundary="diff")
