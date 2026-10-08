"""E-018 stage c: CP-SAT design of class-level schedules (cpgen model) that BLOCK the single-hook weight-11 logicals
(10 data columns + one r2 hook), using chain certificates from the frame model:

  h(x0) = F+1 (x0 reads a hook qubit before the hook lands), h(x_m) = F (x_m reads a hook qubit after it lands),
  and h(x_k) <= h(x_{k+1}) whenever x_k and x_{k+1} share a free qubit w of Q and x_k reads w later than x_{k+1}.
  A chain x0 -> ... -> x_m gives F+1 <= F: infeasible, the logical does not lift (in the bulk, for pure data
  realisations of the data columns).  Sufficient, not necessary.  Chains up to length L are enumerated statically.

The candidate is then verified by the exact DP (lift.py) -- the certificate is only a design heuristic.

    PYTHONPATH=.:tests uv run python -m search.experiments.e018.design --P 14 --L 3
"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np
from ortools.sat.python import cp_model

from search.experiments.e018.anal import comp
from search.experiments.e018.common import ext, orders
from search.experiments.e018.cpgen import model
from search.experiments.e018.frame_model import column_events
from search.experiments.e018.gen import XCOL, ZCOL
from search.experiments.e018.lift import KIND_OF_BASIS
from search.experiments.e018.screen import logicals


def chains_for(S, kind, L):
    """Return (hook check index, hook qubits, list of chains); chain = (x0, q_start, [(x_k, x_k+1, w)...], x_m, q_end)."""
    xo, zo = orders()
    hk_ords, rd_ords = (xo, zo) if kind == "X" else (zo, xo)
    evs = [column_events(kind, j) for j in S]
    hooks = [e for e in evs if e[0] == "h"]
    assert len(hooks) == 1
    _, a, res = hooks[0]
    free = [e[1] for e in evs if e[0] == "d"]
    assert not set(free) & set(res)
    rchecks = {q: [i for i, o in enumerate(rd_ords) if q in o] for q in set(free) | set(res)}
    # adjacency on reading checks via shared free qubits
    adj = {}
    for w in free:
        cs = rchecks[w]
        for x in cs:
            for y in cs:
                if x != y:
                    adj.setdefault(x, []).append((y, w))
    chains = []
    for qs in res:
        for x0 in rchecks[qs]:
            stack = [(x0, [])]
            while stack:
                x, path = stack.pop()
                if path:
                    for qe in res:
                        if x in rchecks[qe] and not (x == x0):
                            chains.append((x0, qs, list(path), x, qe))
                if len(path) < L:
                    for y, w in adj.get(x, []):
                        if y == x0 or any(y == p[1] for p in path):
                            continue
                        stack.append((y, path + [(x, y, w)]))
    return a, res, chains


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--P", type=int, default=14)
    ap.add_argument("--L", type=int, default=3)
    ap.add_argument("--types", default="d10 r21")
    ap.add_argument("--time", type=float, default=600)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--bases", default="ZX")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    m, t, before, touch, pairs = model(a.P)
    xo, zo = orders()
    cls = {("X", i): int(XCOL[i]) for i in range(72)} | {("Z", j): 3 + int(ZCOL[j]) for j in range(72)}
    pos = {("X", i): {q: k for k, q in enumerate(xo[i])} for i in range(72)} | \
          {("Z", j): {q: k for k, q in enumerate(zo[j])} for j in range(72)}

    def T(kind, i, q):
        return t[cls[(kind, i)]][pos[(kind, i)][q]]
    lits = {}

    def later(kx, x, ky, y, q):            # check (kx,x) touches q later than (ky,y)
        key = (kx, x, ky, y, q)
        if key not in lits:
            b = m.NewBoolVar("")
            m.Add(T(kx, x, q) > T(ky, y, q)).OnlyEnforceIf(b)
            m.Add(T(kx, x, q) < T(ky, y, q)).OnlyEnforceIf(b.Not())
            lits[key] = b
        return lits[key]
    types = a.types.split(",")
    stats = []
    for basis in a.bases:
        kind = KIND_OF_BASIS[basis]                 # hooks of `kind` checks; reads by the other type
        rk = "Z" if kind == "X" else "X"
        E = ext(kind)
        for S in logicals(kind, True):
            if comp(E, S) not in types:
                continue
            h, res, chains = chains_for(S, kind, a.L)
            ors = []
            for x0, qs, path, xm, qe in chains:
                conj = [later(kind, h, rk, x0, qs)]          # hook lands after x0 reads qs: x0 reads before
                conj.append(later(rk, xm, kind, h, qe))      # xm reads qe after the hook lands
                for x, y, w in path:
                    conj.append(later(rk, x, rk, y, w))
                c = m.NewBoolVar("")
                m.AddBoolAnd(conj).OnlyEnforceIf(c)
                ors.append(c)
            stats.append((basis, len(chains)))
            if not ors:
                print(f"{basis} S={S}: no chain up to L={a.L} -> cannot block with certificates", flush=True)
                m.AddBoolOr([m.NewConstant(False)])
            else:
                m.AddBoolOr(ors)
    print("chains per logical:", stats, flush=True)
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = a.time
    s.parameters.num_workers = a.workers
    t0 = time.time()
    st = s.Solve(m)
    print(f"P={a.P} L={a.L}: {s.StatusName(st)} in {time.time() - t0:.0f}s", flush=True)
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        TT = [[s.Value(t[c][k]) for k in range(6)] for c in range(6)]
        print("times", TT, flush=True)
        json.dump({"P": a.P, "times": [TT]}, open(a.out, "w"))
    else:
        json.dump({"P": a.P, "status": s.StatusName(st)}, open(a.out, "w"))


if __name__ == "__main__":
    main()
