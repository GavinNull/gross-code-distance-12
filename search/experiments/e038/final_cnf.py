"""E-038: build the final CNF of a class = legality (enc.Enc) + clauses of the UNION of pattern files, write DIMACS,
the pattern list, and (optionally) one cube CNF per cube (CNF + 6 unit clauses fixing the layers of the first check).
usage: uv run python -m search.experiments.e038.final_cnf N 7 OUTPREFIX p1.json,p2.json,... [--cubes]"""
import argparse
import json

from search.experiments.e038.cegar import PatternEncoder, load_patterns, save_patterns
from search.experiments.e038.cube import cubes
from search.experiments.e038.enc import Enc

ap = argparse.ArgumentParser()
ap.add_argument("cls")
ap.add_argument("arg", type=int)
ap.add_argument("out")
ap.add_argument("pats")
ap.add_argument("--variant", default="bb18")
ap.add_argument("--cubes", action="store_true")
a = ap.parse_args()
E = Enc(a.variant, a.cls, a.arg)
nleg = len(E.cl)
PE = PatternEncoder(E)
pats = {}
for p in a.pats.split(","):
    for pat in load_patterns(p):
        if pat not in pats:
            cl = PE.clauses(pat)
            pats[pat] = len(cl)
            for c in cl:
                E.add(c)
with open(a.out + ".cnf", "w") as f:
    f.write(f"p cnf {E.nv} {len(E.cl)}\n")
    for c in E.cl:
        f.write(" ".join(map(str, c)) + " 0\n")
save_patterns(a.out + "_patterns.json", pats)
info = {"vars": E.nv, "clauses": len(E.cl), "legality_and_defs_clauses": nleg, "patterns": len(pats)}
if a.cubes:
    cs = cubes(E, a.arg)
    json.dump([[l for l in c if l is not True] for c in cs], open(a.out + "_cubes.json", "w"))
    info["cubes"] = len(cs)
print(json.dumps(info))
