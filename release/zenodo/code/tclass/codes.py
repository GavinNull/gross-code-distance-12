"""The two BB codes for the class-T(P) computations: check tables built from the polynomials and checked against HX /
HZ of data/code/{gross,bb90}_code.json.  T[kind][c][label] = data qubit, labels 0..5 = A1 A2 A3 B1 B2 B3.
X check c: left qubit c+A_p (label p), right qubit c+B_p (label 3+p); Z check c: right qubit c-A_p (label p), left
qubit c-B_p (label 3+p).

code(name) -> dict(N2, NQ, T, HX, HZ, LX, LZ, d)        (used by bulk.py, cover.py)
table_module(name) -> object with N2, NQ, table()        (the interface used by the CNF encoder cnf.py)
"""
import json
from functools import lru_cache
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parents[2] / "data" / "code"
POLY = {"bb90": (15, 3, [(9, 0), (0, 1), (0, 2)], [(0, 0), (2, 0), (7, 0)], "bb90_code.json", 10),
        "gross": (12, 6, [(3, 0), (0, 1), (0, 2)], [(0, 3), (1, 0), (2, 0)], "gross_code.json", 12)}


def _mat(rows, n):
    M = np.zeros((len(rows), n), np.uint8)
    for i, r in enumerate(rows):
        M[i, r] = 1
    return M


@lru_cache(None)
def code(name):
    l, m, A, B, fname, d = POLY[name]
    js = json.load(open(DATA / fname))
    N2 = l * m
    n = 2 * N2
    ix = lambda a, b: (a % l) * m + (b % m)    # noqa: E731
    T = {"X": np.zeros((N2, 6), int), "Z": np.zeros((N2, 6), int)}
    for i in range(N2):
        a, b = divmod(i, m)
        for p in range(3):
            T["X"][i, p] = ix(a + A[p][0], b + A[p][1])
            T["X"][i, 3 + p] = N2 + ix(a + B[p][0], b + B[p][1])
            T["Z"][i, p] = N2 + ix(a - A[p][0], b - A[p][1])
            T["Z"][i, 3 + p] = ix(a - B[p][0], b - B[p][1])
    HX, HZ = _mat(js["HX"], n), _mat(js["HZ"], n)
    for k, H in (("X", HX), ("Z", HZ)):
        for i in range(N2):
            assert sorted(T[k][i]) == list(np.flatnonzero(H[i])), (name, k, i)
    return dict(name=name, N2=N2, NQ=n, T=T, HX=HX, HZ=HZ, LX=_mat(js["LX"], n), LZ=_mat(js["LZ"], n), d=d)


class _Tab:
    def __init__(self, name):
        C = code(name)
        self.N2, self.NQ, self._T = C["N2"], C["NQ"], C["T"]

    def table(self):
        return self._T


def table_module(name):
    return _Tab(name)


def gf2_rank(M):
    M = (np.array(M, np.uint8) % 2).copy()
    r = 0
    rows, cols = M.shape
    for j in range(cols):
        piv = np.flatnonzero(M[r:, j])
        if len(piv) == 0:
            continue
        p = r + piv[0]
        M[[r, p]] = M[[p, r]]
        nz = np.flatnonzero(M[:, j])
        nz = nz[nz != r]
        M[nz] ^= M[r]
        r += 1
        if r == rows:
            break
    return r


def is_nontrivial_logical(C, kind, e):
    """kind X: e is an X error; undetectable iff HZ e = 0; nontrivial iff e not in rowspace(HX)."""
    H, S = (C["HZ"], C["HX"]) if kind == "X" else (C["HX"], C["HZ"])
    if (H @ e % 2).any():
        return False
    return gf2_rank(np.vstack([S, e[None]])) > gf2_rank(S)
