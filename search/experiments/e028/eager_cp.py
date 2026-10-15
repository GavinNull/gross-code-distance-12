"""E-028: CP-SAT version of eager.py's eager-only problem (same clauses; linear form): y[a,t] one-hot types,
r[a,U] = sum of y[a,t] over types t realising label set U at check a (pairs/triples/4-sets <= 1 automatically);
each eager clause (keys k_1..k_m, every key realised at a single (check, label-set) up to equivalent label sets)
becomes  sum_i pres(k_i) <= m - 1.  INFEASIBLE => no per-check assignment (in the colouring) has d_ext >= 9.

    PYTHONPATH=.:tests uv run python -m search.experiments.e028.eager_cp --kind X --sub 0,0 --workers 4
"""
from __future__ import annotations

import argparse
import json
import pickle
import time

from ortools.sat.python import cp_model

from search.experiments.e028 import common as C
from search.experiments.e028.dext import cosets, types
from search.experiments.e028.eager import eager_clauses


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True)
    ap.add_argument("--sub", default="0,0")
    ap.add_argument("--W", type=int, default=10)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max_sec", type=float, default=3600)
    a = ap.parse_args()
    T0 = time.time()
    kind = a.kind
    gens = [tuple(int(v) for v in g.split(",")) for g in a.sub.split(";")]
    colv, m, perms, hs = cosets(gens)
    TY = types(kind)
    RS = [C.resid_sets(o) for o in TY]
    real = C.realisations(kind)
    ecl = eager_clauses(kind, pickle.load(open(C.OUT / f"codelog_{kind}_W{a.W}.pkl", "rb")))
    M = cp_model.CpModel()
    y = [[M.NewBoolVar(f"y{c}_{t}") for t in range(len(TY))] for c in range(m)]
    for c in range(m):
        M.AddExactlyOne(y[c])
    pres = {}

    def present(k):
        if k not in pres:
            p = M.NewBoolVar("")
            lits = sorted({(colv[a_], t) for a_, U in real[k] for t in range(len(TY)) if U in RS[t]})
            # p <=> OR(lits)
            M.AddBoolOr([y[c][t] for c, t in lits]).OnlyEnforceIf(p)
            for c, t in lits:
                M.AddImplication(y[c][t], p)
            pres[k] = p
        return pres[k]
    for ks in ecl:
        M.AddBoolOr([present(k).Not() for k in ks])
    print(f"clauses {len(ecl)} pres {len(pres)} build {time.time() - T0:.0f}s", flush=True)
    s = cp_model.CpSolver()
    s.parameters.num_workers = a.workers
    s.parameters.max_time_in_seconds = a.max_sec
    s.parameters.log_search_progress = False
    st = s.Solve(M)
    res = {"kind": kind, "sub": a.sub, "W": a.W, "status": s.StatusName(st), "sec": round(time.time() - T0, 1),
           "clauses": len(ecl)}
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        res["orders"] = [C.name(TY[next(t for t in range(len(TY)) if s.Value(y[c][t]))]) for c in range(m)]
    print(json.dumps(res), flush=True)
    with open(C.OUT / "eager_cp_summary.jsonl", "a") as f:
        f.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    main()
