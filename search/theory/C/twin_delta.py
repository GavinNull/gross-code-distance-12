"""Question C: for a twin pair (X_r, Z_r) test each relative offset delta under a relaxation R(S).
usage: uv run python -m search.theory.C.twin_delta results/theory-C/W8.pkl r  S(comma idx or 'touch'|'all') tmax"""
import sys, time
from pysat.solvers import Cadical153
from search.experiments.e036_audit.core import support
from search.theory.C.project import load
D = load(sys.argv[1]); ks = D["ks"]; r = int(sys.argv[2]); tmax = float(sys.argv[4])
ix, iz = ks.index(("X", r)), ks.index(("Z", r))
if sys.argv[3] == "touch":
    Q = set(support(("X", r))); S = {i for i, k in enumerate(ks) if Q & set(support(k))}
elif sys.argv[3] == "all":
    S = set(range(14))
else:
    S = {int(x) for x in sys.argv[3].split(",")}
print("S", sorted(S), len(S))
cl = list(D["base"]) + [c for tag, t, c in D["tagged"] if tag <= S]
pe = D["pi_eq"]
for d in range(8):
    sol = Cadical153(bootstrap_with=cl)
    # pi_Z - pi_X = d (mod 8): disjunction over absolute values
    sel = []
    for a in range(8):
        la, lb = pe[ix].get(a, False), pe[iz].get((a + d) % 8, False)
        if la is False or lb is False: continue
        y = D["nv"] + 1 + len(sel); sel.append(y)
        for l in (la, lb):
            if l is not True: sol.add_clause([-y, l])
    sol.add_clause(sel)
    t0 = time.time()
    sol.conf_budget(10**9)
    import threading
    timer = threading.Timer(tmax, sol.interrupt); timer.start()
    res = sol.solve_limited(expect_interrupt=True); timer.cancel()
    print("delta", d, {True: "SAT", False: "UNSAT", None: "timeout"}[res], round(time.time() - t0, 1), flush=True)
    sol.delete()
