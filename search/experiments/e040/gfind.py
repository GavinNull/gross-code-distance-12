"""E-040 generic witness finder (no extended-code structure): CP-SAT over every bulk fault of bulk.Sector with anchor
round in [0, R-1]; all detectors even, residual a non-trivial logical, weight <= W (minimised).  Faults outside the
window are absent, so any solution is a genuine bulk witness (re-verified with Sector.is_witness).  Incomplete only in
the window size; used for the sector signatures the lift finder leaves unresolved.
"""
from __future__ import annotations

import numpy as np
from ortools.sat.python import cp_model

from search.experiments.e040.bulk import Sector


def gfind(S: Sector, R, W, sec=60, workers=4, minimise=True):
    mech = S.all_mechanisms(0, R - 1)
    m = cp_model.CpModel()
    x = [m.NewBoolVar(f"x{i}") for i in range(len(mech))]
    dets, logs = {}, []
    k = S.L.shape[0]
    lb = []
    for i, f in enumerate(mech):
        for d in S.dets(f):
            dets.setdefault(d, []).append(i)
        e = np.zeros(S.NQ, np.uint8)
        for q in S.data_of(f):
            e[q] ^= 1
        lb.append(S.L @ e % 2)
    for d, ids in dets.items():
        # parity even (a fault may hit one detector twice: count multiplicity)
        cnt = {}
        for i in ids:
            cnt[i] = cnt.get(i, 0) ^ 1
        ids2 = [i for i, v in cnt.items() if v]
        if ids2:
            y = m.NewIntVar(0, len(ids2) // 2, "")
            m.Add(sum(x[i] for i in ids2) == 2 * y)
    lv = []
    for j in range(k):
        ids = [i for i in range(len(mech)) if lb[i][j]]
        z = m.NewIntVar(0, len(ids) // 2 + 1, "")
        b = m.NewBoolVar("")
        m.Add(sum(x[i] for i in ids) == 2 * z + b)
        lv.append(b)
    m.AddBoolOr(lv)
    m.Add(sum(x) <= W)
    if minimise:
        m.Minimize(sum(x))
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = sec
    s.parameters.num_workers = workers
    st = s.Solve(m)
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        F = [mech[i] for i in range(len(mech)) if s.Value(x[i])]
        ok, D, e = S.is_witness(F)
        assert ok
        return F, s.StatusName(st)
    return None, s.StatusName(st)
