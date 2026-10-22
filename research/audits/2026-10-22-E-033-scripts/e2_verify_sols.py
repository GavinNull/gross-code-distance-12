"""Auditor E-033 claim 5: check the ccsearch outputs used for the W10 (IBM) / W12 (u11) counts on MY OWN DEM.
 - every instance column (row set) must be a column of my DEM (own circuit, SD6 lam=1) and vice versa;
 - every root solution: weight W distinct columns, detector sets XOR to empty, MY observables flip (nonzero);
 - expand by the 72 translations, acting on MY detector coordinates (check (x,y) -> (x+a, y+b), round fixed),
   each translated set re-verified; distinct sets counted.  Per-round count = N(R+1) - N(R).
This does NOT re-prove completeness of ccsearch (no weight < W, all weight-W found) -- see report.
  uv run python e2_verify_sols.py <circ> <basis> <R> <W>"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mylib
ROOT = "/Users/ephemeral/Desktop/qec-ai-search/"
SPEC = {"u11": "search/experiments/e032/u11_spec.json", "ibm": "search/experiments/e033/ibm_gross_spec.json"}
circ, b, R, W = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
c = mylib.memory_circuit(mylib.load_spec(ROOT + SPEC[circ]), b, R, p=1e-3, lam=1.0)
coords = c.get_detector_coordinates()
idx = {(int(v[0]), int(v[1])): k for k, v in coords.items()}
terms, nd, no = mylib.dem_terms(c)
mine = {}
for dm, om, pr in terms:
    ds = frozenset(i for i in range(nd) if dm >> i & 1)
    assert mine.get(ds, om) == om
    mine[ds] = om
# instance columns
lines = open(ROOT + f"results/E-033-gross-u11-ler/inst/{circ}_{b}_R{R}.txt").read().split("\n")
nr, nc, nobs, norb = map(int, lines[0].split())
inst = []
for ln in lines[1:1 + nc]:
    t = list(map(int, ln.split()))
    k = t[0]; inst.append(frozenset(t[1:1 + k]))
assert nr == nd and set(inst) == set(mine), "instance columns != my DEM columns"
def tr(ds, a, bb):
    out = set()
    for d in ds:
        i, j = map(int, coords[d][:2]); x, y = divmod(i, 6)
        out.add(idx[(((x + a) % 12) * 6 + (y + bb) % 6, j)])
    return frozenset(out)
# translation is a DEM symmetry (column set mapped to itself)
for a in range(12):
    for bb in range(6):
        assert all(tr(ds, a, bb) in mine for ds in mine), ("not a DEM symmetry", a, bb)
f = ROOT + f"results/E-033-gross-u11-ler/runs/{circ}_{b}_R{R}_enum{W}.txt"
roots = []
for ln in open(f):
    if ln.startswith("SOL"):
        hd, cols = ln.split(":")
        roots.append([inst[int(x)] for x in cols.split()])
def ok(sol):
    acc = set(); om = 0
    for ds in sol:
        acc ^= set(ds); om ^= mine[ds]
    return len(set(sol)) == W and not acc and om != 0
bad = sum(not ok(s) for s in roots)
allsets = set()
for s in roots:
    for a in range(12):
        for bb in range(6):
            t = frozenset(tr(ds, a, bb) for ds in s)
            assert ok(list(t))
            allsets.add(t)
r = dict(circ=circ, basis=b, R=R, W=W, my_cols=len(mine), root_solutions=len(roots), bad_roots=bad, distinct_after_72=len(allsets))
print(json.dumps(r), flush=True)
open(ROOT + "results/E-033-audit/e2_verify_sols.jsonl", "a").write(json.dumps(r) + "\n")
