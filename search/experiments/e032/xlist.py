"""E-032: independent cross-check of d_ext = 10 and of the complete weight-10 / weight-11 lists of a circuit's class,
with the E-029 branch-and-bound (ccsearch, own implementation, different pruning) on the extended code built by
e029/export.py `ext` (from the circuit's own CNOT orders).  Reads ccsearch `enum 11` output, maps solution columns to
(H, L) keys, expands every solution by the 72 translations of the data torus, and compares the sets with the DFS
lists (wlist.py pickles).

    PYTHONPATH=.:tests uv run python -m search.experiments.e032.xlist INST.txt RUN.out KIND ORDERS
"""
from __future__ import annotations

import json
import pickle
import sys

import numpy as np

from search.experiments.e032 import common as C


def main():
    inst, run, kind, orders = sys.argv[1:5]
    meta = json.load(open(inst + ".meta.json"))
    H, L = C.HLk(kind)
    cols = meta["columns"]

    def key(sup):
        v = np.zeros(C.NQ, np.uint8); v[list(sup)] = 1
        return ((H @ v) % 2).astype(np.uint8).tobytes() + ((L @ v) % 2).astype(np.uint8).tobytes()

    ck = [key(c["support"]) for c in cols]
    for c, k in zip(cols, ck):    # meta's H/L lists agree with our matrices
        assert sorted(np.nonzero(np.frombuffer(k[:H.shape[0]], np.uint8))[0].tolist()) == c["H"]

    def tq(q, a, b):
        blk, i = divmod(q, C.N2); x, y = divmod(i, C.M_)
        return blk * C.N2 + ((x + a) % C.L_) * C.M_ + (y + b) % C.M_

    sols = {10: set(), 11: set()}
    nlines = 0
    for line in open(run):
        if not line.startswith("SOL"):
            continue
        nlines += 1
        ids = [int(x) for x in line.split(":")[1].split()]
        w = len(ids)
        assert w in sols, w
        for a in range(C.L_):
            for b in range(C.M_):
                ks = frozenset(key([tq(q, a, b) for q in cols[j]["support"]]) for j in ids)
                assert len(ks) == w
                sols[w].add(ks)
    res = {"sol_lines": nlines, "cc10": len(sols[10]), "cc11": len(sols[11])}
    for w in (10, 11):
        d = pickle.load(open(C.OUT / f"w{w}_{kind}_all_{orders}.pkl", "rb"))
        mine = {frozenset(S) for S in d["keys"]}
        assert set(d["colset"]) == set(ck), "column sets differ"
        res[f"dfs{w}"] = len(mine)
        res[f"only_cc{w}"] = len(sols[w] - mine)
        res[f"only_dfs{w}"] = len(mine - sols[w])
    print(json.dumps(res))


if __name__ == "__main__":
    main()
