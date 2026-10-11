"""Audit E-024b (t1): soundness of gsat's nogoods against the EXACT stim DEM (own lift, b_common/b3 style).
For colour-symmetric Fig. 12-class circuits at period P:
  A (model): for circuits B (random family members from gsat.Enc without logical nogoods, and CEGAR models), every
    rep logical S that the frame model claims lifts on B (evaluate_full + bf_P with B's times) must lift exactly in
    B's stim DEM at R = span(pi) + 3 (retry + 3) -- with the claimed 11 column keys.
  B (clause): nogood clauses (cons, pi) collected along a CEGAR run; on a random family circuit B, a clause whose
    literals are ALL false (evaluated directly from the clause's arithmetic conditions on B's times) excludes B, so S
    must lift exactly on B.  Also checks bf_P(cons, t_B) is feasible in that case.
    PYTHONPATH=.:tests uv run python research/audits/2026-10-11-E-024b-scripts/t1_nogood.py P nowrap n_cegar n_rand
"""
import json, random, sys, time
sys.path.insert(0, "research/audits/2026-10-11-E-024b-scripts")
from b_common import *          # HX, HZ, LX, LZ, dem_groups, parse_schedule (evaluator)
from ortools.sat.python import cp_model
import search.experiments.e024b.gsat as G
import search.experiments.e021.nwfull as NF
from search.experiments.e024b.gen import Cls, bf_P, build_family, prepare

P, nowrap, NC, NR = (int(v) for v in sys.argv[1:5])
ALL = len(sys.argv) > 5 and sys.argv[5] == "all"     # A-test on EVERY claim of the random circuits, stratified
X = "A1A2A3B3B1B2,A1A2A3B1B2B3,A1A3A2B3B1B2"; Z = "A1A3A2B3B1B2,A1A2A3B1B2B3,A1A2A3B3B1B2"
col = (3, 1, 1)
C = Cls(col, X, Z); F, ccol = build_family(col); recs, skipped = prepare(F, C)
rng = random.Random(4242 + P)


def key_of(kind, j):
    H, L = (HZ, LZ) if kind == "X" else (HX, LX)
    v = np.zeros(144, np.uint8); v[list(C.E[kind]["col_sups"][j][0])] = 1
    return ((H @ v) % 2).astype(np.uint8).tobytes() + ((L @ v) % 2).astype(np.uint8).tobytes()


def lifts(S, groups):
    M = cp_model.CpModel(); one = M.NewConstant(1); dl = {}
    for key in S:
        vs = []
        for dets in groups[key]:
            v = M.NewBoolVar(""); vs.append(v)
            for d in dets: dl.setdefault(d, []).append(v)
        M.AddExactlyOne(vs)
    for d, ls in dl.items(): M.AddBoolXOr(ls + [one])
    s = cp_model.CpSolver(); s.parameters.num_workers = 1
    st = s.Solve(M)
    assert st in (cp_model.OPTIMAL, cp_model.FEASIBLE, cp_model.INFEASIBLE)
    return st != cp_model.INFEASIBLE


cache = {}
def exact(t, st, r, pi):
    d = G.spec_of(F, t, st, P); sp = parse_schedule(d); h = sp.hash()
    kind = r["kind"]; basis = BASIS_OF_KIND[kind]
    S = [key_of(kind, j) for j in r["S"]]
    span = max(pi.values()) - min(pi.values())
    for R in (span + 3, span + 6):
        k = (h, R, basis)
        if k not in cache:
            if len(cache) > 12: cache.clear()
            cache[k] = dem_groups(sp, R, basis)[0]
        g = cache[k]
        assert all(x in g for x in S)
        if lifts(S, g): return R
    return None


def claims(t):
    NF.bf_general = lambda cons, rank: bf_P(cons, t, P)
    return NF.evaluate_full(F, recs, None)


def lit_true(cons, pi, t):
    out = []
    for u, w, kd, (i1, i2) in cons:
        K = pi[u] - pi[w]; dlt = t[i2] - t[i1]
        out.append(dlt <= (K - 1) * P - 1 if kd in ("free", "hook+") else dlt >= -K * P)
    return any(out)


t0 = time.time()
res = {"P": P, "nowrap": nowrap, "A_checked": 0, "A_fail": [], "B_checked": 0, "B_fail": [], "B_bf_infeasible": 0,
       "pool": 0, "cegar_iters": 0}
# CEGAR run (gsat logic, own loop) collecting models + nogoods
M = G.Enc(F, C, ccol, P, nowrap)
pool, cmodels = [], []
for it in range(NC):
    if not M.S.solve(): res["cegar_status"] = "UNSAT"; break
    t, st = M.times(M.S.get_model()); lif = claims(t)
    cmodels.append((t, st, lif))
    if not lif: res["cegar_status"] = "CANDIDATE"; break
    for r, cons, pi in lif:
        pool.append((r, cons, pi))
        lits = set()
        for u_, w_, kd, (i1, i2) in cons:
            K = pi[u_] - pi[w_]
            lits.add(-M.D(i1, i2, (K - 1) * P) if kd in ("free", "hook+") else M.D(i1, i2, -K * P))
        M.S.add_clause(sorted(lits))
    res["cegar_iters"] = it + 1
res["pool"] = len(pool)
print("cegar", res["cegar_iters"], "pool", len(pool), round(time.time() - t0), flush=True)
# random family members (no logical nogoods)
M0 = G.Enc(F, C, ccol, P, nowrap); rmodels = []
for k in range(NR):
    M0.S.set_phases([v if rng.random() < 0.5 else -v for v in range(1, M0.pool.top + 1)])
    if not M0.S.solve(): break
    t, st = M0.times(M0.S.get_model()); rmodels.append((t, st))
    M0.S.add_clause([-M0.x[(i, v)] for i, v in t.items()])
# A: model soundness
for idx, (t, st, lif) in enumerate([(t, st, lif) for t, st, lif in cmodels[::max(1, len(cmodels) // 8)]] +
                                    [(t, st, claims(t)) for t, st in rmodels]):
    for r, cons, pi in (lif if ALL else rng.sample(lif, min(6, len(lif)))):
        R = exact(t, st, r, pi); res["A_checked"] += 1
        nh = sum(e[0] == "h" for e in r["evs"]); pairing = max(len(v) for v in r["rc"].values()) > 2
        sk = f"hooks{nh}{'_pairing' if pairing else ''}"
        res.setdefault("A_strata", {}).setdefault(sk, [0, 0]); res["A_strata"][sk][0] += 1
        if R is None: res["A_fail"].append((idx, r["kind"], r["S"]))
        else: res["A_strata"][sk][1] += 1
    print("A", idx, res["A_checked"], len(res["A_fail"]), round(time.time() - t0), flush=True)
# B: clause soundness on random members
for idx, (t, st) in enumerate(rmodels):
    excl = [(r, cons, pi) for r, cons, pi in pool if not lit_true(cons, pi, t)]
    for r, cons, pi in rng.sample(excl, min(6, len(excl))):
        if bf_P(cons, t, P) is None: res["B_bf_infeasible"] += 1
        R = exact(t, st, r, pi); res["B_checked"] += 1
        if R is None: res["B_fail"].append((idx, r["kind"], r["S"]))
    print("B", idx, "excluded-by", len(excl), "checked", res["B_checked"], len(res["B_fail"]), round(time.time() - t0), flush=True)
res["sec"] = round(time.time() - t0)
print(json.dumps(res), flush=True)
json.dump(res, open(f"results/E-024b-audit/t1_nogood_P{P}{'nw' if nowrap else ''}{'_all' if ALL else ''}.json", "w"), indent=1)
