"""CP-SAT probe of the extended-code weight question (timing only; not a certificate).

    python dext_cpsat.py BASIS W [--case K] [--time S]
"""
import sys
import time

from ortools.sat.python import cp_model

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from dext_cnf import load      # noqa: E402

basis, w = sys.argv[1], int(sys.argv[2])
case = int(sys.argv[sys.argv.index("--case") + 1]) if "--case" in sys.argv else None
tl = float(sys.argv[sys.argv.index("--time") + 1]) if "--time" in sys.argv else 600
d, cols = load(basis)
m = cp_model.CpModel()
x = [m.NewBoolVar(f"x{j}") for j in range(len(cols))]
rows_h = [[] for _ in range(d["num_checks"])]
rows_l = [[] for _ in range(d["num_logicals"])]
for c in cols:
    for i in c["H"]:
        rows_h[i].append(x[c["index"]])
    for r in c["L"]:
        rows_l[r].append(x[c["index"]])
one = m.NewConstant(1)
for r in rows_h:
    m.AddBoolXOr(r + [one])
ps = []
for r in rows_l:
    p = m.NewBoolVar("")
    m.AddBoolXOr(r + [p.Not()])     # XOR(r) xor not p = 1  <=> p = XOR(r)
    ps.append(p)
m.AddBoolOr(ps)
m.Add(sum(x) <= w)
if case is not None:
    m.Add(x[min(d["orbits"][case])] == 1)
    for o in d["orbits"][:case]:
        for j in o:
            m.Add(x[j] == 0)
s = cp_model.CpSolver()
s.parameters.num_workers = 1
s.parameters.max_time_in_seconds = tl
t0 = time.process_time()
st = s.Solve(m)
print(basis, w, case, s.StatusName(st), round(time.process_time() - t0, 1), "s", flush=True)
