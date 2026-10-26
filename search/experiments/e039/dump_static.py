"""E-039: write the static CNF (legality + all static patterns of the given types, both bases) of a class as DIMACS,
plus a json map of the prep-time literals (pi[k] = v) for cubes.
usage: uv run python -m search.experiments.e039.dump_static W 8 results/E-039-bb18-pipe/W8_static.cnf"""
import argparse
import json

from search.experiments.e038.cegar import PatternEncoder
from search.experiments.e039.scegar import make_enc
from search.experiments.e039.static import multisets, patterns_of

ap = argparse.ArgumentParser()
ap.add_argument("cls")
ap.add_argument("P", type=int)
ap.add_argument("out")
ap.add_argument("--types", default="HH,HHM,DDH")
a = ap.parse_args()
E = make_enc(a.cls, a.P)
PE = PatternEncoder(E)
npat = 0
for b in ("Z", "X"):
    for m in multisets("bb18", b, set(a.types.split(","))):
        for pat in patterns_of(b, m):
            for c in PE.clauses(pat):
                assert c
                E.add(c)
            npat += 1
pil = {f"{k[0]}{k[1]}": {v: E.pi[k].eq(v) for v in range(E.pi[k].lo, E.pi[k].hi + 1)} for k in E.ks}
# eq() may have created variables/clauses: write after
with open(a.out, "w") as f:
    f.write(f"p cnf {E.nv} {len(E.cl)}\n")
    for c in E.cl:
        f.write(" ".join(map(str, c)) + " 0\n")
json.dump({"pi_eq": pil, "nv": E.nv, "ncl": len(E.cl), "patterns": npat}, open(a.out.replace(".cnf", "_map.json"), "w"))
print(E.nv, len(E.cl), npat)
