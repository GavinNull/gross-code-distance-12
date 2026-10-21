"""A6: premises and arithmetic of the any-R gap argument, recomputed with the own encoder (and the insertion
property also on the evaluator's noisy circuits).
Usage: a6_anyr.py SPEC"""
import sys, json
sys.path.insert(0, "research/audits/2026-10-22-E-032-scripts")
import numpy as np, stim
from alib32 import *

spec = load_spec(sys.argv[1])
D = spec["period"]
out = {"spec": sys.argv[1], "D": D}
st0 = None
for R in range(1, 41):
    D_, st, info, nl, sg = my_unroll(spec, R)
    if st0 is None:
        st0 = st
    assert st == st0, "starts depend on R"
    END = nl          # final readout layer index
    assert END == max(st[k] + D * (R - 1) + info[k][0] for k in info) + 1
dms = {k: v[0] for k, v in info.items()}
lastc = {k: max(o for o, _ in v[1]) for k, v in info.items()}
S = max(st0.values()) - min(st0.values())
dmax = max(dms.values())
out.update(start_min=min(st0.values()), start_max=max(st0.values()), S=S, dm_min=min(dms.values()), dm_max=dmax,
           last_cnot_offset_max=max(lastc.values()), first_round_meas_max=max(st0[k] + dms[k] for k in st0))
assert dmax <= D - 1 and max(lastc.values()) <= D - 2
# END <= s(c,R-1) + S + dm_max + 1 for every c (R = 5)
R = 5
END = max(st0[k] + D * (R - 1) + dms[k] for k in st0) + 1
assert all(END <= st0[k] + D * (R - 1) + S + dmax + 1 for k in st0)


def layers(c):
    res, cur = [], []
    for op in c.flattened():
        if op.name == "TICK":
            res.append("\n".join(sorted(cur))); cur = []
        elif op.name not in ("DETECTOR", "OBSERVABLE_INCLUDE", "SHIFT_COORDS", "QUBIT_COORDS"):
            cur.append(str(op))
    res.append("\n".join(sorted(cur)))
    return res


def cuts(get, Rmax):
    L = {R: layers(get(R)) for R in range(1, Rmax + 1)}
    res = {}
    for R in range(2, Rmax + 1):
        a, b = L[R - 1], L[R]
        assert len(b) == len(a) + D
        xs = [x for x in range(len(a) + 1) if b[:x] == a[:x] and b[x + D:] == a[x:]]
        assert xs == list(range(xs[0], xs[-1] + 1))
        res[R] = (xs[0], xs[-1])
    return res


from evaluators.candidate import build_circuits, parse_schedule
from evaluators.noise import add_noise
from evaluators.tasks import build_code, get_task
ec, _ = build_code(get_task("gross-dcirc"), None)
es = parse_schedule(spec).canonical()
for basis in "ZX":
    mine = cuts(lambda R: memory_circuit(spec, basis, R), 16)
    ev = cuts(lambda R: add_noise(build_circuits(es, ec, R)[basis], "sd6", 1e-3), 12)
    out[f"cuts_mine_{basis}"] = mine
    out[f"cuts_eval_{basis}"] = ev
    los = {v[0] for v in mine.values()} | {v[0] for v in ev.values()}
    his = {v[1] - D * R for R, v in mine.items()} | {v[1] - D * R for R, v in ev.items()}
    assert len(los) == 1 and len(his) == 1, (los, his)
    out["lo"], out["c_hi_for_R_minus_1_to_R"] = los.pop(), his.pop()
lo, chi = out["lo"], out["c_hi_for_R_minus_1_to_R"]
G = max(2 * D + dmax - 1, D + S + dmax)
out["G"] = G
# R': after front deletions f1 <= lo + D - 1; span <= (w-1)(G-1); back deletion at x valid if x <= D*R + chi
# (inserting into the (R-1)-round circuit) and x >= f_last + T (T = 2D-1 as in anyr.py, or 2D-2)
for w in (10, 11):
    span = (w - 1) * (G - 1)
    flast = lo + D - 1 + span
    for T in (2 * D - 1, 2 * D - 2):
        # largest R such that NO valid cut x >= flast + T exists in circuit(R): D*R + chi < flast + T
        Rp = max(R for R in range(1, 1000) if D * R + chi < flast + T)
        out[f"Rprime_w{w}_T{T}"] = Rp
    out[f"span_w{w}"] = span
print(json.dumps(out, indent=1, default=str))
