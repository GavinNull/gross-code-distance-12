"""Audit rev-g (2): recompute every ingredient of R' (SM S7) for circuit A from the evaluator's unroll and the noisy
SD6 circuit, with own code (layer strings incl. noise; insertion points by direct comparison).
    PYTHONPATH=.:tests uv run python research/audits/2026-10-14-revg-scripts/g3_rprime.py
"""
import json, sys
sys.path.insert(0, "tests")
from evaluators.tasks import build_code, get_task
from evaluators.candidate import parse_schedule, build_circuits, unroll
from evaluators.noise import add_noise

code, _ = build_code(get_task("gross-dcirc"), None)
spec = parse_schedule(json.load(open("search/experiments/e024a/cs_P18_H24.json"))).canonical()
D = spec.period
res = {"D": D}
U = {R: unroll(spec, code, R) for R in (1, 2, 5, 9)}
starts = U[2].start
assert all(U[R].start == starts for R in U), "starts depend on R"
dm, last_cnot_off, first_cnot_off = {}, {}, {}
for t, lst in U[2].meas.items():
    for q, typ, j in lst:
        dm[q] = t - starts[q] - D * j
for t, lst in U[2].cnots.items():
    for pr in lst:
        for q in pr:
            if q in starts:
                j = (t - starts[q]) // D; o = t - starts[q] - D * j
                last_cnot_off[q] = max(last_cnot_off.get(q, 0), o); first_cnot_off[q] = min(first_cnot_off.get(q, 99), o)
S = max(starts.values()) - min(starts.values())
Delta = max(dm.values())
res.update(min_start=min(starts.values()), max_start=max(starts.values()), S=S, Delta=Delta, min_dm=min(dm.values()),
           max_last_cnot_offset=max(last_cnot_off.values()), min_first_cnot_offset=min(first_cnot_off.values()),
           max_first_measurement_layer=max(starts[q] + dm[q] for q in starts),
           END_minus_maxmeas={R: U[R].num_layers - max(starts[q] + D * (R - 1) + dm[q] for q in starts) for R in U})
G = max(2 * D + Delta - 1, D + S + Delta)
span = 10 * (G - 1)
res.update(G=G, G_terms=(2 * D + Delta - 1, D + S + Delta), span=span)


def layers(c):
    out, cur = [], []
    for op in c.flattened():
        if op.name == "TICK":
            out.append("\n".join(sorted(cur))); cur = []
        elif op.name not in ("DETECTOR", "OBSERVABLE_INCLUDE", "SHIFT_COORDS", "QUBIT_COORDS"):
            cur.append(str(op))
    out.append("\n".join(sorted(cur)))
    return out


cuts = {}
for basis in "ZX":
    L = {R: layers(add_noise(build_circuits(spec, code, R)[basis], "sd6", 1e-3)) for R in range(1, 9)}
    for R in range(2, 9):
        a, b = L[R - 1], L[R]
        assert len(b) == len(a) + D
        xs = [x for x in range(len(a) + 1) if b[:x] == a[:x] and b[x + D:] == a[x:]]
        assert xs == list(range(xs[0], xs[-1] + 1))
        cuts[f"{basis}{R}"] = (xs[0], xs[-1], xs[-1] - D * (R - 1))
res["cuts(lo,hi,hi-18(R-1))"] = cuts
lo = max(v[0] for v in cuts.values() if True)
f1max = lo + D - 1
f11max = f1max + span
res.update(lo=lo, f1max=f1max, f11max=f11max)
for name, back in (("2D-2", 2 * D - 2), ("2D-1", 2 * D - 1)):
    # largest R with 18(R-1) < f11max + back  (no admissible back cut)
    R = 1
    while D * R < f11max + back:   # D*((R+1)-1) < bound -> R+1 still stuck
        R += 1
    res[f"Rprime_{name}"] = R
    res[f"check_{name}"] = (D * (R - 1), f11max + back, D * R)
print(json.dumps(res, indent=1))
json.dump(res, open("research/audits/2026-10-14-revg-scripts/g3_rprime.json", "w"), indent=1)
