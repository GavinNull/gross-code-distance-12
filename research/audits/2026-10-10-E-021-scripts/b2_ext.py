"""Audit E-021 (b2): extended-code invariance. Own extended code from cand1's per-check orders vs Fig. 12's;
check the order relation (reversal + in-pair swaps); DEM image sets (Table I) for R = 1..Rmax, both bases.
    PYTHONPATH=.:tests uv run python research/audits/2026-10-10-E-021-scripts/b2_ext.py 6
"""
import json, sys
sys.path.insert(0, "research/audits/2026-10-10-E-021-scripts")
from b_common import *

Rmax = int(sys.argv[1]) if len(sys.argv) > 1 else 6
spec = load_spec()
cxo, czo = orders(spec)
fxo, fzo = A1.xo, A1.zo
info = {}
rel = {"same": 0, "rev+swaps": 0, "other": 0}
def sets(o):
    return (frozenset(o[:2]), frozenset(o[:3]), frozenset(o[4:]))
for a, b in list(zip(cxo, fxo)) + list(zip(czo, fzo)):
    r = b[::-1]
    if a == b: rel["same"] += 1
    elif {a[0], a[1]} == {r[0], r[1]} and a[2:4] == r[2:4] and {a[4], a[5]} == {r[4], r[5]}: rel["rev+swaps"] += 1
    else: rel["other"] += 1
info["order_relation"] = rel
# (P1, T, P3) invariants: candidate's (first2, first3, last2) vs Fig12's reversed
inv_ok = all(sets(a)[0] == frozenset(b[4:]) and sets(a)[2] == frozenset(b[:2]) and sets(a)[1] == frozenset(b[3:])
             for a, b in list(zip(cxo, fxo)) + list(zip(czo, fzo)))
info["P1_T_P3_match_reversed"] = inv_ok
for kind in "XZ":
    kc = ext_keys(kind, cxo, czo); kf = ext_keys(kind, fxo, fzo)
    keys18, kidx, colsup, supkey = A2.build(kind)
    k18 = {hb.tobytes() + lb.tobytes() for hb, lb in keys18}
    info[f"ext_{kind}"] = {"N_cand": len(kc), "N_fig12": len(kf), "equal": set(kc) == set(kf),
                           "equal_E018_audit_build": set(kc) == k18}
    basis = BASIS_OF_KIND[kind]
    for R in range(1, Rmax + 1):
        g, st = dem_groups(spec, R, basis)
        info[f"dem_{basis}_R{R}"] = {**st, "subset_of_ext": set(g) <= set(kc), "equal_ext": set(g) == set(kc),
                                     "max_group": max(len(v) for v in g.values())}
        print(R, basis, info[f"dem_{basis}_R{R}"], flush=True)
print(json.dumps(info, indent=1))
json.dump(info, open(f"{OUT}/b2_ext.json", "w"), indent=1)
