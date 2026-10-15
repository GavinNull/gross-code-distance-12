"""The [[90,8,10]] bivariate bicycle code (Bravyi et al., arXiv:2308.07915, Table 3): l = 15, m = 3,
A = x^9 + y + y^2, B = 1 + x^2 + x^7, HX = [A | B], HZ = [B^T | A^T].

Qubit / check index i = 3a + b for the monomial x^a y^b (a in Z_15, b in Z_3); left block = data qubits 0..44,
right block = 45..89.  Term labels A1 = x^9, A2 = y, A3 = y^2, B1 = 1, B2 = x^2, B3 = x^7.  The logical operators
LX, LZ (8 rows each) are part of the data set (data/code/bb90_code.json); every list of extended-code logicals is
expressed with respect to these rows.
"""
from __future__ import annotations

import json

import numpy as np

from gross12.code import Code, gf2_rank
from gross12.paths import DATA

CODE_JSON = DATA / "code" / "bb90_code.json"
L_, M_ = 15, 3
N2 = L_ * M_
N = 2 * N2
A_TERMS = [(9, 0), (0, 1), (0, 2)]
B_TERMS = [(0, 0), (2, 0), (7, 0)]


def _mono(p: int, q: int) -> np.ndarray:
    """matrix of x^p y^q on Z_15 x Z_3 (row i = 3a+b has a 1 in column (a+p, b+q))."""
    M = np.zeros((N2, N2), np.uint8)
    for a in range(L_):
        for b in range(M_):
            M[a * M_ + b, ((a + p) % L_) * M_ + (b + q) % M_] = 1
    return M


def polynomial_checks() -> tuple[np.ndarray, np.ndarray]:
    A = sum(_mono(*t) for t in A_TERMS) % 2
    B = sum(_mono(*t) for t in B_TERMS) % 2
    return np.hstack([A, B]).astype(np.uint8), np.hstack([B.T, A.T]).astype(np.uint8)


def _dense(rows, n=N) -> np.ndarray:
    M = np.zeros((len(rows), n), np.uint8)
    for i, r in enumerate(rows):
        M[i, r] = 1
    return M


def load_code(check: bool = True) -> Code:
    d = json.load(open(CODE_JSON))
    c = Code(*(_dense(d[k]) for k in ("HX", "HZ", "LX", "LZ")))
    if check:
        hx, hz = polynomial_checks()
        assert (hx == c.HX).all() and (hz == c.HZ).all(), "HX/HZ differ from the polynomial definition"
        assert not ((c.HX.astype(int) @ c.HZ.T) % 2).any()
        assert N - gf2_rank(c.HX) - gf2_rank(c.HZ) == 8
        assert not ((c.HX.astype(int) @ c.LZ.T) % 2).any() and not ((c.HZ.astype(int) @ c.LX.T) % 2).any()
        assert gf2_rank((c.LX.astype(int) @ c.LZ.T) % 2) == 8
    return c
