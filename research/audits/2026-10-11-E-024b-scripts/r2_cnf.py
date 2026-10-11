"""Audit E-024b (r2): gsat-equivalent CEGAR (gsat.Enc + nwfull.evaluate_full + bf_P, own loop & own clause build)
run to UNSAT, then the FINAL CNF (family encoding + every nogood) is re-solved from scratch with two other SAT
solvers (Glucose4, MiniSat22) to rule out a solver artefact.
    PYTHONPATH=.:tests uv run python research/audits/2026-10-11-E-024b-scripts/r2_cnf.py P nowrap max_sec
"""
import json, sys, time
from pysat.solvers import Cadical153, Glucose4, Minisat22
import search.experiments.e024b.gsat as G
import search.experiments.e021.nwfull as NF
from search.experiments.e024b.gen import Cls, bf_P, build_family, prepare

P, nowrap, maxs = int(sys.argv[1]), int(sys.argv[2]), float(sys.argv[3])
X = "A1A2A3B3B1B2,A1A2A3B1B2B3,A1A3A2B3B1B2"; Z = "A1A3A2B3B1B2,A1A2A3B1B2B3,A1A2A3B3B1B2"
C = Cls((3, 1, 1), X, Z); F, ccol = build_family((3, 1, 1)); recs, sk = prepare(F, C)
clauses = []
orig_add = None


class Rec(Cadical153):
    def add_clause(self, cl, no_return=True):
        clauses.append(list(cl)); return super().add_clause(cl, no_return)


G.Cadical153 = Rec
t0 = time.time()
M = G.Enc(F, C, ccol, P, nowrap)
n_family = len(clauses)
status, it = "UNKNOWN", 0
while time.time() - t0 < maxs:
    it += 1
    if not M.S.solve(): status = "UNSAT"; break
    t, st = M.times(M.S.get_model())
    NF.bf_general = lambda cons, rank: bf_P(cons, t, P)
    lif = NF.evaluate_full(F, recs, None)
    if not lif: status = "CANDIDATE"; break
    for r, cons, pi in lif:
        lits = set()
        for u, w, kd, (i1, i2) in cons:
            K = pi[u] - pi[w]
            lits.add(-M.D(i1, i2, (K - 1) * P) if kd in ("free", "hook+") else M.D(i1, i2, -K * P))
        M.S.add_clause(sorted(lits))
res = {"P": P, "nowrap": nowrap, "status": status, "iters": it, "clauses": len(clauses), "family_clauses": n_family,
       "sec": round(time.time() - t0, 1)}
if status == "UNSAT":
    for nm, Sv in (("cadical_fresh", Cadical153), ("glucose4", Glucose4), ("minisat22", Minisat22)):
        t1 = time.time()
        with Sv(bootstrap_with=clauses) as s2:
            if nm == "cadical_fresh":
                r_ = s2.solve()
            else:
                s2.conf_budget(int(sys.argv[4]) if len(sys.argv) > 4 else 2000000); r_ = s2.solve_limited()
            res[nm] = {True: "SAT", False: "UNSAT", None: "BUDGET"}[r_]
            res[nm + "_sec"] = round(time.time() - t1, 1)
        print(nm, res[nm], res[nm + "_sec"], flush=True)
    # sanity: family clauses alone are SAT (the family is non-empty)
    with Glucose4(bootstrap_with=clauses[:n_family]) as s3:
        res["family_only"] = "SAT" if s3.solve() else "UNSAT"
print(json.dumps(res), flush=True)
json.dump(res, open(f"results/E-024b-audit/r2_cnf_P{P}{'nw' if nowrap else ''}.json", "w"))
