"""Auditor: the E-031 u11 lists (results/E-031-xor-certificates/u11/u11_<kind>_w{10,11}.json) are valid extended
logicals of the auditor's own u11 extended code (own columns from u11_spec.json, release gross H/L), distinct,
closed under the 72 translations; the w10 list is the upper-bound witness for d_ext = 10."""
import json, sys
import numpy as np
sys.path.insert(0, __import__("os").path.dirname(__file__))
from alib import ROOT, col_vec, ext_code
U = ROOT / "results/E-031-xor-certificates/u11"
for kind, basis in (("X", "Z"), ("Z", "X")):
    E = ext_code("gross", ROOT / "search/experiments/e032/u11_spec.json", basis, None)
    Hc = E["Hc"].astype(int); Lc = np.array([col_vec(E, r) for r in E["L"]]).astype(int)
    for w in (10, 11):
        L = [tuple(sorted(e["columns"])) for e in json.load(open(U / f"u11_{kind}_w{w}.json"))["logicals"]]
        ok = all(len(set(s)) == w and not (Hc[:, list(s)].sum(1) % 2).any() and (Lc[:, list(s)].sum(1) % 2).any() for s in L)
        S = set(L)
        closed = all(tuple(sorted(int(P[j]) for j in s)) in S for s in L for P in E["perms"])
        print(json.dumps({"kind": kind, "w": w, "count": len(L), "distinct": len(S) == len(L), "all_logicals": ok, "closed": closed}))
