"""Second solver: CP-SAT feasibility of |x| <= 9 per symmetry case (x[rep(o)] = 1, x[orbit < o] = 0)."""
import sys, json, time
sys.path.insert(0, "research/audits/2026-10-05-E-013-scripts")
import numpy as np
from ortools.sat.python import cp_model
from extcode import ext

kind, cases, tl, workers = sys.argv[1], [int(c) for c in sys.argv[2].split(",")], float(sys.argv[3]), int(sys.argv[4])
d = ext(kind); He, Le, orb, reps = d["He"], d["Le"], d["orbit"], d["reps"]
res = []
for o in cases:
    md = cp_model.CpModel(); N = He.shape[1]
    x = [md.NewBoolVar("") for _ in range(N)]; one = md.NewConstant(1)
    for row in He:
        md.AddBoolXOr([x[j] for j in np.nonzero(row)[0]] + [one])
    bs = []
    for row in Le:
        b = md.NewBoolVar(""); bs.append(b)
        md.AddBoolXOr([x[j] for j in np.nonzero(row)[0]] + [b.Not()])
    md.AddBoolOr(bs)
    md.Add(sum(x) <= 9)
    md.Add(x[reps[o]] == 1)
    for j in range(N):
        if orb[j] < o: md.Add(x[j] == 0)
    s = cp_model.CpSolver(); s.parameters.max_time_in_seconds = tl; s.parameters.num_workers = workers
    t0 = time.time(); st = s.Solve(md)
    r = dict(kind=kind, case=o, status=s.StatusName(st), seconds=round(time.time() - t0, 1))
    print(json.dumps(r), flush=True); res.append(r)
