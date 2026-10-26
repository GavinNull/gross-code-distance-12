"""E-038 audit: N(S) with my second encoding (gcnf.nclass: one-hot + first-instance indicators J, the same code path
as the V-class check) + my translation of E-038 pattern files; whole CNF -> tools/cadical DRAT -> drat-trim, or cubes.
usage: uv run python -m search.experiments.e038_audit.b8_nclass_gcnf S PATFILES [--cube i,j,...]"""
import argparse
import hashlib
import json
import os
import subprocess
import time

from search.experiments.e038_audit import gcnf, gpat, npat

ap = argparse.ArgumentParser()
ap.add_argument("S", type=int)
ap.add_argument("pats")
ap.add_argument("--cubes", default="")
a = ap.parse_args()
G = gcnf.nclass(a.S)
sem = gpat.GSem(a.S + 2)
seen = set()
for f in a.pats.split(","):
    for p in json.load(open(f)):
        k = json.dumps(p)
        if k in seen:
            continue
        seen.add(k)
        G.cl += G.pattern_clauses(sem.readers, npat.norm_pattern(p))
base = f"results/E-038-audit/my2_N{a.S}"
k0 = ("Z", 0)
qs = sorted(q for (k, q) in G.ev if k == k0)[:2]
allc = [[G.x[(k0, qs[0])][t1], G.x[(k0, qs[1])][t2]] for t1 in range(1, a.S + 1) for t2 in range(1, a.S + 1) if t1 != t2]
todo = [None] if not a.cubes else [allc[int(i)] for i in a.cubes.split(",")]
for cb in todo:
    cnf = base + ("" if cb is None else f"_c{cb[0]}_{cb[1]}") + ".cnf"
    units = [] if cb is None else [[l] for l in cb]
    with open(cnf, "w") as f:
        f.write(f"p cnf {G.nv} {len(G.cl) + len(units)}\n")
        for c in G.cl + units:
            f.write(" ".join(map(str, c)) + " 0\n")
    t0 = time.time()
    r = subprocess.run(["tools/cadical/build/cadical", "-q", cnf, cnf[:-4] + ".drat"], capture_output=True, text=True)
    st = [l for l in r.stdout.splitlines() if l.startswith("s ")]
    rec = {"S": a.S, "cube": cb, "patterns": len(seen), "vars": G.nv, "clauses": len(G.cl) + len(units),
           "cnf_sha256": hashlib.sha256(open(cnf, "rb").read()).hexdigest(), "cadical": st[0] if st else None}
    if st and st[0] == "s UNSATISFIABLE":
        v = subprocess.run(["tools/drat-trim/drat-trim", cnf, cnf[:-4] + ".drat", "-t", "40000"], capture_output=True, text=True)
        rec["drat_verified"] = "s VERIFIED" in v.stdout
    os.remove(cnf[:-4] + ".drat")
    os.remove(cnf)
    rec["sec"] = round(time.time() - t0, 1)
    print(json.dumps(rec), flush=True)
    with open("results/E-038-audit/b8_nclass_gcnf.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
