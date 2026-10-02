"""evaluators/distance.py 的测试：上界（多方法 + 注入验证）、下界（精确方法）、L0 集成。

gross code 的回归测试标记为 slow（每个约 2 分钟，3 个进程）；`-m "not slow"` 可跳过。
"""
from __future__ import annotations

import json
import os
import re

import numpy as np
import pytest
import stim

from evaluators.codes import CSSCode, rotated_surface_code_from_stim
from evaluators.distance import Fault, lower_bound, upper_bound, verify_faults
from evaluators.l0 import L0Constraints, check_l0
from evaluators.noise import add_noise
from memory_builder import build_memory

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAST = dict(bposd_trials=60, lns_starts=6)   # 小电路用的轻量预算


def _noisy_surface(d: int, basis: str) -> stim.Circuit:
    _, _, c = rotated_surface_code_from_stim(d, basis)
    return add_noise(c, "sd6", 1e-3)


# ---------------------------------------------------------------------------
# 上界
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("basis", ["X", "Z"])
@pytest.mark.parametrize("d", [3, 5])
def test_surface_code_upper_bound_equals_d(d, basis):
    r = upper_bound(_noisy_surface(d, basis), seed=0, **FAST)
    assert r.weight == d
    assert r.witness is not None and r.witness.verified and r.witness.weight == d
    assert len(r.witness.faults) == d
    by = {m.method: m for m in r.methods}
    assert set(by) == {"graphlike", "stim_search", "bposd", "bposd_lns"}
    for m in r.methods:  # 每种方法都找到了验证通过的见证，且都不低于真实距离
        assert m.status == "ok" and m.weight == d, m
    assert r.seed == 0 and r.params["bposd_trials"] == 60


def test_upper_bound_is_deterministic_and_independent_of_workers():
    c = _noisy_surface(3, "X")
    a = upper_bound(c, seed=7, **FAST)
    b = upper_bound(c, seed=7, **FAST)
    p = upper_bound(c, seed=7, num_workers=2, **FAST)

    def strip(r):
        return [(m.method, m.status, m.weight, m.extra) for m in r.methods], r.witness.faults

    assert strip(a) == strip(b) == strip(p)


def test_methods_can_be_selected_and_stop_below():
    c = _noisy_surface(3, "Z")
    r = upper_bound(c, seed=0, methods=("bposd",), **FAST)
    assert [m.method for m in r.methods] == ["bposd", "bposd_lns"] and r.weight == 3
    r = upper_bound(c, seed=0, stop_below=4, **FAST)  # graphlike 已给出 3 < 4，其余方法跳过
    assert r.weight == 3 and r.stopped_early
    assert [m.status for m in r.methods] == ["ok", "skipped", "skipped"]
    with pytest.raises(ValueError):
        upper_bound(c, methods=("magic",))


# ---------------------------------------------------------------------------
# 注入验证
# ---------------------------------------------------------------------------

def test_witness_injection_accepts_real_and_rejects_fake_witnesses():
    flat = _noisy_surface(3, "X").flattened()
    r = upper_bound(flat, seed=0, methods=("graphlike",))
    faults = r.witness.faults
    ok, msg, flipped = verify_faults(flat, faults)
    assert ok and flipped == [0] and "0 detectors fire" in msg
    # 少一个故障：会触发 detector
    ok, msg, _ = verify_faults(flat, faults[:-1])
    assert not ok and "fires detectors" in msg
    # 同一个故障两次：互相抵消，什么都不翻转
    ok, msg, _ = verify_faults(flat, [faults[0], faults[0]])
    assert not ok and "flips no observable" in msg


def test_measurement_flip_witness_is_injected():
    c = stim.Circuit("R 0 1\nTICK\nM(0.01) 0 1\nDETECTOR rec[-1]\nOBSERVABLE_INCLUDE(0) rec[-2]")
    r = upper_bound(c, seed=0, **FAST)
    assert r.weight == 1
    (f,) = r.witness.faults
    assert f.measurement_record == 0 and f.paulis == [] and "measurement record 0" in f.describe()
    assert r.witness.verified


def _parse_e002_fault(s: str, flat: stim.Circuit) -> Fault:
    """E-002 文件里是 stim 的 CircuitErrorLocation 文本。指令序号与当前 baselines 生成的电路不一定对齐，
    所以按 (tick, 噪声指令名, 比特) 在电路里重新定位。"""
    pauli = re.search(r"flipped_pauli_product: (\S+)", s).group(1)
    tick = int(re.search(r"after (\d+) TICKs", s).group(1))
    gate = re.search(r"resolving to (\w+)\(", s).group(1)
    q = int(re.sub(r"^[XYZ]", "", pauli.split("*")[0]))
    t = 0
    for i, inst in enumerate(flat):
        if inst.name == "TICK":
            t += 1
        elif t == tick and inst.name == gate and q in [x.value for x in inst.targets_copy()]:
            return Fault(tick=tick, instruction_offset=i, gate=gate, qubits=[q], paulis=pauli.split("*"))
    raise AssertionError(f"cannot locate {gate} on {q} at tick {tick}")


def test_e002_witness_is_confirmed_by_injection():
    """E-002 的权重 10 见证（baselines 噪声口径）用本模块的注入验证独立确认。"""
    path = os.path.join(ROOT, "results", "E-002-gross-baseline", "circuit_distance_witness_X_r3.json")
    if not os.path.exists(path):
        pytest.skip("E-002 witness file not present")
    from baselines.bb_code import gross_code
    from baselines.gross import circuits
    from baselines.schedule import ibm_depth8
    w = json.load(open(path))
    code = gross_code()
    c = circuits(code, ibm_depth8(code), w["rounds"], w["basis"], 0.001).flattened()
    faults = [_parse_e002_fault(s, c) for s in w["result"]["faults"]]
    assert len(faults) == 10
    ok, msg, flipped = verify_faults(c, faults)
    assert ok, msg
    assert flipped == w["result"]["flipped_observables"]
    ok, _, _ = verify_faults(c, faults[1:])
    assert not ok
    # 位置对不上的故障必须被拒绝，而不是被静默忽略
    bad = [Fault(**{**f.__dict__, "instruction_offset": f.instruction_offset + 1}) for f in faults]
    ok, msg, _ = verify_faults(c, bad)
    assert not ok and "does not match" in msg


# ---------------------------------------------------------------------------
# 调度降低距离
# ---------------------------------------------------------------------------

def test_bad_schedule_lowers_distance_and_lower_bound_certifies_it():
    """同一个 d=3 表面码，stim 的标准调度 d_circ = 3；随意的 CNOT 顺序（tests/memory_builder）让一个
    辅助比特上的故障扩散成两个数据比特错误（hook），d_circ 降到 2。上界给出见证，下界证明恰好是 2。"""
    code, _, _ = rotated_surface_code_from_stim(3, "X")
    bad, data = build_memory(code, "X", 3)
    noisy = add_noise(bad, "sd6", 1e-3)
    r = upper_bound(noisy, seed=0, **FAST)
    assert r.weight == 2 and r.witness.verified
    assert any(f.gate == "DEPOLARIZE2" for f in r.witness.faults)
    lb = lower_bound(noisy, method="cpsat", time_limit_s=60, target=2)
    assert lb.status == "infeasible_below_target" and lb.lower_bound == 2
    assert upper_bound(_noisy_surface(3, "X"), seed=0, **FAST).weight == 3
    # L0 门槛：诊断里给出见证的具体故障（层、比特、Pauli）
    rep = check_l0(bad, code, "X", L0Constraints(data_qubits=data, rounds=3, min_circuit_distance=3))
    res = rep.get("circuit_distance")
    assert res.status == "fail" and rep.d_circ == 2
    assert "distance too low" in res.message and "DEPOLARIZE2 on [" in res.message and "injection-verified" in res.message
    assert re.search(r"tick \d+: DEPOLARIZE2 on \[\d+, \d+\] -> [XYZ]\d+", res.message)


# ---------------------------------------------------------------------------
# 下界（精确方法）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method", ["cpsat", "milp", "maxsat"])
def test_lower_bound_methods_are_exact_on_d3(method):
    r = lower_bound(_noisy_surface(3, "Z"), method=method, time_limit_s=60)
    assert r.status == "optimal" and r.lower_bound == r.upper_bound == 3 and r.exact


@pytest.mark.parametrize("method", ["cpsat", "milp"])
def test_lower_bound_target_mode(method):
    c = _noisy_surface(3, "X")
    r = lower_bound(c, method=method, time_limit_s=60, target=3)
    assert r.status == "infeasible_below_target" and r.lower_bound == 3
    r = lower_bound(c, method=method, time_limit_s=60, target=4)
    assert r.status == "feasible_below_target" and r.upper_bound == 3


def test_lower_bound_timeout_reports_partial_bound():
    r = lower_bound(_noisy_surface(5, "X"), method="maxsat", time_limit_s=0.5)
    assert r.status == "timeout" and r.lower_bound is None


# ---------------------------------------------------------------------------
# gross code 回归（E-002 / evaluator_issues 2026-10-02）
# ---------------------------------------------------------------------------

def _gross(basis: str, rounds: int):
    from baselines.bb_code import gross_code
    from baselines.gross import circuits
    from baselines.schedule import ibm_depth8
    code = gross_code()
    sched = ibm_depth8(code)
    c = circuits(code, sched, rounds, basis, 0.0)
    assert c.num_observables == 12 and not any(
        stim.gate_data(i.name).is_noisy_gate and i.gate_args_copy() for i in c.flattened())
    return code, sched, c


@pytest.mark.slow
def test_gross_code_X_3_rounds_upper_bound_at_most_10():
    """旧 L0 报 12；E-002 找到并经 auditor 验证的见证是 10。新的上界必须 ≤ 10，且见证经注入验证。"""
    _, _, c = _gross("X", 3)
    r = upper_bound(add_noise(c, "sd6", 1e-3), seed=0, num_workers=3)
    assert r.weight is not None and r.weight <= 10, r.summary()
    assert r.witness.verified and len(r.witness.faults) == r.weight
    print(f"gross X r3: d_circ <= {r.weight} in {r.seconds}s ({r.summary()})")


@pytest.mark.slow
def test_gross_code_l0_gate_rejects_threshold_11():
    """L0 的 min_circuit_distance 闸门：要求 11 时 IBM gross 电路（X 基底 3 轮）必须被拒绝。"""
    code, sched, c = _gross("X", 3)
    css = CSSCode.from_checks(np.asarray(code.HX), np.asarray(code.HZ), name="gross")
    cons = L0Constraints(data_qubits=list(sched.data), rounds=3, min_circuit_distance=11,
                         distance_num_workers=3)
    rep = check_l0(c, css, "X", cons)
    assert all(x.passed for x in rep.checks if x.name != "circuit_distance"), rep.to_text()
    res = rep.get("circuit_distance")
    assert res.status == "fail" and rep.d_circ is not None and rep.d_circ <= 10, rep.to_text()
    assert "distance too low" in res.message and "tick " in res.message and "injection-verified" in res.message
