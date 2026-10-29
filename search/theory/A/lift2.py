"""Theory A: multi-hook configurations.  For a signature and a side, enumerate (CP-SAT, no-good cuts) extended
logicals of weight <= d-1 built from data columns and the order's hooks S2, S3, S4 at every check (hook at check 0
used, by translation invariance), and decide each one's bulk lift with data cuts and readout flips (budget d-1-w).

    uv run python search/theory/A/lift2.py --code bb90 --src surv_bb90_P10r.pkl --K 300
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from collections import Counter

import numpy as np
from ortools.sat.python import cp_model

sys.path.insert(0, "search/theory/A")
from common import Code  # noqa: E402
from lift import OUT, RR, Bulk  # noqa: E402
from sigs import LAB  # noqa: E402


def ext_logicals(C, kind, order, wmax, K, tl=120.0):
    Hk, Rd, H, L = C.side(kind)
    sufs = [frozenset(order[k:]) for k in (2, 3, 4)]       # sizes 4, 3, 2
    m = cp_model.CpModel()
    x = [m.NewBoolVar("") for _ in range(C.n)]
    y = {(c, i): m.NewBoolVar("") for c in range(C.N2) for i in range(3)}
    m.AddBoolOr([y[(0, i)] for i in range(3)])
    cols = {q: [x[q]] for q in range(C.n)}
    for (c, i), v in y.items():
        for s in sufs[i]:
            cols[int(Hk[c][s])].append(v)
    for r in range(H.shape[0]):
        lits = [l for q in np.nonzero(H[r])[0] for l in cols[q]]
        k = m.NewIntVar(0, len(lits) // 2, "")
        m.Add(sum(lits) == 2 * k)
    us = []
    for r in range(L.shape[0]):
        u = m.NewBoolVar("")
        m.AddBoolXOr([l for q in np.nonzero(L[r])[0] for l in cols[q]] + [u.Not()])
        us.append(u)
    m.AddBoolOr(us)
    allv = x + list(y.values())
    m.Add(sum(allv) <= wmax)
    out = []
    t0 = time.time()
    while len(out) < K and time.time() - t0 < tl:
        sv = cp_model.CpSolver()
        sv.parameters.max_time_in_seconds = 20
        sv.parameters.num_workers = 1
        st = sv.Solve(m)
        if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            break
        data = [q for q in range(C.n) if sv.Value(x[q])]
        hk = [(c, sorted(sufs[i])) for (c, i), v in y.items() if sv.Value(v)]
        out.append((data, hk))
        m.AddBoolOr([v.Not() for v in allv if sv.Value(v)])
    return out


def solve_multi(bk, hooks, data, budget):
    P = bk.P
    m = cp_model.CpModel()
    contrib = {}

    def add(c, v, lit):
        contrib.setdefault((c, v), []).append(lit)
    for (c0, S) in hooks:
        rr = {r: m.NewBoolVar("") for r in RR}
        m.AddExactlyOne(rr.values())
        for r, lit in rr.items():
            for a in S:
                q = int(bk.Hk[c0][a])
                for c, v in bk.idx(q, 2 * (bk.tH[a] + r * P)):
                    add(c, v, lit)
    for q in data:
        opts = []
        for (c0, b0) in bk.readers[q]:
            for n in RR:
                lit = m.NewBoolVar("")
                opts.append(lit)
                for c, v in bk.idx(q, 2 * (bk.tR[b0] + n * P) + 1):
                    add(c, v, lit)
        m.AddExactlyOne(opts)
    vs = [v for c, v in contrib]
    lo, hi = min(vs) - 1, max(vs) + 1
    flips = []
    for c in sorted({c for c, v in contrib}):
        f = {v: m.NewBoolVar("") for v in range(lo, hi + 1)}
        flips += list(f.values())
        for v in range(lo, hi + 2):
            lits = contrib.get((c, v), []) + [f[u] for u in (v, v - 1) if u in f]
            if lits:
                k = m.NewIntVar(0, len(lits) // 2, "")
                m.Add(sum(lits) == 2 * k)
    m.Add(sum(flips) <= budget)
    m.Minimize(sum(flips))
    sv = cp_model.CpSolver()
    sv.parameters.num_workers = 1
    sv.parameters.max_time_in_seconds = 20
    st = sv.Solve(m)
    return int(sv.ObjectiveValue()) if st in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--src", required=True)
    ap.add_argument("--P", type=int, default=10)
    ap.add_argument("--K", type=int, default=300)
    a = ap.parse_args()
    C = Code(a.code)
    d = C.d
    sv = pickle.load(open(OUT / a.src, "rb"))
    cache = {}
    res = []
    for sig, (tx, tz) in zip(sv["surv"], sv["times"]):
        best = None
        for kind, order, tH, tR in (("X", sig[0], tx, tz), ("Z", sig[1], tz, tx)):
            if (kind, order) not in cache:
                cache[(kind, order)] = ext_logicals(C, kind, order, d - 1, a.K)
            bk = Bulk(C, kind, list(tH), list(tR), a.P)
            for data, hk in cache[(kind, order)]:
                w = len(data) + len(hk)
                fl = solve_multi(bk, hk, data, d - 1 - w)
                if fl is not None and (best is None or w + fl < best[0]):
                    best = (w + fl, kind, w, len(hk))
                    break
            if best:
                break
        res.append(best)
        print([LAB[i] for i in sig[0]], [LAB[i] for i in sig[1]], sig[2], best,
              "nlog", {k[0]: len(v) for k, v in cache.items() if k[1] in (sig[0], sig[1])}, flush=True)
    print(json.dumps({"n": len(res), "killed": sum(1 for b in res if b), "hist": dict(Counter(map(str, res)))}))
    pickle.dump({"surv": sv["surv"], "times": sv["times"], "res": res}, open(OUT / ("lift2_" + a.src), "wb"))


if __name__ == "__main__":
    main()
