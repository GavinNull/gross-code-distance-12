"""Is there a data permutation mapping the X-check set onto the Z-check set (so X-side and Z-side single-check
distributions must coincide)?  Candidate: L g -> R (-g), R g -> L (-g)."""
import sys, json
sys.path.insert(0, "research/audits/2026-10-03-E-005-scripts")
from audext import *
out = {}
for name in ["bb90", "bb108", "gross"]:
    c = Code(name); l, m, n2 = c.l, c.m, c.n2
    neg = lambda g: ((-(g // m)) % l) * m + ((-(g % m)) % m)
    p = np.empty(c.n, dtype=int)
    for g in range(n2):
        p[g] = n2 + neg(g); p[n2 + g] = neg(g)
    Xrows = {frozenset(int(p[j]) for j in np.nonzero(c.HX[i])[0]) for i in range(n2)}
    Zrows = {frozenset(int(j) for j in np.nonzero(c.HZ[i])[0]) for i in range(n2)}
    ok = Xrows == Zrows
    Zimg = {frozenset(int(p[j]) for j in np.nonzero(c.HZ[i])[0]) for i in range(n2)}
    Xset = {frozenset(int(j) for j in np.nonzero(c.HX[i])[0]) for i in range(n2)}
    out[name] = {"X_to_Z": ok, "Z_to_X": Zimg == Xset}
    print(name, out[name])
json.dump(out, open("results/E-005-audit/t6_xz_symmetry.json", "w"))
