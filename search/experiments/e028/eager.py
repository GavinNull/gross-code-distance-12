"""E-028 step 1 (per-check free): eager clauses for "d_ext >= 9" from the code's low-weight logicals, then the lazy
DFS loop of dext.py.

For an X-type code logical l of weight w (codelog.py, weight 10 and 12; the list need not be complete, every clause is
individually valid) and disjoint residual label sets U_1..U_k (|U| in 2..4, U_i subset of l and of check a_i's support)
with sum(|U_i| - 1) >= w - 8, the columns {hook(a_i, U_i)} + data(l minus the U_i) form an extended logical of weight
w - sum(|U_i| - 1) <= 8.  So in any d_ext >= 9 assignment not all of these hook columns are present:
clause  OR_i  not present(key(a_i, U_i)).   Only inclusion-minimal selections are added.
Presence is defined exactly as in dext.py (type of a check realises a label set as a residual <=> some residual of
the order has that key).  UNSAT with eager clauses alone => no assignment (in the colouring) has d_ext >= 9.

    PYTHONPATH=.:tests uv run python -m search.experiments.e028.eager --kind X --sub "0,0" --lazy 1
"""
from __future__ import annotations

import argparse
import itertools
import json
import pickle
import time

from pysat.formula import IDPool
from pysat.solvers import Solver

from search.experiments.e028 import common as C
from search.experiments.e028.dext import cosets, dext_dfs, types

N2 = C.N2


def selections(cands, need):
    """inclusion-minimal sets of pairwise disjoint candidates (qubit-set, saving) with total saving >= need."""
    out = []
    n = len(cands)

    def rec(start, chosen, used, sav):
        if sav >= need:
            out.append(list(chosen)); return
        for i in range(start, n):
            qs, s = cands[i]
            if used & qs:
                continue
            chosen.append(i); rec(i + 1, chosen, used | qs, sav + s); chosen.pop()
    rec(0, [], frozenset(), 0)
    return out


def eager_clauses(kind, logicals, maxw=12):
    """list of tuples of hook keys (each tuple = one clause 'not all present')."""
    T = C.table()[kind]
    sup = [frozenset(int(q) for q in T[a]) for a in range(N2)]
    qcheck = {}
    for a in range(N2):
        for q in sup[a]:
            qcheck.setdefault(q, []).append(a)
    out = set()
    for l in logicals:
        w = len(l)
        if w > maxw:
            continue
        L = frozenset(l)
        cands = []
        for a in sorted({a for q in l for a in qcheck[q]}):
            inter = sorted(L & sup[a])
            for size in (2, 3, 4):
                for U in itertools.combinations(inter, size):
                    cands.append((frozenset(U), size - 1, a))
        for sel in selections([(c[0], c[1]) for c in cands], w - 8):
            ks = tuple(sorted({C.key_of(kind, sorted(cands[i][0])) for i in sel}))
            out.add(ks)
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True)
    ap.add_argument("--sub", required=True)
    ap.add_argument("--W", type=int, default=12, help="codelog list to use")
    ap.add_argument("--lazy", type=int, default=1)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--nsol", type=int, default=10)
    ap.add_argument("--max_sec", type=float, default=7200)
    ap.add_argument("--solver", default="cadical153")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    kind = a.kind
    T0 = time.time()
    gens = [tuple(int(v) for v in g.split(",")) for g in a.sub.split(";")]
    colv, m, perms, hs = cosets(gens)
    TY = types(kind)
    nt = len(TY)
    RS = [C.resid_sets(o) for o in TY]
    real = C.realisations(kind)
    logs = pickle.load(open(C.OUT / f"codelog_{kind}_W{a.W}.pkl", "rb"))
    ecl = eager_clauses(kind, logs)
    print(f"eager clauses {len(ecl)} from {len(logs)} logicals {time.time() - T0:.0f}s", flush=True)
    pool = IDPool()
    S = Solver(name=a.solver)
    x = [[pool.id(("x", c, t)) for t in range(nt)] for c in range(m)]
    for c in range(m):
        S.add_clause(x[c])
        for t1 in range(nt):
            for t2 in range(t1 + 1, nt):
                S.add_clause([-x[c][t1], -x[c][t2]])
    pres = {}

    def present(k):
        if k not in pres:
            p = pool.id(("p", k))
            for a_, U in real.get(k, []):
                c = colv[a_]
                for t in range(nt):
                    if U in RS[t]:
                        S.add_clause([-x[c][t], p])
            pres[k] = p
        return pres[k]

    nunreal = 0
    for ks in ecl:
        if not all(k in real for k in ks):
            nunreal += 1; continue
        S.add_clause([-present(k) for k in ks])
    print(f"added {len(ecl) - nunreal} clauses ({nunreal} with unrealisable keys) vars {pool.top}", flush=True)

    def add_witness_clauses(E, w):
        sups = [E["col_sups"][j][0] for j in w if not any(len(s_) == 1 for s_ in E["col_sups"][j])]
        for ga, gb in C.GROUP:
            _, pc = C.tr(ga, gb)
            S.add_clause(sorted({-present(C.key_of(kind, [int(pc[q]) for q in s_])) for s_ in sups}))

    def block(assign):
        for p in perms:
            S.add_clause([-x[p[c]][assign[c]] for c in range(m)])

    tag = f"eager_{kind}_" + a.sub.replace(";", "_").replace(",", "") + a.tag
    outp = C.OUT / f"{tag}.jsonl"
    if outp.exists():
        outp.unlink()
    status, ncalls, nsurv = "TIMEOUT", 0, 0
    while time.time() - T0 < a.max_sec:
        t1 = time.time()
        if not S.solve():
            status = "COMPLETE"; break
        tsat = time.time() - t1
        if not a.lazy:
            status = "SAT_EAGER"; break
        md = set(l for l in S.get_model() if l > 0)
        assign = tuple(next(t for t in range(nt) if x[c][t] in md) for c in range(m))
        E = C.ext_general(kind, [TY[assign[colv[i]]] for i in range(N2)])
        sols, nodes, complete = dext_dfs(E, 8, stopfirst=a.nsol, workers=a.workers)
        ncalls += 1
        rec = {"assign": list(assign), "orders": [C.name(TY[t]) for t in assign], "sat_sec": round(tsat, 2),
               "nodes": nodes}
        if sols:
            C.verify_logicals(E, sols)
            rec["witnesses"] = [list(w_) for w_ in sols]
            for w_ in sols:
                add_witness_clauses(E, w_)
        else:
            assert complete
            rec["survivor"] = True; nsurv += 1
            block(assign)
            print("SURVIVOR", json.dumps(rec), flush=True)
        with open(outp, "a") as f:
            f.write(json.dumps(rec) + "\n")
        if ncalls % 20 == 0:
            print(f"calls {ncalls} survivors {nsurv} last sat {tsat:.1f}s {time.time() - T0:.0f}s", flush=True)
    summ = {"kind": kind, "sub": a.sub, "colours": m, "eager": len(ecl), "status": status, "calls": ncalls,
            "survivors": nsurv, "sec": round(time.time() - T0, 1), "solver": a.solver}
    print("DONE", json.dumps(summ), flush=True)
    with open(C.OUT / "eager_summary.jsonl", "a") as f:
        f.write(json.dumps(summ) + "\n")


if __name__ == "__main__":
    main()
