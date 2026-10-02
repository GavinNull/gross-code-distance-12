"""Bivariate bicycle (BB) codes, Bravyi et al., arXiv:2308.07915.

Conventions (follow the paper, Sec. 4-5):
  x = S_l (x) I_m,  y = I_l (x) S_m,  S_k = cyclic shift (k x k)
  A = A1 + A2 + A3,  B = B1 + B2 + B3   (each term a monomial -> permutation matrix)
  HX = [A | B],  HZ = [B^T | A^T]
  Data qubits split into left block L (columns 0..n/2-1) and right block R.
  X-check i acts on L[A_p(i)] and R[B_p(i)], Z-check i acts on L[B_p^T(i)] and R[A_p^T(i)],
  where j = M(i) means M[i, j] = 1.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np


# ---------------------------------------------------------------- GF(2) utilities

def gf2_rref(M: np.ndarray) -> tuple[np.ndarray, list[int]]:
    """Row-reduce a binary matrix. Returns (rref, pivot_columns)."""
    M = (np.array(M, dtype=np.uint8) % 2).copy()
    rows, cols = M.shape
    pivots: list[int] = []
    r = 0
    for c in range(cols):
        if r >= rows:
            break
        nz = np.nonzero(M[r:, c])[0]
        if len(nz) == 0:
            continue
        p = r + nz[0]
        if p != r:
            M[[r, p]] = M[[p, r]]
        others = np.nonzero(M[:, c])[0]
        others = others[others != r]
        if len(others):
            M[others] ^= M[r]
        pivots.append(c)
        r += 1
    return M[:r], pivots


def gf2_rank(M: np.ndarray) -> int:
    return len(gf2_rref(M)[1])


def gf2_nullspace(M: np.ndarray) -> np.ndarray:
    """Basis of {v : M v = 0} as rows."""
    M = np.array(M, dtype=np.uint8) % 2
    n = M.shape[1]
    R, piv = gf2_rref(M)
    free = [c for c in range(n) if c not in set(piv)]
    basis = np.zeros((len(free), n), dtype=np.uint8)
    for t, f in enumerate(free):
        basis[t, f] = 1
        for i, pc in enumerate(piv):
            if R[i, f]:
                basis[t, pc] = 1
    return basis


def logical_operators(H_same: np.ndarray, H_other: np.ndarray) -> np.ndarray:
    """Independent logicals of one type.

    For logical Z ops pass (H_same=HZ, H_other=HX): vectors in ker(HX) not in rowspace(HZ),
    reduced to k representatives independent modulo rowspace(HZ).
    """
    ker = gf2_nullspace(H_other)
    base_rank = gf2_rank(H_same)
    chosen: list[np.ndarray] = []
    cur = np.array(H_same, dtype=np.uint8)
    for v in ker:
        trial = np.vstack([cur, v[None, :]])
        if gf2_rank(trial) > base_rank + len(chosen):
            chosen.append(v)
            cur = trial
    return np.array(chosen, dtype=np.uint8)


# ---------------------------------------------------------------- BB code

_MONO = re.compile(r"^\s*([xy])(?:\^(\d+))?\s*$")


def _parse_monomial(s: str) -> tuple[str, int]:
    m = _MONO.match(s)
    if not m:
        raise ValueError(f"bad monomial {s!r}; expected like 'x^3', 'y', 'y^2'")
    return m.group(1), int(m.group(2) or 1)


@dataclass
class BBCode:
    l: int
    m: int
    A_terms: list[str]
    B_terms: list[str]
    A_mats: list[np.ndarray] = field(init=False, repr=False)
    B_mats: list[np.ndarray] = field(init=False, repr=False)

    def __post_init__(self):
        Sl = np.roll(np.eye(self.l, dtype=np.uint8), 1, axis=1)
        Sm = np.roll(np.eye(self.m, dtype=np.uint8), 1, axis=1)
        x = np.kron(Sl, np.eye(self.m, dtype=np.uint8))
        y = np.kron(np.eye(self.l, dtype=np.uint8), Sm)

        def mono(s):
            var, pw = _parse_monomial(s)
            base = x if var == "x" else y
            return np.linalg.matrix_power(base.astype(np.int64), pw).astype(np.uint8) % 2

        self.A_mats = [mono(t) for t in self.A_terms]
        self.B_mats = [mono(t) for t in self.B_terms]

    # ---- sizes
    @property
    def n2(self) -> int:
        return self.l * self.m

    @property
    def n(self) -> int:
        return 2 * self.n2

    @property
    def A(self) -> np.ndarray:
        return sum(self.A_mats) % 2

    @property
    def B(self) -> np.ndarray:
        return sum(self.B_mats) % 2

    @property
    def HX(self) -> np.ndarray:
        return np.hstack([self.A, self.B]).astype(np.uint8)

    @property
    def HZ(self) -> np.ndarray:
        return np.hstack([self.B.T, self.A.T]).astype(np.uint8)

    @property
    def k(self) -> int:
        return self.n - gf2_rank(self.HX) - gf2_rank(self.HZ)

    def logical_z(self) -> np.ndarray:
        return logical_operators(self.HZ, self.HX)

    def logical_x(self) -> np.ndarray:
        return logical_operators(self.HX, self.HZ)

    # ---- neighbour maps: term index t in 0..5 = [A1,A2,A3,B1,B2,B3]
    def x_check_neighbor(self, t: int, i: int) -> tuple[str, int]:
        """Data qubit touched by X-check i via term t ('L'|'R', index)."""
        if t < 3:
            return "L", int(np.nonzero(self.A_mats[t][i, :])[0][0])
        return "R", int(np.nonzero(self.B_mats[t - 3][i, :])[0][0])

    def z_check_neighbor(self, t: int, i: int) -> tuple[str, int]:
        """Data qubit touched by Z-check i via term t: A_t -> R[A_t^T(i)], B_t -> L[B_t^T(i)]."""
        if t < 3:
            return "R", int(np.nonzero(self.A_mats[t][:, i])[0][0])
        return "L", int(np.nonzero(self.B_mats[t - 3][:, i])[0][0])


def gross_code() -> BBCode:
    """[[144,12,12]]: l=12, m=6, A = x^3 + y + y^2, B = y^3 + x + x^2."""
    return BBCode(12, 6, ["x^3", "y", "y^2"], ["y^3", "x", "x^2"])


# ---------------------------------------------------------------- distance upper bound

def distance_upper_bound_bposd(code: BBCode, trials: int, seed: int,
                               osd_order: int = 7, max_iter: int = 1000) -> tuple[int, list[int]]:
    """Paper Sec. 6 method (Eq. 11): d(eta) = min |xi| s.t. HX xi = 0, eta^T xi = 1,
    eta a random logical X operator (random element of ker(HZ) outside rs(HX)).
    Solved heuristically by BP-OSD -> each value is an upper bound on d_Z (= d by Lemma 1).
    Returns (min found, list of all values)."""
    from ldpc import BpOsdDecoder

    rng = np.random.default_rng(seed)
    HX, HZ = code.HX, code.HZ
    LX = code.logical_x()
    vals: list[int] = []
    for _ in range(trials):
        # random combination of logical X ops (non-zero) plus random X stabilizers
        c = rng.integers(0, 2, size=LX.shape[0])
        if not c.any():
            c[rng.integers(LX.shape[0])] = 1
        s = rng.integers(0, 2, size=HX.shape[0])
        eta = (c @ LX + s @ HX) % 2
        H = np.vstack([HX, eta[None, :]]).astype(np.uint8)
        syn = np.zeros(H.shape[0], dtype=np.uint8)
        syn[-1] = 1
        dec = BpOsdDecoder(H, error_rate=0.05, max_iter=max_iter, bp_method="minimum_sum",
                           osd_method="osd_cs", osd_order=osd_order)
        xi = dec.decode(syn)
        assert ((H @ xi) % 2 == syn).all()
        vals.append(int(xi.sum()))
    return min(vals), vals
