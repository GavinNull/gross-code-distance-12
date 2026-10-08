"""Audit E-018 (a5): independent CP-SAT encoding of "can a schedule block every Z-basis single-hook logical in the
bulk model?"  Different from design2/design3 (which guess a chain/path certificate with rank variables): here the
Bellman-Ford recursion is unrolled exactly (AddMinEquality), D_0 = 0, D_{k+1}[v] = min(D_k[v], min_u D_k[u] + w_uv),
and "blocked" <=> D_n != D_{n-1} for some node (n = number of nodes) <=> a negative cycle exists.
Schedule family (evaluator rules): per check (mode free) or per (type, colour) class (mode sym): prep s in [0,P-1]
(s = 0 in --nowrap mode: non-wrapping frame), CNOT offsets 1 <= o1 < ... < o6 <= P-2.  Data-conflict-free,
deterministic (floor-equality criterion, validated vs stim in a4).
    PYTHONPATH=.:tests uv run python research/audits/2026-10-08-E-018-scripts/a5_cpsat.py --P 9 --mode sym
"""
import argparse, json, sys, time, itertools
sys.path.insert(0, "research/audits/2026-10-08-E-018-scripts")
from ortools.sat.python import cp_model
from a1_common import xo, zo, xcol, zcol, tr
from a3_model import single_hook_logicals, ZREAD

ap = argparse.ArgumentParser()
ap.add_argument("--P", type=int, required=True)
ap.add_argument("--mode", default="sym")
ap.add_argument("--nowrap", action="store_true")
ap.add_argument("--time", type=float, default=600)
ap.add_argument("--workers", type=int, default=1)
ap.add_argument("--nlog", type=int, default=0, help="use only the first n logicals (0 = all applicable)")
ap.add_argument("--orbit_reps", action="store_true", help="sym mode: one logical per 24-orbit")
a = ap.parse_args()
P = a.P
m = cp_model.CpModel()
key = (lambda chk: (chk[0], xcol[chk[1]] if chk[0] == "X" else zcol[chk[1]])) if a.mode == "sym" else (lambda chk: chk)
allchk = [("X", i) for i in range(72)] + [("Z", j) for j in range(72)]
var = {}
for chk in allchk:
    k = key(chk)
    if k in var: continue
    s = m.NewConstant(0) if a.nowrap else m.NewIntVar(0, P - 1, f"s{k}")
    o = [m.NewIntVar(1, P - 2, f"o{k}{i}") for i in range(6)]
    for i in range(5): m.Add(o[i + 1] > o[i])
    var[k] = (s, o)
if a.mode == "sym" and not a.nowrap:
    m.Add(var[("X", 0)][0] == 0)       # global time shift
ORD = {("X", i): xo[i] for i in range(72)} | {("Z", j): zo[j] for j in range(72)}
Tc = {}
def T(chk, q):
    kk = (key(chk), ORD[chk].index(q))
    if kk not in Tc:
        s, o = var[kk[0]]
        t = m.NewIntVar(1, 2 * P - 3, ""); m.Add(t == s + o[kk[1]]); Tc[kk] = t
    return Tc[kk]
Fc = {}
def fl(c1, c2, q):
    """floor((T(c1,q) - T(c2,q)) / P)"""
    t1, t2 = T(c1, q), T(c2, q)
    kk = (t1.Index(), t2.Index())
    if kk not in Fc:
        f = m.NewIntVar(-2, 1, "")
        m.Add(t1 - t2 >= f * P); m.Add(t1 - t2 <= f * P + P - 1); Fc[kk] = f
    return Fc[kk]
# data conflicts: pairwise T != T (mod P)  <=>  T1 - T2 not in {-P, 0, P}
touch = {}
for chk in allchk:
    for q in ORD[chk]: touch.setdefault(q, []).append(chk)
seen = set()
for q, l in touch.items():
    for c1, c2 in itertools.combinations(l, 2):
        t1, t2 = T(c1, q), T(c2, q)
        kk = tuple(sorted((t1.Index(), t2.Index())))
        if kk in seen or t1.Index() == t2.Index(): continue
        seen.add(kk)
        for d in (-P, 0, P):
            m.Add(t1 - t2 != d)
# determinism
for i in range(72):
    for j in range(72):
        sh = sorted(set(xo[i]) & set(zo[j]))
        if sh:
            u, v = sh
            m.Add(fl(("X", i), ("Z", j), u) == fl(("X", i), ("Z", j), v))
LOG = single_hook_logicals("X")
if a.mode == "sym" and a.orbit_reps:
    G = []
    ords_set = {tuple(o): i for i, o in enumerate(xo)}
    for aa in range(12):
        for bb in range(6):
            p = tr(aa, bb); pp = p + [x + 72 for x in p]
            if all(tuple(pp[q] for q in o) in ords_set and xcol[ords_set[tuple(pp[q] for q in o)]] == xcol[i] for i, o in enumerate(xo)):
                G.append(pp)
    reps, seen_l = [], set()
    for L in LOG:
        if (tuple(sorted(L[0])), L[1], tuple(sorted(L[2]))) in seen_l: continue
        reps.append(L)
        for pp in G:
            fr = tuple(pp[q] for q in L[0]); r = tuple(pp[q] for q in L[2])
            ai = ords_set[tuple(pp[q] for q in xo[L[1][1]])]
            seen_l.add((tuple(sorted(fr)), ("X", ai), tuple(sorted(r))))
    LOG = reps
if a.nlog: LOG = LOG[:a.nlog]
import os
if os.environ.get("SELECT"):      # e.g. "7:9,25;46:42,64" -> first logical with that hook check and residual
    sel = []
    for item in os.environ["SELECT"].split(";"):
        if item.startswith("F"):
            fr = tuple(sorted(map(int, item[1:].split(","))))
            sel.append(next(L for L in LOG if tuple(sorted(L[0])) == fr)); continue
        ci, r = item.split(":"); r = tuple(sorted(map(int, r.split(","))))
        sel.append(next(L for L in LOG if L[1] == ("X", int(ci)) and tuple(sorted(L[2])) == r))
    LOG = sel
LB = -64
BS = []
for (free, hk, res) in LOG:
    nodes = ["F"] + sorted({c for q in list(free) + list(res) for c in ZREAD[q]})
    idx = {c: i for i, c in enumerate(nodes)}
    edges = []                           # (u, v, weight expr): D[v] <= D[u] + w
    for w in free:
        for c in ZREAD[w]:
            for d in ZREAD[w]:
                if c != d:   # H_c - H_d <= floor((T_d - T_c)/P) + 1 : edge d -> c
                    edges.append((idx[d], idx[c], fl(d, c, w) + 1))
    for q in res:
        for c in ZREAD[q]:
            off = fl(hk, c, q) + 1      # H_c = F + off
            edges.append((0, idx[c], off)); edges.append((idx[c], 0, -off))
    n = len(nodes)
    D = [[m.NewConstant(0) for _ in range(n)]]
    for k in range(n):
        nxt = []
        for v in range(n):
            cands = [D[-1][v]]
            for u, vv, w in edges:
                if vv == v:
                    x = m.NewIntVar(LB - 2, 2, ""); m.Add(x == D[-1][u] + w); cands.append(x)
            y = m.NewIntVar(LB, 0, ""); m.AddMinEquality(y, cands); nxt.append(y)
        D.append(nxt)
    lits = []
    for v in range(n):
        b = m.NewBoolVar(""); m.Add(D[n][v] < D[n - 1][v]).OnlyEnforceIf(b); lits.append(b)
    if os.environ.get("MAXIMIZE"):
        bS = m.NewBoolVar(""); m.AddBoolOr(lits).OnlyEnforceIf(bS); BS.append(bS)
    else:
        m.AddBoolOr(lits)
if os.environ.get("MAXIMIZE"):
    m.Maximize(sum(BS))
t0 = time.time()
s = cp_model.CpSolver(); s.parameters.max_time_in_seconds = a.time; s.parameters.num_workers = a.workers
st = s.Solve(m)
res = {"P": P, "mode": a.mode, "nowrap": a.nowrap, "nlog": len(LOG), "status": s.StatusName(st),
       "max_blocked": (s.ObjectiveValue() if os.environ.get("MAXIMIZE") and st in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None),
       "bound": (s.BestObjectiveBound() if os.environ.get("MAXIMIZE") else None),
       "sec": round(time.time() - t0, 1)}
if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
    res["sched"] = {str(k): [s.Value(v[0]), [s.Value(x) for x in v[1]]] for k, v in var.items()}
print(json.dumps({k: v for k, v in res.items() if k != "sched"}))
json.dump(res, open(f"results/E-018-audit/a5_{a.mode}_P{P}{'_nowrap' if a.nowrap else ''}_n{len(LOG)}{'_sel' if os.environ.get('SELECT') else ''}{'_max' if os.environ.get('MAXIMIZE') else ''}.json", "w"))
