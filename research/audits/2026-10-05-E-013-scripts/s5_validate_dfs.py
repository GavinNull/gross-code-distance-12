"""Validate the C DFS against CP-SAT on instances with KNOWN small d_ext: random two-colour (row-parity) term orders
(same 27-element symmetry group).  For each instance: DFS min = smallest W with a hit (W<=9) and DFS proves
nothing below; CP-SAT (own model, 4 workers) min.  Every DFS witness is re-verified in Python."""
import sys, json, subprocess, random, time
sys.path.insert(0, "research/audits/2026-10-05-E-013-scripts")
import numpy as np
from extcode import ext, dump_instance

DFS = "results/E-013-audit/dfs"


def dfs_min(path, Wmax=9):
    for W in range(3, Wmax + 1):
        hits = []
        tot = 0.0
        for k in range(10):
            o = subprocess.run([DFS, path, str(W), str(k)], capture_output=True, text=True).stdout
            for ln in o.splitlines():
                if ln.startswith("FOUND"):
                    hits.append([int(t) for t in ln.split("cols:")[1].split()])
                if ln.startswith("SUMMARY"):
                    tot += float(ln.split("sec=")[1])
            if hits:
                return W, hits, tot
    return None, [], tot


def cpsat(He, Le, tl=120, workers=4):
    from ortools.sat.python import cp_model
    md = cp_model.CpModel(); N = He.shape[1]
    x = [md.NewBoolVar("") for _ in range(N)]; one = md.NewConstant(1)
    for row in He:
        md.AddBoolXOr([x[j] for j in np.nonzero(row)[0]] + [one])
    bs = []
    for row in Le:
        b = md.NewBoolVar(""); bs.append(b)
        md.AddBoolXOr([x[j] for j in np.nonzero(row)[0]] + [b.Not()])
    md.AddBoolOr(bs); md.Minimize(sum(x))
    s = cp_model.CpSolver(); s.parameters.max_time_in_seconds = tl; s.parameters.num_workers = workers
    st = s.Solve(md)
    v = int(s.ObjectiveValue()) if st in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None
    return v, int(np.ceil(s.BestObjectiveBound() - 1e-6)), s.StatusName(st)


rng = random.Random(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
ninst = int(sys.argv[2]) if len(sys.argv) > 2 else 6
res = []
for t in range(ninst):
    perm = lambda: rng.sample(range(6), 6)
    kw = dict(xe=perm(), xo=perm(), ze=perm(), zo=perm())
    for kind in "ZX":
        d = ext(kind, **{k: v for k, v in kw.items()})
        path = f"results/E-013-audit/val_{t}_{kind}.txt"
        dump_instance(d, path)
        Wd, hits, sec = dfs_min(path)
        for h in hits:
            x = np.zeros(d["He"].shape[1], dtype=np.int64); x[h] = 1
            assert not ((d["He"] @ x) % 2).any() and ((d["Le"] @ x) % 2).any() and x.sum() == Wd
        v, lb, st = cpsat(d["He"], d["Le"])
        r = dict(inst=t, kind=kind, orders=kw, dfs_min=Wd, dfs_hits=len(hits), dfs_sec=round(sec, 1),
                 cpsat_val=v, cpsat_lb=lb, cpsat_status=st,
                 consistent=(Wd is None and (v is None or v >= 10)) or (Wd is not None and v is not None and v >= Wd and (st != "OPTIMAL" or v == Wd)))
        print(json.dumps(r), flush=True); res.append(r)
json.dump(res, open(f"results/E-013-audit/s5_validate_{sys.argv[1] if len(sys.argv)>1 else 1}.json", "w"), indent=1)
