"""E-022 audit: independent minimum-weight undetected-logical solver (CP-SAT ILP over GF(2) via integer slack),
no search tree of mine, no orbit split. Reads the mdfs instance format.
usage: a2_cpsat.py instance [time_limit_s] [workers]  -> prints JSON {status, d (if OPTIMAL), lb, sol}"""
import sys, json, time
from ortools.sat.python import cp_model

def load(path):
    with open(path) as fh:
        R, C, NO, NORB = map(int, fh.readline().split())
        cols = []
        for _ in range(C):
            t = list(map(int, fh.readline().split()))
            k = t[1]; D = t[2:2 + k]; j = t[2 + k]; O = t[3 + k:3 + k + j]
            cols.append((D, O))
    return R, C, NO, cols

def solve(path, tl=600, workers=2):
    R, C, NO, cols = load(path)
    m = cp_model.CpModel()
    x = [m.NewBoolVar(f'x{c}') for c in range(C)]
    rows = [[] for _ in range(R)]; obs = [[] for _ in range(NO)]
    for c, (D, O) in enumerate(cols):
        for r in D: rows[r].append(x[c])
        for o in O: obs[o].append(x[c])
    for r in range(R):
        if rows[r]:
            y = m.NewIntVar(0, len(rows[r]) // 2, f'y{r}')
            m.Add(sum(rows[r]) == 2 * y)
    ob = []
    for o in range(NO):
        if not obs[o]:
            continue
        b = m.NewBoolVar(f'o{o}'); z = m.NewIntVar(0, len(obs[o]) // 2, f'z{o}')
        m.Add(sum(obs[o]) == 2 * z + b); ob.append(b)
    m.AddBoolOr(ob)
    m.Minimize(sum(x))
    s = cp_model.CpSolver(); s.parameters.max_time_in_seconds = tl; s.parameters.num_workers = workers
    t0 = time.time(); st = s.Solve(m)
    out = dict(path=path.split('/')[-1], status=s.StatusName(st), sec=round(time.time() - t0, 1),
               lb=s.BestObjectiveBound())
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        sol = [c for c in range(C) if s.Value(x[c])]
        out['ub'] = len(sol); out['sol'] = sol
        if st == cp_model.OPTIMAL: out['d'] = len(sol)
    return out

if __name__ == '__main__':
    tl = float(sys.argv[2]) if len(sys.argv) > 2 else 600
    w = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    print(json.dumps(solve(sys.argv[1], tl, w)))
