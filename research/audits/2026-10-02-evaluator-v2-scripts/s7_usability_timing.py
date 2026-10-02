"""S7 可用性：一次 L0 + 距离评估的耗时，以及诊断信息是否够搜索程序改进。

  surface d=3（自检任务预算）：L0（3 轮，不含距离）、L0+距离、完整 pipeline.evaluate（含 L2 到每 sector ≥1000 次失败）
  BB72 [[72,12,6]]（IBM depth-8 调度；任务 = gross 任务换码，门槛 6）：L0（打分轮数 6，不含距离）、3 轮距离（默认预算 /
    小预算），3 worker
  gross（可选 --gross）：L0 12 轮不含距离、3 轮距离（任务默认预算）
  诊断样例：一个确定但距离不够的表面码调度、一个模板不合法的调度，打印 Report.to_text()

用法：uv run python s7_usability_timing.py [--gross]
"""
import dataclasses
import random
import sys
import time

from common import cand, deterministic, random_free_schedule, surface
from evaluators import pipeline
from evaluators.codes import CSSCode
from evaluators.l0 import check_l0
from evaluators.tasks import bb_matrices, build_code, get_task


def timed(f):
    t0 = time.time()
    r = f()
    return r, time.time() - t0


def l0(task, code, spec, R, with_d, **over):
    cons = pipeline._l0_constraints(task, code, R, with_distance=with_d)
    cons = dataclasses.replace(cons, **over) if over else cons
    return check_l0(cand.build_circuits(spec, code, R), code, "both", cons)


def bb_schedule(l, m):
    from baselines.bb_code import BBCode
    from baselines.gross import parse_poly
    from baselines.schedule import ibm_depth8
    from schedule_helpers import from_baseline
    return from_baseline(ibm_depth8(BBCode(l, m, parse_poly(["x^3", "y", "y^2"]), parse_poly(["y^3", "x", "x^2"]))))


def main():
    st = get_task("selftest-surface-d3-sd6-paper")
    code, spec = surface(3)
    r, t = timed(lambda: l0(st, code, spec, 3, False))
    print(f"[surface d=3] L0 r=3 no distance: passed={r.passed} {t:.2f}s")
    r, t = timed(lambda: l0(st, code, spec, 3, True))
    print(f"[surface d=3] L0 r=3 + distance (task budget 100 BP-OSD / 8 LNS, 3 workers): d_circ={r.d_circ} {t:.2f}s")
    rep, t = timed(lambda: pipeline.evaluate("selftest-surface-d3-sd6-paper", None, spec.to_dict(), seed=5, submit=False))
    print(f"[surface d=3] full evaluate (L0 + distance + L2 to >=1000 failures/sector): {rep.status} {t:.1f}s; "
          f"L2 shots {rep.l2['counts']['shots']}")

    # BB72
    gt = get_task("gross-sd6-p4e-3")
    HX, HZ = bb_matrices(6, 6, ["x^3", "y", "y^2"], ["y^3", "x", "x^2"])
    bb = CSSCode.from_checks(HX, HZ, name="bb72")
    bt = dataclasses.replace(gt, task_id="audit-bb72", code_family={"kind": "bb", "fixed": {
        "l": 6, "m": 6, "A": ["x^3", "y", "y^2"], "B": ["y^3", "x", "x^2"]}},
        l0=dict(gt.l0, min_circuit_distance=6))
    bspec = bb_schedule(6, 6)
    print(f"[BB72] n={bb.n} k={bb.k} schedule period {bspec.period}")
    r, t = timed(lambda: l0(bt, bb, bspec, 6, False))
    print(f"[BB72] L0 r=6 no distance: passed={r.passed} {t:.1f}s")
    r, t = timed(lambda: l0(bt, bb, bspec, 3, False))
    print(f"[BB72] L0 r=3 no distance: passed={r.passed} {t:.1f}s")
    r, t = timed(lambda: l0(bt, bb, bspec, 3, True))
    print(f"[BB72] L0 r=3 + distance (default 1500 BP-OSD / 96 LNS, 3 workers): d_circ={r.d_circ} passed={r.passed} "
          f"{t:.1f}s")
    r, t = timed(lambda: l0(bt, bb, bspec, 3, True, distance_bposd_trials=200, distance_lns_starts=8))
    print(f"[BB72] L0 r=3 + distance (200 / 8, 3 workers): d_circ={r.d_circ} {t:.1f}s")

    if "--gross" in sys.argv:
        gcode, _ = build_code(gt, None)
        gspec = bb_schedule(12, 6)
        r, t = timed(lambda: l0(gt, gcode, gspec, 12, False))
        print(f"[gross] L0 r=12 no distance: passed={r.passed} {t:.1f}s")
        r, t = timed(lambda: l0(gt, gcode, gspec, 3, True))
        print(f"[gross] L0 r=3 + distance (task budget, 3 workers): d_circ={r.d_circ} {t:.1f}s")

    # 诊断样例
    rng = random.Random(3)
    for _ in range(5000):
        s = random_free_schedule(code, rng.randint(6, 8), rng)
        if s is None or not deterministic(s, code):
            continue
        rep = pipeline.evaluate("selftest-surface-d3-sd6-paper", None, s.to_dict(), seed=1, submit=False)
        if rep.status == "rejected_l0":
            print("\n===== diagnostic sample: deterministic schedule with low circuit distance =====")
            print(rep.to_text())
            break
    bad = spec.to_dict()
    bad["z_checks"][0]["cnots"][0][1] = bad["x_checks"][0]["cnots"][0][1]
    bad["x_checks"][1]["meas"] = 2
    rep = pipeline.evaluate("selftest-surface-d3-sd6-paper", None, bad, seed=1, submit=False)
    print("\n===== diagnostic sample: template violations =====")
    print(rep.to_text())


if __name__ == "__main__":
    main()
