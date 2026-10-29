"""Question C: projection of a sound relaxation onto the relative prep offsets of a check set S.
Relaxation R(S) = full legality + every tagged witness clause whose involved-check set is a subset of S.
Enumerates all relative offset tuples (pi_k - pi_{k0}) mod P, k in S, feasible for R(S) (blocking all P shifts).
usage: uv run python -m search.theory.C.project results/theory-C/W8.pkl 0,7,8,9  [--legal-only]"""
import pickle, sys, time
from pysat.solvers import Cadical153

def load(path):
    return pickle.load(open(path, "rb"))

def project(D, S, legal_only=False, tmax=1e9, extra=()):
    P = D["P"]; S = sorted(S)
    cl = list(D["base"])
    if not legal_only:
        cl += [c for tag, t, c in D["tagged"] if tag <= set(S)]
    cl += [list(c) for c in extra]
    sol = Cadical153(bootstrap_with=cl)
    pe = D["pi_eq"]
    def val(i, m):
        for v, l in pe[i].items():
            if l is True or (l is not False and (m[abs(l) - 1] > 0) == (l > 0)):
                return v
    out = set(); t0 = time.time(); calls = 0
    while time.time() - t0 < tmax:
        calls += 1
        if not sol.solve():
            break
        m = sol.get_model()
        vals = [val(i, m) for i in S]
        rel = tuple((v - vals[0]) % P for v in vals)
        out.add(rel)
        for s in range(P):
            ab = [(rel[j] + s) % P for j in range(len(S))]
            lits = [pe[i].get(a, False) for i, a in zip(S, ab)]
            if any(l is False for l in lits):
                continue
            sol.add_clause([-l for l in lits if l is not True])
    else:
        return out, False, time.time() - t0
    return out, True, time.time() - t0

if __name__ == "__main__":
    D = load(sys.argv[1]); S = [int(x) for x in sys.argv[2].split(",")]
    out, done, dt = project(D, S, "--legal-only" in sys.argv)
    print(len(out), "complete" if done else "INCOMPLETE", round(dt, 1))
