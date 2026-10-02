"""S8b：同 s8 (b)，但在 gross 任务的码上（[[144,12,12]]，HX/HZ 各 6 个冗余行），并给出过度计数的原因：
被多数出来的那个窗口里是哪些测量（是否恰好是“其他行之和 = 该行”的冗余组合）。

用法：uv run python s8b_gross_free_windows.py [n]
"""
import random
import sys
import time

import numpy as np

from common import cand, deterministic
from evaluators import pipeline
from evaluators.l0 import check_l0
from evaluators.tasks import build_code, get_task

import s8_free_schedules_false_reject as s8


def gross_free(rng, Dp):
    from baselines.bb_code import BBCode
    from baselines.gross import parse_poly
    from baselines.schedule import ibm_depth8
    from schedule_helpers import from_baseline
    code = BBCode(12, 6, parse_poly(["x^3", "y", "y^2"]), parse_poly(["y^3", "x", "x^2"]))
    base = from_baseline(ibm_depth8(code))
    D = base.period
    slots = sorted(rng.sample(range(Dp), D))
    m = {t: slots[t] for t in range(D)}
    out = []
    for checks in (base.x_checks, base.z_checks):
        lst = []
        for c in checks:
            p0 = m[c.prep]
            offs = sorted((m[t] - p0) % Dp for _, t in c.cnots)
            first, last = offs[0], offs[-1]
            opts = [p0 + o for o in range(last - Dp + 1, first)]
            rng.shuffle(opts)
            for pp in opts:
                if p0 + last - pp >= Dp - 1:
                    continue
                mm = rng.randint(p0 + last + 1, pp + Dp - 1)
                lst.append(cand.CheckTiming(pp % Dp, mm % Dp, tuple(sorted((a, m[t]) for a, t in c.cnots))))
                break
            else:
                return None
        out.append(tuple(lst))
    return cand.ScheduleSpec(Dp, out[0], out[1])


def main(n=4):
    task = get_task("gross-sd6-p4e-3")
    code, _ = build_code(task, None)
    rng = random.Random(144)
    k = 0
    while k < n:
        s = gross_free(rng, rng.randint(10, 12))
        if s is None or cand.validate_schedule(s, code) or not deterministic(s, code, 2):
            continue
        k += 1
        t0 = time.time()
        r = check_l0(cand.build_circuits(s, code, 3), code, "both",
                     pipeline._l0_constraints(task, code, 3, with_distance=False))
        fails = {c["name"]: c["message"][:220] for c in r.to_dict()["checks"] if c["status"] == "fail"}
        print(f"gross free-window variant {k} (period {s.period}): L0 passed={r.passed} ({time.time() - t0:.1f}s)")
        for name, msg in list(fails.items())[:2]:
            print(f"   FAIL {name}: {msg}")
        if not r.passed and k == 1:
            # 解释：被多计的 X 行 = 同一测量层的其他行之和？
            meas_x = {i: c.meas for i, c in enumerate(s.x_checks)}
            HX = code.HX.astype(np.uint8)
            for i in range(HX.shape[0]):
                others = [j for j in range(HX.shape[0]) if j != i and meas_x[j] != meas_x[i]]
                A = HX[others].T.astype(np.int64)
                # 求解 A x = HX[i] (GF2)：用 galois-free 的高斯消元
                M = np.concatenate([A % 2, HX[i][:, None]], axis=1) % 2
                rows, cols = M.shape
                piv = 0
                for col in range(cols - 1):
                    pr = next((r_ for r_ in range(piv, rows) if M[r_, col]), None)
                    if pr is None:
                        continue
                    M[[piv, pr]] = M[[pr, piv]]
                    for r_ in range(rows):
                        if r_ != piv and M[r_, col]:
                            M[r_] ^= M[piv]
                    piv += 1
                consistent = not any(M[r_, -1] and not M[r_, :-1].any() for r_ in range(rows))
                if consistent:
                    print(f"   X row {i} (meas t={meas_x[i]}) is a GF(2) sum of rows measured at other time steps "
                          f"-> an extra disjoint 'window' for it")
                    break


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 4)
