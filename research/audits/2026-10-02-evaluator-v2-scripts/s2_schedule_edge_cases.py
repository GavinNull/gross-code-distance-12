"""S2 调度规范边界情况（只做解析 / 模板校验 / 电路生成，不采样）。

每一项打印 ACCEPT / REJECT 与第一条诊断。期望：不合法的全部 REJECT；合法的边界（跨周期窗口等）ACCEPT。
另外检查：in-process 直接传 ScheduleSpec 对象（绕过 JSON 解析）时的行为；numpy 整数；超大周期。

用法：uv run python s2_schedule_edge_cases.py
"""
import copy
import json
import time

import numpy as np

from common import cand, circuit_hash, surface
from evaluators import pipeline
from evaluators.tasks import build_code, get_task

TASK = "selftest-surface-d3-sd6-paper"


def check(label, obj, code):
    try:
        spec = cand.parse_schedule(obj)
        probs = cand.validate_schedule(spec, code)
        if probs:
            print(f"REJECT  {label}: {probs[0][:150]}")
            return None
        # 模板展开（含防御性检查）
        cand.build_circuits(spec, code, 2)
        print(f"ACCEPT  {label}  (hash {spec.hash()[:10]})")
        return spec
    except cand.ScheduleError as e:
        print(f"REJECT  {label}: {e.problems[0][:150]}")
    except Exception as e:  # noqa: BLE001
        print(f"ERROR   {label}: {type(e).__name__}: {str(e)[:150]}")
    return None


def main():
    code, spec = surface(3)
    base = spec.to_dict()
    print("base:", json.dumps(base)[:200], "...")

    def mod(f):
        d = copy.deepcopy(base)
        f(d)
        return d

    cases = [
        ("baseline (period 6)", base),
        ("period 1", mod(lambda d: d.update(period=1))),
        ("period 65 (> MAX_PERIOD)", mod(lambda d: d.update(period=65))),
        ("period True", mod(lambda d: d.update(period=True))),
        ("period 6.0", mod(lambda d: d.update(period=6.0))),
        ("period '6'", mod(lambda d: d.update(period="6"))),
        ("prep -1", mod(lambda d: d["x_checks"][0].update(prep=-1))),
        ("meas = period", mod(lambda d: d["x_checks"][0].update(meas=6))),
        ("meas == prep", mod(lambda d: d["x_checks"][0].update(meas=0))),
        ("empty cnots", mod(lambda d: d["x_checks"][0].update(cnots=[]))),
        ("duplicate column", mod(lambda d: d["x_checks"][1]["cnots"].append(list(d["x_checks"][1]["cnots"][0])))),
        ("column outside row support", mod(lambda d: d["x_checks"][0]["cnots"].append([8, 4]))),
        ("column 10**9 (beyond n)", mod(lambda d: d["x_checks"][0]["cnots"].append([10 ** 9, 4]))),
        ("column -1", mod(lambda d: d["x_checks"][0]["cnots"].append([-1, 4]))),
        ("time step = period", mod(lambda d: d["x_checks"][0]["cnots"][0].__setitem__(1, 6))),
        ("CNOT at prep time", mod(lambda d: d["x_checks"][0]["cnots"][0].__setitem__(1, 0))),
        ("CNOT at meas time", mod(lambda d: d["x_checks"][0]["cnots"][0].__setitem__(1, 5))),
        ("CNOT as [col, t, extra]", mod(lambda d: d["x_checks"][0]["cnots"][0].append(0))),
        ("CNOT entries as bools", mod(lambda d: d["x_checks"][0]["cnots"].__setitem__(0, [True, 1]))),
        ("one X check missing", mod(lambda d: d["x_checks"].pop())),
        ("one extra (duplicated) X check", mod(lambda d: d["x_checks"].append(copy.deepcopy(d["x_checks"][0])))),
        ("X and Z lists swapped", mod(lambda d: d.update(x_checks=d["z_checks"], z_checks=d["x_checks"]))),
        ("extra top-level field 'rounds'", mod(lambda d: d.update(rounds=30))),
        ("extra check field 'basis'", mod(lambda d: d["x_checks"][0].update(basis="Z"))),
        ("format v2", mod(lambda d: d.update(format="qec-schedule/v2"))),
        ("name not string", mod(lambda d: d.update(name=5))),
        ("name 201 chars", mod(lambda d: d.update(name="a" * 201))),
        ("two checks same data same step", None),
        ("wrap-around window: shift all X checks by +3 (prep 3, meas 2)", mod(
            lambda d: [c.update(prep=3, meas=2, cnots=[[a, (t + 3) % 6] for a, t in c["cnots"]]) for c in d["x_checks"]])),
        ("JSON text with duplicate 'period' key (last wins)", json.dumps(base).replace('"period": 6', '"period": 6, "period": 7')),
        ("JSON text period 1e400", json.dumps(base).replace('"period": 6', '"period": 1e400')),
        ("numpy int64 time steps (dict built with numpy)", mod(
            lambda d: d["x_checks"][0].update(prep=np.int64(0)))),
    ]
    # 两个校验同一时间步用同一数据比特
    d = copy.deepcopy(base)
    c0 = d["x_checks"][0]["cnots"][0]
    for zc in d["z_checks"]:
        for e in zc["cnots"]:
            if e[0] == c0[0]:
                e[1] = c0[1]
    cases[[c[0] for c in cases].index("two checks same data same step")] = ("two checks same data same step", d)

    for label, obj in cases:
        check(label, obj, code)

    # ---- in-process：直接传 ScheduleSpec（parse_schedule 原样返回，不做范围检查）
    print("\n-- in-process ScheduleSpec objects (bypass JSON parsing)")
    s = cand.parse_schedule(base)
    neg = cand.ScheduleSpec(6, tuple(cand.CheckTiming(c.prep - 6, c.meas + 6, tuple((a, t + 12) for a, t in c.cnots))
                                     for c in s.x_checks), s.z_checks)
    r = check("ScheduleSpec with prep-6, meas+6, t+12 (same mod 6)", neg, code)
    if r is not None:
        same = circuit_hash(cand.build_circuits(neg, code, 3)) == circuit_hash(cand.build_circuits(s, code, 3))
        print(f"        circuit identical to baseline: {same}; hash identical: {neg.hash() == s.hash()}; "
              f"stored canonical is normalised: {neg.canonical().to_dict() == s.canonical().to_dict()}")
    for D in (2000, 20000):
        big = cand.ScheduleSpec(D, s.x_checks, s.z_checks)
        t0 = time.time()
        try:
            probs = cand.validate_schedule(big, code)
            h = big.hash()
            cand.unroll(big, code, 1)
            print(f"ACCEPT  ScheduleSpec period={D} (> MAX_PERIOD 64, only checked by the JSON parser): "
                  f"validate+hash+unroll {time.time() - t0:.1f}s")
        except Exception as e:  # noqa: BLE001
            print(f"REJECT  period={D}: {type(e).__name__} {str(e)[:100]} ({time.time() - t0:.1f}s)")
    t0 = time.time()
    task = get_task(TASK)
    code2, _ = build_code(task, None)
    rep = pipeline.evaluate(TASK, None, cand.ScheduleSpec(200, s.x_checks, s.z_checks), seed=1, submit=False)
    print(f"pipeline.evaluate(ScheduleSpec period=200) -> status {rep.status} after {time.time() - t0:.1f}s; "
          f"diagnostics {rep.diagnostics[:1]}")


if __name__ == "__main__":
    main()
