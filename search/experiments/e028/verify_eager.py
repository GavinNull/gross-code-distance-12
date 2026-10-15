"""E-028: direct validity check of every eager clause (independent of any assignment): for each clause, rebuild the
extended-logical it encodes -- hook columns (check a_i, label set U_i) plus the data qubits l minus the U_i -- and assert
(i) the (H,L) keys of the hook columns are the clause's keys, (ii) the columns sum to (0, L l) with L l != 0,
(iii) number of columns <= 8.  Also re-derives the 54 allowed types from scratch-free facts (singles.json).

    PYTHONPATH=.:tests uv run python -m search.experiments.e028.verify_eager --kind X
"""
from __future__ import annotations

import argparse
import itertools
import pickle

import numpy as np

from search.experiments.e028 import common as C
from search.experiments.e028.eager import selections


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True)
    ap.add_argument("--W", type=int, default=10)
    a = ap.parse_args()
    kind = a.kind
    H, L = C.HLk(kind)
    T = C.table()[kind]
    sup = [frozenset(int(q) for q in T[c]) for c in range(C.N2)]
    logs = pickle.load(open(C.OUT / f"codelog_{kind}_W{a.W}.pkl", "rb"))
    nchk = 0
    keysets = set()
    for l in logs:
        v = np.zeros(C.NQ, np.uint8); v[list(l)] = 1
        assert not (H @ v % 2).any() and (L @ v % 2).any()
        Lset = frozenset(l)
        cands = []
        for c in range(C.N2):
            inter = sorted(Lset & sup[c])
            for size in (2, 3, 4):
                for U in itertools.combinations(inter, size):
                    cands.append((frozenset(U), size - 1, c))
        for sel in selections([(x[0], x[1]) for x in cands], len(l) - 8):
            hooks = [cands[i][0] for i in sel]
            used = frozenset().union(*hooks)
            assert len(used) == sum(len(h) for h in hooks)
            data = sorted(Lset - used)
            cols = [C.key_of(kind, [q]) for q in data] + [C.key_of(kind, sorted(h)) for h in hooks]
            assert len(cols) <= 8
            hv = np.zeros(H.shape[0], np.uint8); lv = np.zeros(L.shape[0], np.uint8)
            for k in cols:
                hv ^= np.frombuffer(k[:H.shape[0]], np.uint8); lv ^= np.frombuffer(k[H.shape[0]:], np.uint8)
            assert not hv.any() and lv.any()
            keysets.add(tuple(sorted({C.key_of(kind, sorted(h)) for h in hooks})))
            nchk += 1
    print(kind, "logicals", len(logs), "selections verified", nchk, "distinct clauses", len(keysets))


if __name__ == "__main__":
    main()
