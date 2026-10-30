"""E-040 impossibility audit (independent code): BB code check tables built from the polynomials, checked against the
frozen evaluator's HX / HZ (evaluators.tasks.build_code, public entry).  T[kind][c][label] = data qubit, labels
0..5 = A1 A2 A3 B1 B2 B3.  X check c: left qubit c+A_p (label p), right qubit c+B_p (label 3+p);
Z check c: right qubit c-A_p (label p), left qubit c-B_p (label 3+p)."""
from functools import lru_cache

import numpy as np

from evaluators.tasks import build_code, get_task

POLY = {"bb90": (15, 3, [(9, 0), (0, 1), (0, 2)], [(0, 0), (2, 0), (7, 0)], "bb90-dcirc", 10),
        "gross": (12, 6, [(3, 0), (0, 1), (0, 2)], [(0, 3), (1, 0), (2, 0)], "gross-dcirc", 12)}


@lru_cache(None)
def code(name):
    l, m, A, B, task, d = POLY[name]
    c, _ = build_code(get_task(task), None)
    N2 = l * m
    ix = lambda a, b: (a % l) * m + (b % m)
    T = {"X": np.zeros((N2, 6), int), "Z": np.zeros((N2, 6), int)}
    for i in range(N2):
        a, b = divmod(i, m)
        for p in range(3):
            T["X"][i, p] = ix(a + A[p][0], b + A[p][1])
            T["X"][i, 3 + p] = N2 + ix(a + B[p][0], b + B[p][1])
            T["Z"][i, p] = N2 + ix(a - A[p][0], b - A[p][1])
            T["Z"][i, 3 + p] = ix(a - B[p][0], b - B[p][1])
    HX, HZ = np.asarray(c.HX) % 2, np.asarray(c.HZ) % 2
    for k, H in (("X", HX), ("Z", HZ)):
        for i in range(N2):
            assert sorted(T[k][i]) == list(np.flatnonzero(H[i])), (name, k, i)
    return dict(name=name, N2=N2, NQ=2 * N2, T=T, HX=HX.astype(np.uint8), HZ=HZ.astype(np.uint8),
                LX=np.asarray(c.LX, np.uint8) % 2, LZ=np.asarray(c.LZ, np.uint8) % 2, d=d, css=c)


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
