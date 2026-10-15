"""A3b: exact "no undetected logical of weight <= W" on the own-encoder DEM, with a rigorous translation case split.
The circuit is invariant under the 45 translations (checked in a2: one (label,time) signature per check type), so the
set of DEM detector-sets is invariant under the induced detector permutation (asserted here).  DEM columns are
identified by their detector set (asserted: no two columns share a detector set, no detector-free column flips an
observable -- otherwise d_circ <= 2).  Any solution F, translated so that its column of smallest orbit index k becomes
that orbit's representative, is a solution containing rep_k and no column of orbits < k.  So the cases k = 0..#orbits-1
(assumptions: rep_k = 1, earlier orbits = 0) are exhaustive.
Usage: a3b_dcirc_symsat.py SPEC BASIS W R [case_lo case_hi]"""
import sys, time, json
sys.path.insert(0, "research/audits/2026-10-15-E-028-scripts")
from alib import *
from pysat.card import CardEnc, EncType
from pysat.solvers import Solver
from a3_dcirc_sat import build_cnf

spec_path, basis, W, R = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
spec = load_spec(spec_path)
cols, nd, no = dem_matrix(memory_circuit(spec, basis, R))
assert nd == N2 * (R + 1)
bydet = {}
for j, (d, o) in enumerate(cols):
    assert d, "detector-free column flips an observable"
    assert d not in bydet, "two columns share a detector set"
    bydet[d] = j
def perm(ga, gb):
    p = []
    for x in range(nd):
        r, i = divmod(x, N2)
        a, b = divmod(i, M_)
        p.append(r * N2 + ((a + ga) % L_) * M_ + (b + gb) % M_)
    return p
G = [perm(ga, gb) for ga in range(L_) for gb in range(M_)]
orb = [-1] * len(cols); reps = []
for j, (d, o) in enumerate(cols):
    imgs = [bydet[frozenset(p[x] for x in d)] for p in G]   # KeyError => not invariant
    if orb[j] < 0:
        for i2 in imgs: orb[i2] = len(reps)
        reps.append(j)
nor = len(reps)
lo, hi = (int(sys.argv[5]), int(sys.argv[6])) if len(sys.argv) > 6 else (0, nor)
cls, nv = build_cnf(cols, nd, no, W)
res = {"spec": spec_path, "basis": basis, "R": R, "W": W, "errs": len(cols), "orbits": nor, "cases": [lo, hi], "sat": False}
t0 = time.time()
with Solver(name="cd15", bootstrap_with=cls) as s:
    for k in range(lo, min(hi, nor)):
        ass = [reps[k] + 1] + [-(j + 1) for j in range(len(cols)) if orb[j] < k]
        tk = time.time()
        r = s.solve(assumptions=ass)
        print(f"case {k}/{nor} sat={r} {time.time()-tk:.1f}s", flush=True)
        if r:
            m = s.get_model(); wit = [j for j in range(len(cols)) if m[j] > 0]
            dd, oo = set(), set()
            for j in wit: dd ^= set(cols[j][0]); oo ^= set(cols[j][1])
            assert not dd and oo
            res["sat"] = True; res["wit_weight"] = len(wit); break
res["sec"] = round(time.time() - t0, 1)
print(json.dumps(res), flush=True)
with open("results/E-028-audit/a3b_symsat.jsonl", "a") as f:
    f.write(json.dumps(res) + "\n")
