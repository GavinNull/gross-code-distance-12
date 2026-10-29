"""Item 6: direct circuit-distance decision on the evaluator's SD6 DEM (no extended code, no step model):
is there a set of <= W distinct DEM error mechanisms with zero detector parity and odd parity on some observable?
CP-SAT, single worker.  Feasible solutions are re-verified by XOR.

  uv run python -m search.theory.B_audit.dem_search bb108 results/theoryB/specs/bb108_u11tpl.json Z 1 9 [timelimit_s]
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict

import numpy as np
from ortools.sat.python import cp_model

from search.theory.B_audit.common import get_code, load_spec_dict


def dem_errors(code, spec_d, basis, R):
    from evaluators import candidate as cand
    from evaluators.noise import add_noise
    circ = add_noise(cand.memory_circuit(cand.parse_schedule(spec_d), code, basis, R), "sd6", 1e-3)
    d = circ.detector_error_model(approximate_disjoint_errors=True, flatten_loops=True)
    errs = set()
    for e in d.flattened():
        if e.type != "error":
            continue
        ds, os_ = set(), set()
        for t in e.targets_copy():
            if t.is_relative_detector_id():
                ds ^= {t.val}
            elif t.is_logical_observable_id():
                os_ ^= {t.val}
        if ds or os_:
            errs.add((frozenset(ds), frozenset(os_)))
    return sorted(errs, key=lambda x: (sorted(x[0]), sorted(x[1]))), d.num_detectors, d.num_observables


def decide(errs, nd, no, W, tl):
    m = cp_model.CpModel()
    e = [m.NewBoolVar("") for _ in errs]
    byd, byo = defaultdict(list), defaultdict(list)
    for i, (ds, os_) in enumerate(errs):
        for x in ds:
            byd[x].append(e[i])
        for x in os_:
            byo[x].append(e[i])
    for x, l in byd.items():
        m.Add(sum(l) == 2 * m.NewIntVar(0, len(l) // 2, ""))
    ps = []
    for x, l in byo.items():
        p = m.NewBoolVar("")
        m.Add(sum(l) == 2 * m.NewIntVar(0, len(l) // 2, "") + p)
        ps.append(p)
    m.Add(sum(ps) >= 1)
    m.Add(sum(e) <= W)
    s = cp_model.CpSolver()
    s.parameters.num_workers = 1
    s.parameters.max_time_in_seconds = tl
    st = s.Solve(m)
    sol = None
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        sol = [i for i in range(len(errs)) if s.Value(e[i])]
        dd, oo = set(), set()
        for i in sol:
            dd ^= set(errs[i][0]); oo ^= set(errs[i][1])
        assert not dd and oo, "solution check failed"
    return s.StatusName(st), sol, s.WallTime()


def main():
    name, sp, basis, R, W = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
    tl = float(sys.argv[6]) if len(sys.argv) > 6 else 3600
    code = get_code(name)
    errs, nd, no = dem_errors(code, load_spec_dict(sp), basis, R)
    st, sol, wt = decide(errs, nd, no, W, tl)
    print(json.dumps({"code": name, "spec": sp, "basis": basis, "R": R, "W<=": W, "n_mech": len(errs),
                      "n_det": nd, "status": st, "found_weight": len(sol) if sol else None, "sec": round(wt, 1),
                      "witness": sol}), flush=True)


if __name__ == "__main__":
    main()
