"""E-040: for each pair (and triple) of labels of check 0's support, up to K code logicals of weight d (sector's
(H, L)) containing those data qubits (CP-SAT enumeration, each verified by linear algebra).  Source of the
"pair hook + rest of a weight-d logical" lift candidates (cf. theory A, lemma F / F'); soundness of any witness built
from them is re-checked by bulk.Sector.is_witness, vec.test, CNF semantics and stim injection as for all others.

    PYTHONPATH=.:tests uv run python -m search.experiments.e040.pairlog --code gross --kind X --K 12
"""
from __future__ import annotations

import argparse
import itertools
import json

import numpy as np
from ortools.sat.python import cp_model

from search.experiments.e040.codes import DCODE, MOD, OUT


def logicals_containing(H, L, qs, w, K, sec=120):
    n = H.shape[1]
    m = cp_model.CpModel()
    x = [m.NewBoolVar("") for _ in range(n)]
    for row in H:
        ids = np.flatnonzero(row)
        y = m.NewIntVar(0, len(ids) // 2, "")
        m.Add(sum(x[i] for i in ids) == 2 * y)
    lb = []
    for row in L:
        ids = np.flatnonzero(row)
        y = m.NewIntVar(0, len(ids) // 2 + 1, "")
        b = m.NewBoolVar("")
        m.Add(sum(x[i] for i in ids) == 2 * y + b)
        lb.append(b)
    m.AddBoolOr(lb)
    m.Add(sum(x) == w)
    for q in qs:
        m.Add(x[q] == 1)
    out = []
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = sec
    s.parameters.num_workers = 1
    for _ in range(K):
        st = s.Solve(m)
        if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            break
        v = [i for i in range(n) if s.Value(x[i])]
        e = np.zeros(n, np.uint8); e[v] = 1
        assert not (H @ e % 2).any() and (L @ e % 2).any()
        out.append(v)
        m.AddBoolOr([x[i].Not() for i in v])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--kind", required=True)
    ap.add_argument("--K", type=int, default=12)
    ap.add_argument("--triples", type=int, default=1)
    a = ap.parse_args()
    C = MOD[a.code]
    H, L = C.HLk(a.kind)
    T = C.table()[a.kind]
    d = DCODE[a.code]
    res = {}
    for size in ((2, 3) if a.triples else (2,)):
        for S in itertools.combinations(range(6), size):
            qs = [int(T[0][l]) for l in S]
            res["".join(map(str, S))] = logicals_containing(H, L, qs, d, a.K)
            print(size, S, len(res["".join(map(str, S))]), flush=True)
    json.dump(res, open(OUT / f"pairlog_{a.code}_{a.kind}.json", "w"))


if __name__ == "__main__":
    main()
