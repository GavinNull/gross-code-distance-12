"""E-024b step 1: enumerate ALL colour-dependent type assignments with d_ext >= 11 on one side (kind), for one
colouring, by a lazy SAT loop with a complete-DFS oracle.

Variables x[c][t]: colour c uses type t (one of the 45 allowed types, types(kind)); exactly one per colour.
Oracle: for a model, build the extended code (e021 extgen.ext_general on the 72 per-check orders) and run the E-014
DFS at W=10 (stop at first witness; with no witness the run is complete = proof d_ext >= 11 on this side).
Nogood from a witness (columns j_1..j_w, weight <= 10): for every translation g of the 72, the translated supports
give column keys; if all non-data keys are present the translated set is again a weight <= 10 logical (translations
are code automorphisms, keys are (H,L) images).  present(key) <- x[colour(a)][t] for every realisation (a, U) of
the key with U a residual set of t.  Clause: OR_k not present(key_k).  Valid for every assignment.
Survivors: blocked together with their colour-shift images (the 72 translations permute colours cyclically).
Loop ends when UNSAT => the survivor list is complete for this colouring and side.

    PYTHONPATH=. uv run python -m search.experiments.e024b.dextsat --kind X --col 3,1,1 --workers 4
"""
from __future__ import annotations

import argparse
import json
import time

from pysat.formula import IDPool
from pysat.solvers import Cadical153

from search.experiments.e018 import common as C
from search.experiments.e024b.common import (OUT, colour, dfs, ext_general, key_of, labord, name, realisations,
                                              resid_sets, single_hooks, types)

N2 = 72


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True)
    ap.add_argument("--col", required=True, help="m,alpha,beta")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max_sec", type=float, default=36000)
    a = ap.parse_args()
    kind = a.kind
    col = tuple(int(v) for v in a.col.split(","))
    m = col[0]
    TY = types(kind)
    nt = len(TY)
    RS = [resid_sets(o) for o in TY]
    real = realisations(kind)
    pool = IDPool()
    S = Cadical153()
    x = [[pool.id(("x", c, t)) for t in range(nt)] for c in range(m)]
    for c in range(m):
        S.add_clause(x[c])
        for t1 in range(nt):
            for t2 in range(t1 + 1, nt):
                S.add_clause([-x[c][t1], -x[c][t2]])
    pres = {}

    def present(k):
        if k not in pres:
            p = pool.id(("p", k))
            for a_, U in real.get(k, []):
                c = colour(col, a_)
                for t in range(nt):
                    if U in RS[t]:
                        S.add_clause([-x[c][t], p])
            pres[k] = p
        return pres[k]

    # colour shift of each translation
    shifts = sorted({colour(col, 6 * ga + gb) for ga in range(12) for gb in range(6)})
    T0 = time.time()
    tag = f"dext_{kind}_m{col[0]}_{col[1]}{col[2]}"
    outp = OUT / f"{tag}.jsonl"
    nclauses, ncalls, nsurv = 0, 0, 0
    status = "TIMEOUT"
    def add_witness_clauses(E, w):
        sups = [E["col_sups"][j][0] for j in w if not any(len(s_) == 1 for s_ in E["col_sups"][j])]
        clauses = set()
        for ga in range(12):
            for gb in range(6):
                _, pc = C.tr(ga, gb)
                ks = [key_of(kind, [int(pc[q]) for q in s_]) for s_ in sups]
                clauses.add(tuple(sorted({-present(k) for k in ks})))
        for cl in clauses:
            S.add_clause(list(cl))
        return len(sups), len(clauses)

    # restart: replay previous records of this run
    if outp.exists():
        for line in outp.read_text().splitlines():
            r = json.loads(line)
            assign = tuple(r["assign"])
            if r.get("survivor"):
                nsurv += 1
                for sh in shifts:
                    S.add_clause([-x[(c + sh) % m][assign[c]] for c in range(m)])
            else:
                E = ext_general(kind, labord(col, tuple(TY[t] for t in assign)))
                nclauses += add_witness_clauses(E, r["witness"])[1]
            ncalls += 1
        print(f"replayed {ncalls} records", flush=True)
    while time.time() - T0 < a.max_sec:
        if not S.solve():
            status = "COMPLETE"; break
        md = set(l for l in S.get_model() if l > 0)
        assign = tuple(next(t for t in range(nt) if x[c][t] in md) for c in range(m))
        orders = tuple(TY[t] for t in assign)
        lab = labord(col, orders)
        E = ext_general(kind, lab)
        t1 = time.time()
        sols, nodes, complete = dfs(E, 10, stopfirst=1, workers=a.workers)
        ncalls += 1
        rec = {"kind": kind, "col": col, "assign": list(assign), "orders": [name(o) for o in orders],
               "group": len(E["group"]), "orbits": len(E["reps"]), "N": E["N"], "nodes": nodes,
               "sec": round(time.time() - t1, 1), "single_hooks": [single_hooks(kind, o) for o in orders]}
        if sols:
            w = sols[0]
            rec["witness"] = list(w)
            nh, ncl = add_witness_clauses(E, w)
            rec["n_hooks"] = nh
            nclauses += ncl
        else:
            assert complete
            rec["survivor"] = True
            nsurv += 1
            # block this assignment and its colour-shift images
            for sh in shifts:
                S.add_clause([-x[(c + sh) % m][assign[c]] for c in range(m)])
            print("SURVIVOR", json.dumps(rec), flush=True)
        with open(outp, "a") as f:
            f.write(json.dumps(rec) + "\n")
        if ncalls % 20 == 0:
            print(f"calls {ncalls} clauses {nclauses} survivors {nsurv} {time.time() - T0:.0f}s", flush=True)
    summ = {"kind": kind, "col": col, "status": status, "calls": ncalls, "clauses": nclauses, "survivors": nsurv,
            "sec": round(time.time() - T0, 1)}
    print("DONE", json.dumps(summ), flush=True)
    with open(OUT / "dext_summary.jsonl", "a") as f:
        f.write(json.dumps(summ) + "\n")


if __name__ == "__main__":
    main()
