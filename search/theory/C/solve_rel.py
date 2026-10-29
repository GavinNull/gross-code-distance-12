"""Question C: full static CNF (legality + all tagged witness clauses) plus relative-offset constraints
pi_j - pi_i = d (mod P); one SAT call with a wall-clock cap.
usage: uv run python -m search.theory.C.solve_rel results/theory-C/W8.pkl tmax 'X0-Z0=0,X1-Z1=0'   (i-j=d means pi_j-pi_i=d)
       optional 4th arg: comma list of types to keep (default all), e.g. DDH"""
import sys, time, threading
from pysat.solvers import Cadical153
from search.theory.C.project import load

def name(k): return f"{k[0]}{k[1]}"

def rel_clauses(D, cons, nv0):
    """cons: list of (i, j, d).  returns clauses and new nv (selector vars)."""
    pe, P = D["pi_eq"], D["P"]; out = []; nv = nv0
    for i, j, d in cons:
        sel = []
        for a in range(P):
            la, lb = pe[i].get(a, False), pe[j].get((a + d) % P, False)
            if la is False or lb is False: continue
            nv += 1; sel.append(nv)
            for l in (la, lb):
                if l is not True: out.append([-nv, l])
        out.append(sel)
    return out, nv

def solve(D, cons, tmax, types=None):
    cl = list(D["base"]) + [c for tag, t, c in D["tagged"] if types is None or t in types]
    extra, _ = rel_clauses(D, cons, D["nv"] + 1000)
    sol = Cadical153(bootstrap_with=cl + extra)
    timer = threading.Timer(tmax, sol.interrupt); timer.start(); t0 = time.time()
    res = sol.solve_limited(expect_interrupt=True); timer.cancel()
    model = sol.get_model() if res else None
    sol.delete()
    return res, time.time() - t0, model

def parse(D, spec):
    idx = {name(k): i for i, k in enumerate(D["ks"])}
    cons = []
    for item in spec.split(","):
        if not item: continue
        lhs, d = item.split("=")
        a, b = lhs.split("-")
        cons.append((idx[a], idx[b], int(d)))
    return cons

if __name__ == "__main__":
    D = load(sys.argv[1]); tmax = float(sys.argv[2]); cons = parse(D, sys.argv[3])
    types = set(sys.argv[4].split(",")) if len(sys.argv) > 4 else None
    res, dt, _ = solve(D, cons, tmax, types)
    print({True: "SAT", False: "UNSAT", None: "timeout"}[res], round(dt, 1))
