"""S8 可用性：逐检查自由的合法调度是否被误拒。

(a) d=3 表面码：随机逐检查自由调度（每个校验自己的 prep、窗口长度、CNOT 时间，可跨周期），周期 6..10。
    只保留无噪声电路确定（stim DEM 不报错）的；对它们跑 pipeline 用的 L0（不含距离），统计 FAIL 的检查项。
    确定 + 模板合法的电路就是合法 memory 实验，任何 L0 失败（除距离外）都是误拒。
(b) BB72 [[72,12,6]]：IBM depth-8 调度嵌入更长周期 D'，每个校验随机选 prep / meas 位置（窗口长度各不相同、可跨周期），
    CNOT 相对次序不变（所以仍然确定）。

用法：uv run python s8_free_schedules_false_reject.py [n_surface] [n_bb]
"""
import collections
import random
import sys
import time
from multiprocessing import Pool

from common import ROOT, cand, deterministic, random_free_schedule, surface  # noqa: F401
from evaluators import pipeline
from evaluators.l0 import check_l0
from evaluators.tasks import get_task, bb_matrices
from evaluators.codes import CSSCode

TASK = get_task("selftest-surface-d3-sd6-paper")


def l0_no_distance(args):
    spec_dict, code_kind, rounds = args
    code = surface(3)[0] if code_kind == "surface" else bb72()
    spec = cand.parse_schedule(spec_dict)
    t0 = time.time()
    r = check_l0(cand.build_circuits(spec, code, rounds), code, "both",
                 pipeline._l0_constraints(TASK, code, rounds, with_distance=False))
    fails = [c.name if hasattr(c, "name") else str(c) for c in []]
    d = r.to_dict()
    fails = [c["name"] for c in d["checks"] if c["status"] == "fail"]
    msg = [c["message"][:300] for c in d["checks"] if c["status"] == "fail"][:1]
    return r.passed, fails, msg, time.time() - t0


_BB = None


def bb72():
    global _BB
    if _BB is None:
        HX, HZ = bb_matrices(6, 6, ["x^3", "y", "y^2"], ["y^3", "x", "x^2"])
        _BB = CSSCode.from_checks(HX, HZ, name="bb72")
    return _BB


def bb_free(rng, Dp):
    from baselines.bb_code import BBCode
    from baselines.gross import parse_poly
    from baselines.schedule import ibm_depth8
    from schedule_helpers import from_baseline
    code = BBCode(6, 6, parse_poly(["x^3", "y", "y^2"]), parse_poly(["y^3", "x", "x^2"]))
    base = from_baseline(ibm_depth8(code))
    D = base.period
    # 把 8 个时间步嵌入 Dp 个（保持循环次序），留出空位给 prep / meas
    slots = sorted(rng.sample(range(Dp), D))
    m = {t: slots[t] for t in range(D)}
    out = []
    for checks in (base.x_checks, base.z_checks):
        lst = []
        for c in checks:
            ts = [m[t] for _, t in c.cnots]
            # 以原 prep 的映射为参照，CNOT 偏移
            p0 = m[c.prep]
            offs = sorted((t - p0) % Dp for t in ts)
            first, last = offs[0], offs[-1]
            # 新 prep：在 (last - Dp, first) 之间（循环），新 meas：在 (last, prep + Dp) 之间
            lo = last - Dp + 1
            cand_prep = [p0 + o for o in range(lo, first)]
            rng.shuffle(cand_prep)
            for pp in cand_prep:
                new_offs_last = (p0 + last - pp)
                if new_offs_last >= Dp - 1:
                    continue
                mm = rng.randint(p0 + last + 1, pp + Dp - 1)
                lst.append(cand.CheckTiming(pp % Dp, mm % Dp, tuple(sorted((a, m[t]) for a, t in c.cnots))))
                break
            else:
                return None
        out.append(tuple(lst))
    return cand.ScheduleSpec(Dp, out[0], out[1])


def main(n_surface=150, n_bb=12):
    code, _ = surface(3)
    rng = random.Random(2026)
    jobs = []
    tried = 0
    while len(jobs) < n_surface and tried < 20000:
        tried += 1
        D = rng.randint(6, 10)
        s = random_free_schedule(code, D, rng)
        if s is None or not deterministic(s, code):
            continue
        jobs.append((s.to_dict(), "surface", 3))
    print(f"(a) surface d=3: {len(jobs)} deterministic random free schedules (from {tried} random draws)")
    bjobs = []
    rng2 = random.Random(72)
    tries = 0
    bbcode = bb72()
    while len(bjobs) < n_bb and tries < 500:
        tries += 1
        s = bb_free(rng2, rng2.randint(10, 14))
        if s is None or cand.validate_schedule(s, bbcode) or not deterministic(s, bbcode):
            continue
        bjobs.append((s.to_dict(), "bb", 3))
    print(f"(b) BB72: {len(bjobs)} free-window variants of IBM depth-8 (from {tries} draws)")
    with Pool(4) as pool:
        for label, js in (("surface", jobs), ("bb72", bjobs)):
            res = pool.map(l0_no_distance, js)
            ok = sum(r[0] for r in res)
            fails = collections.Counter(f for r in res for f in r[1])
            print(f"[{label}] L0 (no distance) passed {ok}/{len(res)}; failing checks: {dict(fails)}; "
                  f"median L0 time {sorted(r[3] for r in res)[len(res) // 2]:.2f}s")
            for (sd, _, _), r in zip(js, res):
                if not r[0]:
                    print("   example false reject:", r[1], r[2])
                    print("   schedule:", sd)
                    break


if __name__ == "__main__":
    a = [int(x) for x in sys.argv[1:]]
    main(*a)
