"""评估器 v2.1 回归测试用的调度生成器（照抄 research/audits/2026-10-02-evaluator-v2-scripts/ 里 auditor 的生成方式）。

评估器本身不 import baselines / search；只有测试为了构造 IBM 式调度才 import。
"""
from __future__ import annotations

import random

import numpy as np

from evaluators import candidate as cand


def random_free_schedule(code, D, rng: random.Random, max_tries=2000):
    """auditor common.random_free_schedule：逐检查自由的随机调度（每个校验自己的 prep、窗口长度、CNOT 时间，模 D），
    满足模板约束（数据比特每步至多一个 CNOT）。不保证确定性。"""
    for _ in range(max_tries):
        used = set()
        x, z = [], []
        ok = True
        for _typ, H, out in (("X", code.HX, x), ("Z", code.HZ, z)):
            for i in range(H.shape[0]):
                supp = [int(c) for c in np.flatnonzero(H[i])]
                w = len(supp)
                if w + 2 > D:
                    return None
                placed = False
                for _ in range(200):
                    prep = rng.randrange(D)
                    dm = rng.randint(w + 1, D - 1)
                    offs = rng.sample(range(1, dm), w)
                    cols = supp[:]
                    rng.shuffle(cols)
                    ts = [(prep + o) % D for o in offs]
                    if any((t, c) in used for t, c in zip(ts, cols)):
                        continue
                    for t, c in zip(ts, cols):
                        used.add((t, c))
                    out.append(cand.CheckTiming(prep, (prep + dm) % D, tuple(sorted(zip(cols, ts)))))
                    placed = True
                    break
                if not placed:
                    ok = False
                    break
            if not ok:
                break
        if ok:
            return cand.ScheduleSpec(D, tuple(x), tuple(z))
    return None


def deterministic(spec, code, rounds=2) -> bool:
    try:
        for b in "ZX":
            cand.memory_circuit(spec, code, b, rounds).detector_error_model(allow_gauge_detectors=False)
        return True
    except ValueError:
        return False


def shifted(spec, s):
    D = spec.period
    return cand.ScheduleSpec(D, tuple(cand._shift(c, s, D) for c in spec.x_checks),
                             tuple(cand._shift(c, s, D) for c in spec.z_checks))


def ibm_spec(l, m, A, B):
    """IBM depth-8 调度（baselines.schedule.ibm_depth8）转成 ScheduleSpec。A、B 为 baselines 的项列表。"""
    from baselines.bb_code import BBCode
    from baselines.gross import parse_poly
    from baselines.schedule import ibm_depth8
    from schedule_helpers import from_baseline
    return from_baseline(ibm_depth8(BBCode(l, m, parse_poly(A), parse_poly(B))))


# E-004 的码构造（search/proxy/candidates.py::_code，项的顺序决定 IBM 项顺序调度）
_E004_CODES = {
    "bb72-dcirc": ("bb", 6, 6, "x^3+y+y^2", "y^3+x+x^2"),
    "bb90-dcirc": ("bb", 15, 3, "x^9+y+y^2", "1+x^2+x^7"),
    "bb108-dcirc": ("bb", 9, 6, "x^3+y+y^2", "y^3+x+x^2"),
    "bb120-dcirc": ("bb", 20, 3, "1+x^3y^2+x^7y^2", "1+x^16y+x^9y"),
    "cp126-dcirc": ("coprime", 7, 9, (0, 1, 58), (0, 13, 41)),
    "gross-dcirc": ("bb", 12, 6, "x^3+y+y^2", "y^3+x+x^2"),
}


def dcirc_ibm_spec(task_id):
    """E-004 的 IBM 项顺序调度（search.codes.schedule.default_schedule）转成 ScheduleSpec，并核对 search 构造的
    校验矩阵与评估器任务的码逐元素相同。返回 (code, spec)。"""
    from search.codes.construct import bb_code, coprime_bb_code
    from search.codes.schedule import default_schedule
    from schedule_helpers import from_baseline
    from evaluators.tasks import build_code, get_task
    kind, l, m, A, B = _E004_CODES[task_id]
    sc = bb_code(l, m, A, B) if kind == "bb" else coprime_bb_code(l, m, A, B)
    css = sc.to_css()
    code, _ = build_code(get_task(task_id), None)
    assert np.array_equal(css.HX, code.HX) and np.array_equal(css.HZ, code.HZ), task_id
    return code, from_baseline(default_schedule(sc))


def free_window_variant(base: cand.ScheduleSpec, rng: random.Random, Dp: int):
    """auditor s8 bb_free / s8b gross_free：把 IBM depth-8 的 8 个时间步嵌入更长的周期 Dp（保持循环次序），
    每个校验随机选 prep / meas（窗口长度各不相同、可跨周期），CNOT 相对次序不变（所以仍然确定）。"""
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


def auditor_bb72_variants(n=12):
    """auditor s8 (b) 的 12 个 BB72 自由窗口变体（random.Random(72)，周期 10..14）。"""
    from evaluators.codes import CSSCode
    from evaluators.tasks import bb_matrices
    HX, HZ = bb_matrices(6, 6, ["x^3", "y", "y^2"], ["y^3", "x", "x^2"])
    code = CSSCode.from_checks(HX, HZ, name="bb72")
    base = ibm_spec(6, 6, ["x^3", "y", "y^2"], ["y^3", "x", "x^2"])
    rng2 = random.Random(72)
    out, tries = [], 0
    while len(out) < n and tries < 500:
        tries += 1
        s = _bb_free_s8(base, rng2, rng2.randint(10, 14))
        if s is None or cand.validate_schedule(s, code) or not deterministic(s, code):
            continue
        out.append(s)
    return code, out


def _bb_free_s8(base, rng, Dp):
    """s8 的 bb_free（与 free_window_variant 的随机数消耗顺序完全相同，为了复现 auditor 的 12 个调度单列）。"""
    D = base.period
    slots = sorted(rng.sample(range(Dp), D))
    m = {t: slots[t] for t in range(D)}
    out = []
    for checks in (base.x_checks, base.z_checks):
        lst = []
        for c in checks:
            ts = [m[t] for _, t in c.cnots]
            p0 = m[c.prep]
            offs = sorted((t - p0) % Dp for t in ts)
            first, last = offs[0], offs[-1]
            lo = last - Dp + 1
            cand_prep = [p0 + o for o in range(lo, first)]
            rng.shuffle(cand_prep)
            for pp in cand_prep:
                if p0 + last - pp >= Dp - 1:
                    continue
                mm = rng.randint(p0 + last + 1, pp + Dp - 1)
                lst.append(cand.CheckTiming(pp % Dp, mm % Dp, tuple(sorted((a, m[t]) for a, t in c.cnots))))
                break
            else:
                return None
        out.append(tuple(lst))
    return cand.ScheduleSpec(Dp, out[0], out[1])


def auditor_gross_variants(n=3):
    """auditor s8b 的 gross 自由窗口变体（random.Random(144)，周期 10..12；第 1 个原来被误拒）。"""
    from evaluators.tasks import build_code, get_task
    code, _ = build_code(get_task("gross-sd6-p4e-3"), None)
    base = ibm_spec(12, 6, ["x^3", "y", "y^2"], ["y^3", "x", "x^2"])
    rng = random.Random(144)
    out = []
    while len(out) < n:
        s = free_window_variant(base, rng, rng.randint(10, 12))
        if s is None or cand.validate_schedule(s, code) or not deterministic(s, code, 2):
            continue
        out.append(s)
    return code, out
