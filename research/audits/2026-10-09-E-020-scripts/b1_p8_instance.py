"""Audit E-020 b1: build the P=8 per-check start instance independently of e018/e020 code.

Source: baselines.strikis.strikis_fig12 layers (time = layer index) and the evaluator's gross-dcirc code.
Check c (0..71 X in HX row order, 72..143 Z): prep p_c, CNOT to data col q at offset k_c(q) = (t - p_c) mod 8.
Writes results/E-020-audit/p8_inst.txt: lines "c p_c q1 k1 ... q6 k6".
Also: verifies the reduction against the evaluator: spec(s) built from a start vector s (prep=s_c, cnot at s_c+k,
meas s_c+7) is legal by evaluators.candidate.validate_schedule  <=>  my conflict test, on Fig12 and 3000 random /
perturbed s-vectors.
"""
import random, sys
import numpy as np
from baselines.bb_code import gross_code
from baselines.strikis import strikis_fig12
from evaluators.candidate import CheckTiming, ScheduleSpec, validate_schedule, parse_schedule
from evaluators.tasks import build_code, get_task

code, _ = build_code(get_task("gross-dcirc"), None)
sched, meta = strikis_fig12(gross_code())
col = {q: j for j, q in enumerate(sched.data)}
D = 8
assert len(sched.layers) == D
checks = []
for typ, ancs in (("X", sched.x_checks), ("Z", sched.z_checks)):
    for q in ancs:
        tp = [t for t, L in enumerate(sched.layers) if q in (L.prep_x if typ == "X" else L.prep_z)]
        tm = [t for t, L in enumerate(sched.layers) if q in (L.meas_x if typ == "X" else L.meas_z)]
        assert len(tp) == 1 and len(tm) == 1
        cn = {}
        for t, L in enumerate(sched.layers):
            for a, b in L.cnots:
                if q in (a, b):
                    d = b if a == q else a
                    assert col[d] not in cn
                    cn[col[d]] = (t - tp[0]) % D
        assert (tm[0] - tp[0]) % D == 7 and sorted(cn.values()) == [1, 2, 3, 4, 5, 6], (typ, q)
        checks.append((typ, tp[0], cn))
# support check vs evaluator matrices
for i, (typ, p, cn) in enumerate(checks):
    H = code.HX if typ == "X" else code.HZ
    r = i if i < 72 else i - 72
    assert set(np.flatnonzero(np.asarray(H)[r]).tolist()) == set(cn), i


def spec_of(s):
    xs, zs = [], []
    for (typ, p, cn), sc in zip(checks, s):
        ct = CheckTiming(sc % D, (sc + 7) % D, tuple(sorted((q, (sc + k) % D) for q, k in cn.items())))
        (xs if typ == "X" else zs).append(ct)
    return ScheduleSpec(D, tuple(xs), tuple(zs))


def mylegal(s):
    seen = set()
    for (typ, p, cn), sc in zip(checks, s):
        for q, k in cn.items():
            key = (q, (sc + k) % D)
            if key in seen:
                return False
            seen.add(key)
    return True


if __name__ == "__main__":
    with open("results/E-020-audit/p8_inst.txt", "w") as f:
        for i, (typ, p, cn) in enumerate(checks):
            f.write(" ".join(map(str, [i, p] + [x for q in sorted(cn) for x in (q, cn[q])])) + "\n")
    s0 = [p for _, p, _ in checks]
    assert mylegal(s0) and not validate_schedule(parse_schedule(spec_of(s0).to_dict()), code)
    rng = random.Random(20261009)
    agree = nl = 0
    for it in range(3000):
        if it % 3 == 0:
            s = [rng.randrange(D) for _ in checks]
        else:
            s = list(s0)
            for _ in range(rng.choice([1, 1, 2, 3])):
                s[rng.randrange(144)] = rng.randrange(D)
        a = mylegal(s)
        b = not validate_schedule(parse_schedule(spec_of(s).to_dict()), code)
        assert a == b, s
        agree += 1; nl += a
    print("reduction agrees with evaluator validate_schedule on", agree, "vectors; legal among them:", nl)
