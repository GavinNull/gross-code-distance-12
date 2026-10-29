"""Theory A (2026-10-29): independent small helpers for the period lower-bound lemmas.

Codes: BB codes on G = Z_l x Z_m.  Terms A = [a1,a2,a3], B = [b1,b2,b3] (group elements).
X check c: left qubit c+a_k (label A_k), right qubit c+b_l (label B_l).
Z check c: left qubit c-b_l (label B_l), right qubit c-a_k (label A_k).
Qubit index: left g -> idx(g), right g -> N2 + idx(g).  Labels 0..5 = A1 A2 A3 B1 B2 B3.
Written from the definitions only (does not import the E-028/E-032/E-040 modules).
"""
from __future__ import annotations

import numpy as np

CODES = {
    "gross": dict(l=12, m=6, A=[(3, 0), (0, 1), (0, 2)], B=[(0, 3), (1, 0), (2, 0)], d=12),
    "bb90": dict(l=15, m=3, A=[(9, 0), (0, 1), (0, 2)], B=[(0, 0), (2, 0), (7, 0)], d=10),
}


class Code:
    def __init__(self, name):
        p = CODES[name]
        self.name, self.l, self.m, self.d = name, p["l"], p["m"], p["d"]
        self.A, self.B = p["A"], p["B"]
        self.N2 = self.l * self.m
        self.n = 2 * self.N2
        self.G = [(a, b) for a in range(self.l) for b in range(self.m)]
        self.X = np.zeros((self.N2, 6), dtype=np.int64)   # X[c][label] = qubit
        self.Z = np.zeros((self.N2, 6), dtype=np.int64)
        for c, g in enumerate(self.G):
            for k in range(3):
                self.X[c, k] = self.idx(self.add(g, self.A[k]))
                self.X[c, 3 + k] = self.N2 + self.idx(self.add(g, self.B[k]))
                self.Z[c, 3 + k] = self.idx(self.sub(g, self.B[k]))
                self.Z[c, k] = self.N2 + self.idx(self.sub(g, self.A[k]))
        self.HX = np.zeros((self.N2, self.n), dtype=np.uint8)
        self.HZ = np.zeros((self.N2, self.n), dtype=np.uint8)
        for c in range(self.N2):
            self.HX[c, self.X[c]] = 1
            self.HZ[c, self.Z[c]] = 1
        assert not ((self.HX.astype(int) @ self.HZ.T.astype(int)) % 2).any()
        self.k = self.n - rank2(self.HX) - rank2(self.HZ)
        # logical operators: LZ (Z-type, detect X-logicals), LX (X-type, detect Z-logicals)
        self.LZ = logicals(self.HX, self.HZ)   # rows in ker HX, independent mod rowspace HZ
        self.LX = logicals(self.HZ, self.HX)

    def idx(self, g):
        return (g[0] % self.l) * self.m + (g[1] % self.m)

    def add(self, g, h):
        return ((g[0] + h[0]) % self.l, (g[1] + h[1]) % self.m)

    def sub(self, g, h):
        return ((g[0] - h[0]) % self.l, (g[1] - h[1]) % self.m)

    def side(self, kind):
        """kind 'X': X-check hooks, Z-check readers, X-type logicals (Z-basis memory).  returns (Hook table,
        Reader table, H_reader, L) where an X-type error e is a logical iff H e = 0 and L e != 0."""
        if kind == "X":
            return self.X, self.Z, self.HZ, self.LZ
        return self.Z, self.X, self.HX, self.LX


def rank2(M):
    M = (M.copy() % 2).astype(np.uint8)
    r = 0
    rows, cols = M.shape
    for c in range(cols):
        piv = None
        for i in range(r, rows):
            if M[i, c]:
                piv = i
                break
        if piv is None:
            continue
        M[[r, piv]] = M[[piv, r]]
        for i in range(rows):
            if i != r and M[i, c]:
                M[i] ^= M[r]
        r += 1
        if r == rows:
            break
    return r


def nullspace2(M):
    M = (M.copy() % 2).astype(np.uint8)
    rows, cols = M.shape
    pivcols = []
    r = 0
    for c in range(cols):
        piv = None
        for i in range(r, rows):
            if M[i, c]:
                piv = i
                break
        if piv is None:
            continue
        M[[r, piv]] = M[[piv, r]]
        for i in range(rows):
            if i != r and M[i, c]:
                M[i] ^= M[r]
        pivcols.append(c)
        r += 1
        if r == rows:
            break
    free = [c for c in range(cols) if c not in set(pivcols)]
    basis = []
    for f in free:
        v = np.zeros(cols, dtype=np.uint8)
        v[f] = 1
        for i, pc in enumerate(pivcols):
            if M[i, f]:
                v[pc] = 1
        basis.append(v)
    return np.array(basis, dtype=np.uint8)


def logicals(Hperp, Hsame):
    """rows of ker(Hperp) that are independent modulo rowspace(Hsame)."""
    K = nullspace2(Hperp)
    base = Hsame.copy()
    r0 = rank2(base)
    out = []
    for v in K:
        t = np.vstack([base, v[None]])
        r = rank2(t)
        if r > r0:
            base, r0 = t, r
            out.append(v)
    return np.array(out, dtype=np.uint8)
