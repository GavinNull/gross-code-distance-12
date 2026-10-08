"""E-017 stage 4: exact CP-SAT on the projected single-round instance (lower-bound feasibility test).

Instance: columns of the single-noisy-round DEM projected onto memory-type detectors + observables (CSS
relaxation: dropping the other-type detectors can only lower the minimum, so 'no solution of weight <= W'
on the projection proves d_circ(1) >= W+1 for that basis).
Usage: uv run python -m search.experiments.e017.exact_proj --basis Z --maxw 11 --time 1800 --workers 4
"""
from __future__ import annotations

import argparse
import json
import time

from ortools.sat.python import cp_model

from search.experiments.e017.oneround import one_round_circuit
from search.experiments.e017.project import projected_columns


def solve(cols, nrows, nobs, maxw=None, time_s=600, workers=4, seed=0, minimize=True, fix_first=None):
    m = cp_model.CpModel()
    x = [m.NewBoolVar(f"x{i}") for i in range(len(cols))]
    rows = [[] for _ in range(nrows)]
    obs = [[] for _ in range(nobs)]
    for i, (ds, ob) in enumerate(cols):
        for d in ds:
            rows[d].append(x[i])
        for o in ob:
            obs[o].append(x[i])
    one = m.NewConstant(1)
    for r in rows:
        if r:
            m.AddBoolXOr(r + [one])
    zs = []
    for o in obs:
        z = m.NewBoolVar("")
        m.AddBoolXOr(o + [z, one])
        zs.append(z)
    m.AddBoolOr(zs)
    if maxw is not None:
        m.Add(sum(x) <= maxw)
    if fix_first is not None:
        m.Add(x[fix_first] == 1)
    if minimize:
        m.Minimize(sum(x))
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = time_s
    s.parameters.num_workers = workers
    s.parameters.random_seed = seed
    t0 = time.time()
    st = s.Solve(m)
    sol = [i for i in range(len(cols)) if s.StatusName(st) in ("OPTIMAL", "FEASIBLE") and s.Value(x[i])]
    return {"status": s.StatusName(st), "obj": s.ObjectiveValue() if minimize and sol else None,
            "bound": s.BestObjectiveBound() if minimize else None, "solution": sol,
            "seconds": round(time.time() - t0, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--basis", default="Z")
    ap.add_argument("--hom", default="x")
    ap.add_argument("--swap23", action="store_true")
    ap.add_argument("--maxw", type=int, default=None)
    ap.add_argument("--time", type=float, default=600)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    c, M = one_round_circuit(hom=a.hom, swap23=a.swap23, basis=a.basis)
    keep, cols = projected_columns(c, a.basis)
    r = solve(cols, len(keep), c.num_observables, maxw=a.maxw, time_s=a.time, workers=a.workers,
              minimize=(a.maxw is None))
    r["config"] = vars(a)
    r["ncols"] = len(cols)
    json.dump(r, open(a.out, "w"), indent=1)
    print(json.dumps({k: v for k, v in r.items() if k != "solution"}), flush=True)


if __name__ == "__main__":
    main()
