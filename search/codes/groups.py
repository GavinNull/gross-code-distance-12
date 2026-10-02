"""Finite groups given by multiplication tables, plus abelian-group helpers.

Elements are integers 0..order-1, identity is 0.  For the abelian group Z_l x Z_m the element
(i, j) = x^i y^j has index i*m + j, which matches the Kronecker convention x = S_l (x) I_m,
y = I_l (x) S_m of arXiv:2308.07915 (and baselines/bb_code.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from math import gcd

import numpy as np


@dataclass(eq=False)
class FiniteGroup:
    name: str
    mul: np.ndarray                      # (N, N) int table: mul[g, h] = g*h
    abelian_lm: tuple[int, int] | None = None   # set for Z_l x Z_m
    labels: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.mul = np.asarray(self.mul, dtype=np.int64)
        N = self.order
        assert self.mul.shape == (N, N)
        assert (self.mul[0] == np.arange(N)).all() and (self.mul[:, 0] == np.arange(N)).all(), "0 must be identity"
        self.inv = np.array([int(np.nonzero(self.mul[g] == 0)[0][0]) for g in range(N)], dtype=np.int64)
        if not self.labels:
            self.labels = [f"g{g}" for g in range(N)]

    @property
    def order(self) -> int:
        return self.mul.shape[0]

    @property
    def is_abelian(self) -> bool:
        return bool((self.mul == self.mul.T).all())

    def label(self, g: int) -> str:
        return self.labels[g]


def _mono_label(i: int, j: int) -> str:
    if i == 0 and j == 0:
        return "1"
    s = []
    if i:
        s.append("x" if i == 1 else f"x^{i}")
    if j:
        s.append("y" if j == 1 else f"y^{j}")
    return "".join(s)


@lru_cache(maxsize=None)
def abelian_group(l: int, m: int) -> FiniteGroup:
    """Z_l x Z_m, element x^i y^j -> index i*m + j."""
    I, J = np.divmod(np.arange(l * m), m)
    mul = ((I[:, None] + I[None, :]) % l) * m + (J[:, None] + J[None, :]) % m
    labels = [_mono_label(int(i), int(j)) for i, j in zip(I, J)]
    return FiniteGroup(name=f"Z{l}xZ{m}", mul=mul, abelian_lm=(l, m), labels=labels)


@lru_cache(maxsize=None)
def dihedral_group(r: int) -> FiniteGroup:
    """D_r of order 2r: elements s^e r^i (e in {0,1}) -> index e*r + i; s r s = r^-1.
    Provided as a non-abelian example for the 2BGA interface (no equivalence reduction)."""
    N = 2 * r
    mul = np.zeros((N, N), dtype=np.int64)
    for g in range(N):
        e1, i1 = divmod(g, r)
        for h in range(N):
            e2, i2 = divmod(h, r)
            # (s^e1 r^i1)(s^e2 r^i2) = s^(e1+e2) r^((-1)^e2 i1 + i2)
            i = ((-i1 if e2 else i1) + i2) % r
            mul[g, h] = ((e1 + e2) % 2) * r + i
    labels = []
    for g in range(N):
        e, i = divmod(g, r)
        lab = ("s" if e else "") + ("" if i == 0 else ("r" if i == 1 else f"r^{i}"))
        labels.append(lab or "1")
    return FiniteGroup(name=f"D{r}", mul=mul, labels=labels)


# ------------------------------------------------------------------ abelian structure


def _add(l, m):
    return lambda a, b: ((a[0] + b[0]) % l, (a[1] + b[1]) % m)


def _order(e, l, m):
    i, j = e
    oi = l // gcd(i, l)
    oj = m // gcd(j, m)
    return oi * oj // gcd(oi, oj)


@lru_cache(maxsize=None)
def invariant_factors(l: int, m: int) -> tuple[int, int]:
    """Z_l x Z_m ~= Z_d1 x Z_d2 with d1 | d2 (d1 = gcd, d2 = lcm)."""
    g = gcd(l, m)
    return g, l * m // g


@lru_cache(maxsize=None)
def iso_to_canonical(l: int, m: int) -> np.ndarray:
    """Array phi with phi[index in Z_l x Z_m] = index in Z_d1 x Z_d2 (an explicit isomorphism)."""
    d1, d2 = invariant_factors(l, m)
    elems = [(i, j) for i in range(l) for j in range(m)]
    add = _add(l, m)
    us = [e for e in elems if _order(e, l, m) == d2]
    for u in us:
        cyc = set()
        cur = (0, 0)
        for _ in range(d2):
            cyc.add(cur)
            cur = add(cur, u)
        for v in elems:
            if _order(v, l, m) != d1:
                continue
            # check <u> + <v> is the whole group (sizes multiply => direct)
            span = {}
            ok = True
            cv = (0, 0)
            for a in range(d1):
                cu = cv
                for b in range(d2):
                    if cu in span:
                        ok = False
                        break
                    span[cu] = a * d2 + b
                    cu = add(cu, u)
                if not ok:
                    break
                cv = add(cv, v)
            if ok and len(span) == l * m:
                phi = np.zeros(l * m, dtype=np.int64)
                for (i, j), idx in span.items():
                    phi[i * m + j] = idx
                return phi
    raise RuntimeError("no isomorphism found")  # pragma: no cover


@lru_cache(maxsize=None)
def abelian_automorphisms(d1: int, d2: int) -> np.ndarray:
    """All automorphisms of Z_d1 x Z_d2 as permutation arrays, shape (|Aut|, d1*d2).
    A homomorphism is fixed by the images p of e1=(1,0) (order | d1) and q of e2=(0,1) (order | d2)."""
    N = d1 * d2
    elems = [(i, j) for i in range(d1) for j in range(d2)]
    I = np.array([e[0] for e in elems])
    J = np.array([e[1] for e in elems])
    cand1 = [e for e in elems if (d1 * e[0]) % d1 == 0 and (d1 * e[1]) % d2 == 0]
    cand2 = [e for e in elems if (d2 * e[0]) % d1 == 0 and (d2 * e[1]) % d2 == 0]
    out = []
    for p in cand1:
        for q in cand2:
            img_i = (I * p[0] + J * q[0]) % d1
            img_j = (I * p[1] + J * q[1]) % d2
            perm = img_i * d2 + img_j
            if len(np.unique(perm)) == N:
                out.append(perm)
    return np.array(out, dtype=np.int64)
