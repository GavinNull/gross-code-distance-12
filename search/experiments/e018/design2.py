"""E-018 stage c: CP-SAT existence question "is there a non-wrapping frame schedule (depth P, Fig. 12 per-check CNOT
orders, data-conflict-free, deterministic) in which EVERY single-hook weight-11 logical (10 data + one r2 hook) is
blocked in the frame model?"  Blocking certificate = a 0-weight chain (any length) from a check that reads a hook
qubit before the hook lands to a check that reads a hook qubit after it lands; consecutive checks share a free qubit
w of Q and the first reads w later than the second (h(first) <= h(second)).  Encoded with reachability booleans and
integer ranks (no length bound).  Only checks with |Q∩c| = 2 are used in chains (so certificates are sound in the
frame model also when some |Q∩c| = 4).

In the frame model (bulk, pure-data realisations of the data columns, disjoint supports) this certificate is also
necessary for blocking a single-hook logical: a negative cycle must pass the hook variable F through the single -1
edge (before-check -> F) and return through 0-weight edges only (all other edge weights are 0 or +1).
So INFEASIBLE here => every such schedule has a single-hook logical that lifts in the bulk (modulo the |Q∩c|=4
restriction, reported).

    PYTHONPATH=.:tests uv run python -m search.experiments.e018.design2 --mode sym --P 16
    PYTHONPATH=.:tests uv run python -m search.experiments.e018.design2 --mode free --P 14
"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np
from ortools.sat.python import cp_model

from search.experiments.e018.anal import comp
from search.experiments.e018.common import css, ext, orders
from search.experiments.e018.frame_model import column_events
from search.experiments.e018.gen import XCOL, ZCOL
from search.experiments.e018.lift import KIND_OF_BASIS
from search.experiments.e018.screen import logicals


def build(P, mode, bases, types, n4_policy="exclude", assume=False):
    xo, zo = orders()
    m = cp_model.CpModel()
    if mode == "sym":
        tc = [[m.NewIntVar(1, P - 2, "") for _ in range(6)] for _ in range(6)]
        key = {("X", i): int(XCOL[i]) for i in range(72)} | {("Z", j): 3 + int(ZCOL[j]) for j in range(72)}
        tv = {k: tc[c] for k, c in key.items()}
        uniq = [tc[c] for c in range(6)]
    else:
        tv = {(k, i): [m.NewIntVar(1, P - 2, "") for _ in range(6)] for k in "XZ" for i in range(72)}
        uniq = list(tv.values())
    for v in uniq:
        for k in range(5):
            m.Add(v[k + 1] > v[k])
    pos = {("X", i): {q: k for k, q in enumerate(xo[i])} for i in range(72)} | \
          {("Z", j): {q: k for k, q in enumerate(zo[j])} for j in range(72)}

    def T(k, i, q):
        return tv[(k, i)][pos[(k, i)][q]]
    # data conflicts
    touch = [[] for _ in range(144)]
    for k, ords in (("X", xo), ("Z", zo)):
        for i, o in enumerate(ords):
            for q in o:
                touch[q].append((k, i))
    done = set()
    for q in range(144):
        exprs = [T(k, i, q) for k, i in touch[q]]
        sig = tuple(sorted(id(e) for e in exprs))
        if sig in done:
            continue
        done.add(sig)
        m.AddAllDifferent(exprs)
    lits = {}

    def later(kx, x, ky, y, q):
        kk = (kx, x, ky, y, q)
        if kk not in lits:
            if (ky, y, kx, x, q) in lits:
                lits[kk] = lits[(ky, y, kx, x, q)].Not()
            else:
                b = m.NewBoolVar("")
                m.Add(T(kx, x, q) > T(ky, y, q)).OnlyEnforceIf(b)
                m.Add(T(kx, x, q) < T(ky, y, q)).OnlyEnforceIf(b.Not())
                lits[kk] = b
        return lits[kk]
    # determinism
    for i in range(72):
        for j in range(72):
            sh = sorted(set(xo[i]) & set(zo[j]))
            if sh:
                u, v = sh
                m.Add(later("X", i, "Z", j, u) == later("X", i, "Z", j, v))
    n4 = 0
    nS = 0
    m.assume_lits = []
    for basis in bases:
        kind = KIND_OF_BASIS[basis]
        rk = "Z" if kind == "X" else "X"
        rd_ords = zo if kind == "X" else xo
        E = ext(kind)
        for S in logicals(kind, mode == "sym"):
            if comp(E, S) not in types:
                continue
            nS += 1
            evs = [column_events(kind, j) for j in S]
            (_, a, res), = [e for e in evs if e[0] == "h"]
            free = [e[1] for e in evs if e[0] == "d"]
            Q = set(free) | set(res)
            rchk = {q: [c for c, o in enumerate(rd_ords) if q in o] for q in Q}
            qc = {}
            for q in Q:
                for c in rchk[q]:
                    qc.setdefault(c, []).append(q)
            good = {c for c, l in qc.items() if len(l) == 2}
            n4 += sum(len(l) > 2 for l in qc.values())
            nodes = sorted(good)
            R = {c: m.NewBoolVar("") for c in nodes}
            rank = {c: m.NewIntVar(0, len(nodes), "") for c in nodes}
            tgt = []
            for c in nodes:
                supp = []
                base = [later(kind, a, rk, c, q) for q in qc[c] if q in res]     # hook lands after c reads q
                if base:
                    supp += base
                    tgt += [(c, later(rk, c, kind, a, q)) for q in qc[c] if q in res]
                for w in qc[c]:
                    if w in res:
                        continue
                    for d in rchk[w]:
                        if d == c or d not in good:
                            continue
                        e = m.NewBoolVar("")
                        m.AddImplication(e, R[d])
                        m.AddImplication(e, later(rk, d, rk, c, w))           # d reads w later than c
                        m.Add(rank[d] < rank[c]).OnlyEnforceIf(e)
                        supp.append(e)
                if supp:
                    m.AddBoolOr(supp).OnlyEnforceIf(R[c])
                else:
                    m.Add(R[c] == 0)
            fin = []
            for c, aft in tgt:
                f = m.NewBoolVar("")
                m.AddImplication(f, R[c]); m.AddImplication(f, aft)
                fin.append(f)
            if assume:
                lit = m.NewBoolVar(f"S{nS - 1}")
                m.AddBoolOr(fin).OnlyEnforceIf(lit)
                m.assume_lits.append((lit, basis, S))
            else:
                m.AddBoolOr(fin)
    return m, tv, nS, n4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--P", type=int, default=16)
    ap.add_argument("--mode", default="sym")
    ap.add_argument("--bases", default="ZX")
    ap.add_argument("--types", default="d10 r21")
    ap.add_argument("--time", type=float, default=900)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    t0 = time.time()
    m, tv, nS, n4 = build(a.P, a.mode, a.bases, a.types.split(","))
    print(f"model built: {nS} logicals, {n4} check incidences with |Q∩c|>2 excluded from chains, {time.time() - t0:.0f}s",
          flush=True)
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = a.time
    s.parameters.num_workers = a.workers
    st = s.Solve(m)
    res = {"P": a.P, "mode": a.mode, "bases": a.bases, "types": a.types, "status": s.StatusName(st),
           "sec": round(time.time() - t0, 1), "nS": nS, "n4": n4}
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        res["times"] = {f"{k}{i}": [s.Value(x) for x in v] for (k, i), v in tv.items()}
    print(json.dumps({k: v for k, v in res.items() if k != "times"}), flush=True)
    json.dump(res, open(a.out, "w"))


if __name__ == "__main__":
    main()
