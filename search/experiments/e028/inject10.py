"""E-028 (copy of e024b/inject12.py for [[90,8,10]]): upper bound d_circ <= 10: a minimum-weight data logical (CP-SAT, weight 10) injected right after the data reset
into the evaluator's noiseless circuit (each flip is one SD6 reset-fault mechanism); expect 0 detectors and an
observable flip.  Same method as research/audits/2026-10-10-E-021-scripts/b6_inject.py.

    PYTHONPATH=.:tests uv run python -m search.experiments.e028.inject10 spec.json
"""
import json
import sys

import numpy as np
import stim
from ortools.sat.python import cp_model

from evaluators.candidate import build_circuits, parse_schedule
from search.experiments.e028.common import css

spec = parse_schedule(json.load(open(sys.argv[1]))).canonical()
c = css()
out = {}
for basis in "ZX":
    H, L = (np.asarray(c.HZ) % 2, np.asarray(c.LZ) % 2) if basis == "Z" else (np.asarray(c.HX) % 2, np.asarray(c.LX) % 2)
    M = cp_model.CpModel(); x = [M.NewBoolVar("") for _ in range(90)]
    for row in H:
        k = M.NewIntVar(0, 6, ""); M.Add(sum(x[j] for j in np.nonzero(row)[0]) == 2 * k)
    k = M.NewIntVar(0, 45, ""); M.Add(sum(x[j] for j in np.nonzero(L[0])[0]) == 2 * k + 1)
    M.Minimize(sum(x))
    s = cp_model.CpSolver(); s.parameters.max_time_in_seconds = 120; s.parameters.num_workers = 1
    s.Solve(M)
    supp = [j for j in range(90) if s.Value(x[j])]
    res = {"weight": len(supp), "support": supp}
    for R in (1, 3, 6, 10):
        circ = build_circuits(spec, c, R)[basis]
        ops = list(circ)
        inj = stim.Circuit(); inj.append(ops[0]); inj.append("X_ERROR" if basis == "Z" else "Z_ERROR", supp, 1.0)
        for op in ops[1:]:
            inj.append(op)
        d, o = inj.compile_detector_sampler().sample(1, separate_observables=True)
        res[f"R{R}"] = {"detectors_fired": int(d.sum()), "obs_flipped": int(o.sum())}
    out[basis] = res
    print(basis, res, flush=True)
json.dump(out, open("results/E-028-bb90-interleaved/inject10_" + sys.argv[1].split("/")[-1], "w"))
