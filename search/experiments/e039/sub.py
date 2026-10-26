"""E-039 sub-system lemmas.  For memory basis b and a set S of spreader checks (type != b), the sub-CNF
    legality of the whole class  +  every static pattern of basis b (types HH, HHM, DDH, optionally DHH, HHH) whose
    H slots all belong to checks in S
is a SUBSET of the clauses of the full CNF (each pattern clause is sound on its own), so if the sub-CNF is UNSAT the
whole class has a bulk witness of weight <= 3 in every schedule.  Such a pattern only involves the times of the
readers (all checks of type b) and of the spreaders in S.
usage: uv run python -m search.experiments.e039.sub W 8 --basis Z --spreaders X3 [--types HH,HHM,DDH] [--dump f.cnf]"""
import argparse
import json
import time

from pysat.solvers import Solver

from search.experiments.e038.cegar import PatternEncoder
from search.experiments.e039.scegar import make_enc
from search.experiments.e039.static import multisets, patterns_of


def build(cls, P, basis, S, types, variant="bb18"):
    E = make_enc(cls, P, variant)
    PE = PatternEncoder(E)
    n = 0
    for m in multisets(variant, basis, set(types)):
        if any(h[0] == "H" and h[1] not in S for h in m):
            continue
        for pat in patterns_of(basis, m):
            cl = PE.clauses(pat)
            assert all(len(c) for c in cl)
            for c in cl:
                E.add(c)
            n += 1
    return E, n


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cls")
    ap.add_argument("P", type=int)
    ap.add_argument("--basis", required=True)
    ap.add_argument("--spreaders", required=True, help="comma list like X3,X4 or 'all'")
    ap.add_argument("--types", default="HH,HHM,DDH")
    ap.add_argument("--dump")
    a = ap.parse_args()
    from search.experiments.e036_audit.core import checks
    allsp = [k for k in checks("bb18") if k[0] != a.basis]
    S = allsp if a.spreaders == "all" else [(s[0], int(s[1:])) for s in a.spreaders.split(",")]
    t0 = time.time()
    E, n = build(a.cls, a.P, a.basis, set(S), a.types.split(","))
    tb = time.time() - t0
    s = Solver(name="cd15", bootstrap_with=E.cl)
    r = s.solve()
    rec = {"cls": a.cls, "P": a.P, "basis": a.basis, "S": [f"{k[0]}{k[1]}" for k in S], "types": a.types,
           "patterns": n, "vars": E.nv, "clauses": len(E.cl), "result": "SAT" if r else "UNSAT",
           "build": round(tb, 1), "solve": round(time.time() - t0 - tb, 1)}
    print(json.dumps(rec), flush=True)
    with open("results/E-039-bb18-pipe/sub.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    if a.dump:
        with open(a.dump, "w") as f:
            f.write(f"p cnf {E.nv} {len(E.cl)}\n")
            for c in E.cl:
                f.write(" ".join(map(str, c)) + " 0\n")
