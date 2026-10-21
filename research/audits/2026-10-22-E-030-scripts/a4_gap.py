"""A4: premises and arithmetic of the wrapping gap argument (E-024a, audited in E-024b) for c11, on the OWN encoder.
  - starts s_q independent of R (R = 1..40), dm_q <= D-1, S = max s - min s, G = max(2D + dm_max - 1, D + S + dm_max)
  - block insertion: noisy circuit(R) layer list == circuit(R-1) with D layers inserted at x, for which x
    (layer-by-layer comparison of all ops incl. noise channels; measurement-record targets compared by (qubit, k-th
    measurement of that qubit) relabelling is unnecessary because layer contents are compared as (gate, targets, args))
  - R'_w = smallest R' such that every weight-w undetected logical with gaps <= G-1 can be moved into <= R' rounds
    using the valid insertion range [lo, D R + c_hi] and the frame conditions x + D <= f1, x >= f_last + 2D - 1.
    PYTHONPATH=. uv run python research/audits/2026-10-22-E-030-scripts/a4_gap.py SPEC"""
import json
import sys

sys.path.insert(0, "research/audits/2026-10-22-E-030-scripts")
from mylib import *

d = load_spec(sys.argv[1])
D = d["period"]
st0 = None
for R in range(1, 41):
    _, st, info, _ = unroll(d, R)
    st0 = st0 or st
    assert st == st0, R
dm = {q: v[2] for q, v in info.items()}
S = max(st0.values()) - min(st0.values())
dmax = max(dm.values())
assert dmax <= D - 1
G = max(2 * D + dmax - 1, D + S + dmax)


def layers_of(R, b):
    c = memory_circuit(d, b, R, 1e-3, 1.0)
    out, cur = [], []
    for ins in c:
        if ins.name == "TICK":
            out.append(tuple(cur)); cur = []
        elif ins.name in ("DETECTOR", "OBSERVABLE_INCLUDE"):
            continue
        else:
            cur.append(str(ins))
    out.append(tuple(cur))
    return out


cuts = {}
for b in "ZX":
    for R in range(3, 16):
        A, B = layers_of(R, b), layers_of(R - 1, b)
        assert len(A) == len(B) + D
        xs = [x for x in range(len(B) + 1) if A[:x] == B[:x] and A[x + D:] == B[x:]]
        assert xs == list(range(xs[0], xs[-1] + 1))
        cuts[(b, R)] = (xs[0], xs[-1] - D * R)
los = {v[0] for v in cuts.values()}
chis = {v[1] for v in cuts.values()}
assert len(chis) == 1
lo, c_hi = max(los), chis.pop()
res = {"D": D, "S": S, "dm_max": dmax, "G": G, "lo": lo, "c_hi": c_hi, "cuts_sample": {f"{b}{R}": v for (b, R), v in cuts.items() if R in (3, 15)}}
for w in (8, 9, 10):
    span = (w - 1) * (G - 1)
    # after deleting blocks in front: f1 <= lo + D - 1;  F fits iff no block can be deleted behind it
    f_last = lo + D - 1 + span
    # a circuit with R+1 rounds admits a deletion behind F iff D(R+1) + c_hi >= f_last + 2D - 1
    Rmin = min(R for R in range(1, 200) if D * (R + 1) + c_hi >= f_last + 2 * D - 1)
    res[f"w{w}"] = {"span": span, "f_last_max": f_last, "R_prime": Rmin}
print(json.dumps(res, indent=1))
json.dump(res, open("results/E-030-audit/a4_gap.json", "w"), indent=1)
