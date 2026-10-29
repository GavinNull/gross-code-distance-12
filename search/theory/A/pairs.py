"""(iii) For each code, side and term subset S of a check support: the minimum weight of a logical of that side that
contains the qubits of S (check at the origin), searched with CP-SAT up to weight d+1.  Witnesses are re-verified
by linear algebra.  Also the hook distance d(S) := min weight of (data columns + hook columns S_c, c any check)
forming an extended logical, restricted to configurations that use the hook at check 0 (translation invariance).

    uv run python search/theory/A/pairs.py gross X
"""
from __future__ import annotations

import itertools
import json
import sys
import time

import numpy as np
from ortools.sat.python import cp_model

sys.path.insert(0, "search/theory/A")
from common import Code  # noqa: E402

LAB = ["A1", "A2", "A3", "B1", "B2", "B3"]


def model_base(C, kind, wmax):
    T, R, H, L = C.side(kind)
    m = cp_model.CpModel()
    x = [m.NewBoolVar(f"x{q}") for q in range(C.n)]
    return m, x, T, R, H, L


def add_logical(m, terms_per_row_H, terms_per_row_L):
    for lits in terms_per_row_H:
        if lits:
            k = m.NewIntVar(0, len(lits) // 2, "")
            m.Add(sum(lits) == 2 * k)
    us = []
    for lits in terms_per_row_L:
        u = m.NewBoolVar("")
        m.AddBoolXOr(lits + [u.Not()])
        us.append(u)
    m.AddBoolOr(us)


def contains(C, kind, S, w, tl=60.0):
    """is there a logical of weight <= w containing qubits T[0][S]?  returns witness or None/'unknown'."""
    m, x, T, R, H, L = model_base(C, kind, w)
    for s in S:
        m.Add(x[int(T[0][s])] == 1)
    add_logical(m, [[x[q] for q in np.nonzero(H[i])[0]] for i in range(H.shape[0])],
                [[x[q] for q in np.nonzero(L[i])[0]] for i in range(L.shape[0])])
    m.Add(sum(x) <= w)
    sv = cp_model.CpSolver()
    sv.parameters.max_time_in_seconds = tl
    sv.parameters.num_workers = 1
    st = sv.Solve(m)
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        e = np.array([sv.Value(v) for v in x], dtype=np.uint8)
        assert not (H.astype(int) @ e % 2).any() and (L.astype(int) @ e % 2).any()
        assert all(e[int(T[0][s])] for s in S) and e.sum() <= w
        return [int(q) for q in np.nonzero(e)[0]]
    if st == cp_model.INFEASIBLE:
        return None
    return "unknown"


def main():
    name, kind = sys.argv[1], sys.argv[2]
    C = Code(name)
    d = C.d
    res = {}
    for size in (2, 3):
        for S in itertools.combinations(range(6), size):
            key = "".join(LAB[s] for s in S)
            t0 = time.time()
            out = {}
            for w in (d, d + 1):
                r = contains(C, kind, S, w)
                out[w] = r if not isinstance(r, list) else "found"
                if isinstance(r, list):
                    out["wit"] = r
                    break
            res[key] = out
            print(key, {k: v for k, v in out.items() if k != "wit"}, round(time.time() - t0, 1), flush=True)
    json.dump(res, open(f"results/theoryA/pairs_{name}_{kind}.json", "w"))


if __name__ == "__main__":
    main()
