"""The gross code [[144,12,12]] (Bravyi et al., arXiv:2308.07915): l = 12, m = 6, A = x^3 + y + y^2, B = y^3 + x + x^2.

Qubit / check index i = 6a + b for the monomial x^a y^b; left block = data qubits 0..71, right block = 72..143.
HX = [A | B], HZ = [B^T | A^T].  The logical operators LX, LZ (12 rows each) are part of the data set
(data/code/gross_code.json): every list of extended-code logicals is expressed with respect to these rows.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np

from .paths import CODE_JSON

L_, M_ = 12, 6


def _mono(p: int, q: int) -> np.ndarray:
    """matrix of the monomial x^p y^q acting on Z_12 x Z_6 (row i = 6a+b has a 1 in column (a+p, b+q))."""
    M = np.zeros((72, 72), np.uint8)
    for a in range(L_):
        for b in range(M_):
            M[a * M_ + b, ((a + p) % L_) * M_ + (b + q) % M_] = 1
    return M


def polynomial_checks() -> tuple[np.ndarray, np.ndarray]:
    A = (_mono(3, 0) + _mono(0, 1) + _mono(0, 2)) % 2
    B = (_mono(0, 3) + _mono(1, 0) + _mono(2, 0)) % 2
    return np.hstack([A, B]), np.hstack([B.T, A.T])


def gf2_rank(M: np.ndarray) -> int:
    M = np.array(M, np.uint8) % 2
    r = 0
    for c in range(M.shape[1]):
        piv = np.nonzero(M[r:, c])[0]
        if len(piv) == 0:
            continue
        p = piv[0] + r
        M[[r, p]] = M[[p, r]]
        for i in np.nonzero(M[:, c])[0]:
            if i != r:
                M[i] ^= M[r]
        r += 1
        if r == M.shape[0]:
            break
    return r


@dataclass(frozen=True)
class Code:
    HX: np.ndarray
    HZ: np.ndarray
    LX: np.ndarray
    LZ: np.ndarray

    @property
    def n(self) -> int:
        return self.HX.shape[1]


def _dense(rows, n=144) -> np.ndarray:
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
        assert not ((c.HX @ c.HZ.T) % 2).any()
        k = 144 - gf2_rank(c.HX) - gf2_rank(c.HZ)
        assert k == 12
        # LZ: Z-type logicals (commute with HX), LX: X-type logicals (commute with HZ); symplectic pairing of rank 12
        assert not ((c.HX @ c.LZ.T) % 2).any() and not ((c.HZ @ c.LX.T) % 2).any()
        assert gf2_rank((c.LX @ c.LZ.T) % 2) == 12
    return c
