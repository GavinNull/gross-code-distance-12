"""E-038 audit: V(P, delta) with my CNF (gcnf.vclass + my translation of E-038's V patterns), split into the 42
cubes of check Z0's first two CNOT times (window delta+1 .. delta+P-2), each solved by pysat CaDiCaL 1.9.5.
usage: uv run python -m search.experiments.e038_audit.b5b_vcubes P delta --shard i/n"""
import argparse
import json
import time

from pysat.solvers import Solver

from search.experiments.e038_audit import gcnf, gpat, npat

ap = argparse.ArgumentParser()
ap.add_argument("P", type=int)
ap.add_argument("delta", type=int)
ap.add_argument("--shard", default="0/1")
a = ap.parse_args()
sh, n = map(int, a.shard.split("/"))
P, d = a.P, a.delta
G = gcnf.vclass(P, d)
sem = gpat.GSem(P)
pf = f"results/E-038-bb18-d4/cegar_bb18_V{P}_d4_delta{d}_patterns.json"
for p in json.load(open(pf)):
    G.cl += G.pattern_clauses(sem.readers, npat.norm_pattern(p))
k0 = ("Z", 0)
qs = sorted(q for (k, q) in G.ev if k == k0)[:2]
win = sorted(G.x[(k0, qs[0])])
cubes = [[G.x[(k0, qs[0])][t1], G.x[(k0, qs[1])][t2]] for t1 in win for t2 in win if t1 != t2]
out = open(f"results/E-038-audit/b5b_V{P}_delta{d}_{sh}of{n}.jsonl", "a")
for i, cb in enumerate(cubes):
    if i % n != sh:
        continue
    t0 = time.time()
    s = Solver(name="cadical195", bootstrap_with=G.cl)
    r = s.solve(assumptions=cb)
    s.delete()
    rec = {"P": P, "delta": d, "cube": i, "ncubes": len(cubes), "lits": cb, "result": "SAT" if r else "UNSAT",
           "sec": round(time.time() - t0, 1)}
    out.write(json.dumps(rec) + "\n")
    out.flush()
    print(json.dumps(rec), flush=True)
