"""E-037: write an E-029 ccsearch instance from a dem_inst.py column file (task 4 cross-check).  experimenter.

    uv run python search/experiments/e037/to_cc.py OUT.cols.json OUT.json CC.txt
Rows = detectors, observables = the original observable rows (not the closure), orbits = those of OUT.json's group
(recomputed here from the detector permutation, independently of dem_inst.py's orbit list).
"""
import json
import sys

cols = json.load(open(sys.argv[1]))
meta = json.load(open(sys.argv[2]))
D, L, ndet, nobs = cols["D"], cols["L"], cols["ndet"], cols["nobs"]
src = cols["source"]
kind, code, b, R = src.split(":")
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import dem_inst  # noqa: E402

s = dem_inst.load_source(src)
assert s["D"] == [tuple(d) for d in D] or [list(d) for d in s["D"]] == D
l, m = s["l"], s["m"]
key = {c: i for i, c in enumerate(s["coords"])}
index = {tuple(d): j for j, d in enumerate(D)}
orb = [-1] * len(D)
orbits = []
for j in range(len(D)):
    if orb[j] >= 0:
        continue
    o = set()
    for (a, bb) in meta["group"]:
        def tq(i):
            x, y = divmod(i, m)
            return ((x + a) % l) * m + (y + bb) % m
        img = tuple(sorted(key[(tq(s["coords"][x][0]), s["coords"][x][1])] for x in D[j]))
        o.add(index[img])
    o = sorted(o)
    for c in o:
        orb[c] = len(orbits)
    orbits.append(o)
with open(sys.argv[3], "w") as f:
    f.write(f"{ndet} {len(D)} {nobs} {len(orbits)}\n")
    for d, o in zip(D, L):
        f.write(f"{len(d)} " + " ".join(map(str, d)) + f" {len(o)} " + " ".join(map(str, o)) + "\n")
    for o in orbits:
        f.write(f"{len(o)} " + " ".join(map(str, o)) + "\n")
print(len(D), "columns", len(orbits), "orbits")
