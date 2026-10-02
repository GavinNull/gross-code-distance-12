"""evaluators/candidate.py：调度规范、模板约束、电路生成；与 baselines 的电路逐机制对照。"""
from __future__ import annotations

import json

import numpy as np
import pytest

from evaluators.candidate import (
    ScheduleError,
    build_circuits,
    memory_circuit,
    parse_schedule,
    template_edges,
    unroll,
    validate_schedule,
)
from evaluators.codes import CSSCode
from evaluators.l0 import L0Constraints, check_l0
from evaluators.noise import add_noise
from schedule_helpers import from_baseline, max_dem_difference, surface_schedule

FAST_DIST = dict(distance_bposd_trials=100, distance_lns_starts=8)


def _gross_baseline():
    bb = pytest.importorskip("baselines.bb_code")
    from baselines.gross import parse_poly
    code = bb.BBCode(12, 6, parse_poly(["x^3", "y", "y^2"]), parse_poly(["y^3", "x", "x^2"]))
    css = CSSCode.from_checks(code.HX, code.HZ, name="gross")
    return code, css


# ---------------------------------------------------------------------------
# 与 baselines 逐机制一致（IBM 非流水、Strikis 流水）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rounds", [1, 3])
@pytest.mark.parametrize("basis", ["Z", "X"])
def test_ibm_schedule_matches_baseline_dem(basis, rounds):
    from baselines.circuit import memory_circuit as base_memory
    from baselines.schedule import ibm_depth8
    code, css = _gross_baseline()
    sched = ibm_depth8(code)
    spec = parse_schedule(json.dumps(from_baseline(sched).to_dict()))   # 走一遍 JSON
    assert validate_schedule(spec, css) == []
    L = css.LZ if basis == "Z" else css.LX
    p = 0.003
    ours = add_noise(memory_circuit(spec, css, basis, rounds), "sd6", p)
    base = base_memory(sched, code.HX, code.HZ, L, rounds, basis, p)
    diff, na, nb = max_dem_difference(ours, base)
    assert na == nb and diff < 1e-12, (diff, na, nb)
    assert ours.num_detectors == base.num_detectors and ours.num_observables == base.num_observables


@pytest.mark.parametrize("rounds", [1, 3])
@pytest.mark.parametrize("basis", ["Z", "X"])
def test_strikis_schedule_matches_baseline_dem(basis, rounds):
    from baselines.circuit import pipelined_memory_circuit
    from baselines.strikis import strikis_fig12
    code, css = _gross_baseline()
    sched, _ = strikis_fig12(code)
    spec = from_baseline(sched)
    assert validate_schedule(spec, css) == []
    # Strikis 是跨周期流水：至少有一个校验的窗口跨越周期边界
    assert any((c.meas - c.prep) % spec.period != c.meas - c.prep for c in spec.x_checks + spec.z_checks)
    L = css.LZ if basis == "Z" else css.LX
    p = 0.003
    ours = add_noise(memory_circuit(spec, css, basis, rounds), "sd6", p)
    base = pipelined_memory_circuit(sched, code.HX, code.HZ, L, rounds, basis, p)
    diff, na, nb = max_dem_difference(ours, base)
    assert na == nb and diff < 1e-12, (diff, na, nb)


def test_gross_template_circuits_pass_l0_without_distance():
    from baselines.schedule import ibm_depth8
    from baselines.strikis import strikis_fig12
    code, css = _gross_baseline()
    for spec in (from_baseline(ibm_depth8(code)), from_baseline(strikis_fig12(code)[0])):
        circ = build_circuits(spec, css, 3)
        cons = L0Constraints(data_qubits=list(range(css.n)), max_qubits=css.n + 144, rounds=3,
                             allowed_edges=template_edges(css), allowed_gates={"R", "RX", "M", "MX", "CX"})
        r = check_l0(circ, css, "both", cons)
        assert r.passed, r.to_text()


# ---------------------------------------------------------------------------
# 表面码：模板电路通过 L0，距离 = d
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("d", [3, 5])
def test_surface_template_passes_l0_with_full_distance(d):
    code, spec = surface_schedule(d)
    circ = build_circuits(spec, code, d)
    cons = L0Constraints(data_qubits=list(range(code.n)), rounds=d, min_circuit_distance=d,
                         allowed_edges=template_edges(code), **FAST_DIST)
    r = check_l0(circ, code, "both", cons)
    assert r.passed and r.d_circ == d, r.to_text()


def test_per_check_free_schedule_is_expressible():
    """逐检查自由的调度（每个校验自己的 prep / CNOT / meas 时间，不同校验窗口长度不同）。"""
    HX = np.array([[1, 0, 1, 0, 1, 0, 1], [0, 1, 1, 0, 0, 1, 1], [0, 0, 0, 1, 1, 1, 1]])
    code = CSSCode.from_checks(HX, HX.copy(), name="Steane")
    # Z 校验先做完，X 校验在后（对易），每个校验的时间各不相同
    sched = {"format": "qec-schedule/v1", "period": 12,
             "z_checks": [{"prep": 0, "meas": 5, "cnots": [[0, 1], [2, 2], [4, 3], [6, 4]]},
                          {"prep": 0, "meas": 6, "cnots": [[1, 1], [2, 3], [5, 4], [6, 5]]},
                          {"prep": 1, "meas": 7, "cnots": [[3, 2], [4, 4], [5, 5], [6, 6]]}],
             "x_checks": [{"prep": 6, "meas": 11, "cnots": [[0, 7], [2, 8], [4, 9], [6, 10]]},
                          {"prep": 7, "meas": 0, "cnots": [[1, 8], [2, 9], [5, 10], [6, 11]]},
                          {"prep": 6, "meas": 1, "cnots": [[3, 7], [4, 8], [5, 11], [6, 0]]}]}
    spec = parse_schedule(sched)
    assert validate_schedule(spec, code) == []
    circ = build_circuits(spec, code, 3)
    r = check_l0(circ, code, "both", L0Constraints(data_qubits=list(range(7)), rounds=3, compute_distance=True,
                                                   **FAST_DIST))
    assert r.passed and r.d_circ is not None and r.d_circ >= 2, r.to_text()   # 任意顺序有 hook 错误，d_circ 可能 < 3


# ---------------------------------------------------------------------------
# 模板的结构保证
# ---------------------------------------------------------------------------

def test_template_structure_every_check_every_round_and_readout_last():
    code, spec = surface_schedule(3)
    R = 4
    U = unroll(spec, code, R)
    for basis in "ZX":
        c = memory_circuit(spec, code, basis, R)
        flat = c.flattened()
        layer, per_q = 0, {}
        for inst in flat:
            if inst.name == "TICK":
                layer += 1
                continue
            if inst.name in ("DETECTOR", "OBSERVABLE_INCLUDE"):
                continue
            for g in inst.target_groups():
                for t in g:
                    per_q.setdefault(t.value, []).append((layer, inst.name))
        last_layer = layer
        for q in range(code.n):          # 数据：开头复位、最后读出、中间只有 CX
            ops = per_q[q]
            assert ops[0] == (0, "R" if basis == "Z" else "RX")
            assert ops[-1] == (last_layer, "M" if basis == "Z" else "MX")
            assert {nm for _, nm in ops[1:-1]} == {"CX"}
        for i in range(code.HX.shape[0] + code.HZ.shape[0]):   # 辅助：每轮 复位 → w 个 CX → 测量
            q = code.n + i
            names = [nm for _, nm in per_q[q]]
            w = (code.HX if i < code.HX.shape[0] else code.HZ)[i % code.HX.shape[0] if i < code.HX.shape[0]
                                                                else i - code.HX.shape[0]].sum()
            pr, ms = ("RX", "MX") if i < code.HX.shape[0] else ("R", "M")
            assert names == ([pr] + ["CX"] * int(w) + [ms]) * R
            assert max(l for l, _ in per_q[q]) < last_layer      # 读出之后没有任何辅助比特操作
    assert U.num_layers >= 1


def test_hash_is_invariant_under_global_time_shift_only():
    code, spec = surface_schedule(3)
    d = spec.to_dict()
    D = d["period"]
    shifted = json.loads(json.dumps(d))
    for typ in ("x_checks", "z_checks"):
        for c in shifted[typ]:
            c["prep"] = (c["prep"] + 2) % D
            c["meas"] = (c["meas"] + 2) % D
            c["cnots"] = [[a, (t + 2) % D] for a, t in c["cnots"]]
    s2 = parse_schedule(shifted)
    assert s2.hash() == spec.hash()
    assert str(memory_circuit(s2, code, "Z", 3)) == str(memory_circuit(spec, code, "Z", 3))
    other = json.loads(json.dumps(d))
    c0 = other["z_checks"][0]["cnots"]
    c0[0][1], c0[1][1] = c0[1][1], c0[0][1]
    assert parse_schedule(other).hash() != spec.hash()
    named = dict(d, name="whatever")
    assert parse_schedule(named).hash() == spec.hash()


# ---------------------------------------------------------------------------
# 拒绝：语法与模板约束（诊断可读）
# ---------------------------------------------------------------------------

def _bad(mutate):
    code, spec = surface_schedule(3)
    d = json.loads(json.dumps(spec.to_dict()))
    mutate(d)
    with pytest.raises(ScheduleError) as ei:
        s = parse_schedule(d)
        probs = validate_schedule(s, code)
        if probs:
            raise ScheduleError(probs)
    return str(ei.value)


@pytest.mark.parametrize("field,value", [
    ("noise", {"DEPOLARIZE1": 0}), ("rounds", 30), ("circuit", "M 0"), ("detectors", []), ("observables", []),
])
def test_reject_extra_top_level_fields(field, value):
    msg = _bad(lambda d: d.__setitem__(field, value))
    assert "unknown top-level field" in msg and field in msg


def test_reject_missing_redundant_or_any_row():
    msg = _bad(lambda d: d["z_checks"].pop())
    assert "every row (including redundant rows) must be measured every round" in msg


def test_reject_missing_and_extra_cnots():
    def m(d):
        d["z_checks"][0]["cnots"].pop()
    assert "missing CNOT" in _bad(m)

    def m2(d):
        d["z_checks"][0]["cnots"].append([d["z_checks"][0]["cnots"][0][0], 3])
    assert "more than one CNOT" in _bad(m2)


def test_reject_cnot_outside_window():
    def m(d):
        d["z_checks"][0]["meas"] = 3      # 窗口 0..3，第 4 个 CNOT 在 t=4
    assert "outside the window" in _bad(m)


def test_reject_data_collision_and_prep_eq_meas():
    def m(d):
        c0, c1 = d["z_checks"][0], d["x_checks"][0]
        shared = sorted({a for a, _ in c0["cnots"]} & {a for a, _ in c1["cnots"]})
        a = shared[0]
        t0 = dict(map(tuple, c0["cnots"]))[a]
        for e in c1["cnots"]:
            if e[0] == a:
                old = e[1]
                e[1] = t0
        for e in c1["cnots"]:     # 保持该辅助比特自己的时间步互异
            if e[0] != a and e[1] == t0:
                e[1] = old
    msg = _bad(m)
    assert "at most one operation per qubit per time step" in msg

    def m2(d):
        d["x_checks"][0]["meas"] = d["x_checks"][0]["prep"]
    assert "same time step" in _bad(m2)


@pytest.mark.parametrize("mut,kw", [
    (lambda d: d.__setitem__("period", 10_000), "period must be"),
    (lambda d: d.__setitem__("period", True), "period must be"),
    (lambda d: d["x_checks"][0].__setitem__("prep", True), "prep must be"),
    (lambda d: d["x_checks"][0].__setitem__("prep", 99), "prep must be"),
    (lambda d: d["x_checks"][0].__setitem__("gate", "H"), "fields must be exactly"),
    (lambda d: d.__setitem__("format", "v0"), "format must be"),
    (lambda d: d["x_checks"][0]["cnots"].append([0, 1, 2]), "bad CNOT entry"),
])
def test_reject_malformed(mut, kw):
    assert kw in _bad(mut)


def test_rounds_must_be_positive_int():
    code, spec = surface_schedule(3)
    for r in (0, -1, 2.0, True):
        with pytest.raises(ValueError):
            memory_circuit(spec, code, "Z", r)
