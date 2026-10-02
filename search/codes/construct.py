"""Code construction: BB codes and two-block group-algebra (2BGA) codes.

Convention (one class covers both families):
  group G (multiplication table), a = a_1 + a_2 + a_3, b = b_1 + b_2 + b_3 in F2[G].
  Term matrices (permutations on G):
     A_t[g, a_t * g] = 1        (left multiplication by a_t)
     B_t[g, g * b_t] = 1        (right multiplication by b_t)
  A = sum A_t, B = sum B_t;  HX = [A | B],  HZ = [B^T | A^T]  (n = 2|G|).
  Left and right multiplications commute, so HX HZ^T = AB + BA = 0 for any group.

* BB code (arXiv:2308.07915 Eq. (1)(2)): G = Z_l x Z_m, terms are monomials x^i y^j.  With
  index(x^i y^j) = i*m + j the matrices are identical to baselines/bb_code.py (x = S_l (x) I_m).
* 2BGA (arXiv:2306.16400): same formula for an arbitrary finite group; for abelian G the left/right
  distinction disappears and a 2BGA code over Z_a x Z_b is exactly a BB code with general monomials.

The object also exposes `n2`, `x_check_neighbor`, `z_check_neighbor` with the semantics of
baselines.bb_code.BBCode, so it can be passed directly to baselines.schedule.bb_term_schedule.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

from search.codes.groups import FiniteGroup, abelian_group
from search.codes.gf2 import rank_rows


@dataclass(eq=False)
class GroupAlgebraCode:
    group: FiniteGroup
    a: tuple[int, ...]          # group elements of the A-polynomial (left multiplication)
    b: tuple[int, ...]          # group elements of the B-polynomial (right multiplication)
    family: str = "2BGA"        # "BB" | "2BGA"
    name: str = ""
    _cache: dict = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self):
        self.a = tuple(int(t) for t in self.a)
        self.b = tuple(int(t) for t in self.b)
        if len(set(self.a)) != len(self.a) or len(set(self.b)) != len(self.b):
            raise ValueError("terms of a (and of b) must be distinct group elements")
        N = self.group.order
        mul = self.group.mul
        # perm arrays: A_perm[t][g] = a_t * g ; B_perm[t][g] = g * b_t
        self.A_perm = [mul[t, :].copy() for t in self.a]
        self.B_perm = [mul[:, t].copy() for t in self.b]
        assert all(len(p) == N for p in self.A_perm + self.B_perm)

    # ------------------------------------------------------------- sizes
    @property
    def n2(self) -> int:
        return self.group.order

    @property
    def n(self) -> int:
        return 2 * self.n2

    @property
    def is_abelian(self) -> bool:
        return self.group.abelian_lm is not None or self.group.is_abelian

    # ------------------------------------------------------------- matrices
    def _perm_matrix(self, perm) -> np.ndarray:
        N = self.n2
        M = np.zeros((N, N), dtype=np.uint8)
        M[np.arange(N), perm] = 1
        return M

    @property
    def A_mats(self) -> list[np.ndarray]:
        return [self._perm_matrix(p) for p in self.A_perm]

    @property
    def B_mats(self) -> list[np.ndarray]:
        return [self._perm_matrix(p) for p in self.B_perm]

    @property
    def A(self) -> np.ndarray:
        return (sum(m.astype(np.int64) for m in self.A_mats) % 2).astype(np.uint8)

    @property
    def B(self) -> np.ndarray:
        return (sum(m.astype(np.int64) for m in self.B_mats) % 2).astype(np.uint8)

    @property
    def HX(self) -> np.ndarray:
        if "HX" not in self._cache:
            self._cache["HX"] = np.hstack([self.A, self.B]).astype(np.uint8)
        return self._cache["HX"]

    @property
    def HZ(self) -> np.ndarray:
        if "HZ" not in self._cache:
            self._cache["HZ"] = np.hstack([self.B.T, self.A.T]).astype(np.uint8)
        return self._cache["HZ"]

    # ------------------------------------------------------------- fast k
    def _rows_bits(self, which: str) -> list[int]:
        """Rows of HX or HZ as python-int bitsets (columns 0..n2-1 = L, n2..n-1 = R)."""
        N = self.n2
        rows = [0] * N
        if which == "X":   # row g: L[a_t g], R[g b_t]
            for p in self.A_perm:
                for g in range(N):
                    rows[g] ^= 1 << int(p[g])
            for p in self.B_perm:
                for g in range(N):
                    rows[g] ^= 1 << (N + int(p[g]))
        else:              # HZ = [B^T | A^T]: row g has L[h] for B_t[h, g]=1, R[h] for A_t[h, g]=1
            for p in self.B_perm:
                for h in range(N):
                    rows[int(p[h])] ^= 1 << h
            for p in self.A_perm:
                for h in range(N):
                    rows[int(p[h])] ^= 1 << (N + h)
        return rows

    @property
    def k(self) -> int:
        if "k" not in self._cache:
            self._cache["k"] = self.n - rank_rows(self._rows_bits("X")) - rank_rows(self._rows_bits("Z"))
        return self._cache["k"]

    # ------------------------------------------------------------- CSSCode
    def to_css(self):
        """evaluators.codes.CSSCode (validated: commuting checks, paired logicals)."""
        from evaluators.codes import CSSCode
        if "css" not in self._cache:
            self._cache["css"] = CSSCode.from_checks(self.HX, self.HZ, name=self.name or self.label())
        return self._cache["css"]

    # ------------------------------------------------------------- schedule adapter (BBCode API)
    def x_check_neighbor(self, t: int, i: int) -> tuple[str, int]:
        """Data qubit touched by X-check i via term t in [A1,A2,A3,B1,B2,B3] order."""
        if t < 3:
            return "L", int(self.A_perm[t][i])
        return "R", int(self.B_perm[t - 3][i])

    def z_check_neighbor(self, t: int, i: int) -> tuple[str, int]:
        """Z-check i via term t: A_t -> R[A_t^T(i)], B_t -> L[B_t^T(i)] (j with M[j, i] = 1)."""
        if t < 3:
            return "R", int(self._inv_perm("A", t)[i])
        return "L", int(self._inv_perm("B", t - 3)[i])

    def _inv_perm(self, which, t):
        key = f"inv{which}{t}"
        if key not in self._cache:
            p = (self.A_perm if which == "A" else self.B_perm)[t]
            inv = np.empty_like(p)
            inv[p] = np.arange(len(p))
            self._cache[key] = inv
        return self._cache[key]

    # ------------------------------------------------------------- printing
    def poly(self, which: str) -> str:
        terms = self.a if which == "A" else self.b
        return " + ".join(self.group.label(t) for t in terms)

    def label(self) -> str:
        return f"{self.family}[{self.group.name}] A={self.poly('A')} B={self.poly('B')}"

    def to_dict(self) -> dict:
        d = {"family": self.family, "group": self.group.name, "n": self.n,
             "A": self.poly("A"), "B": self.poly("B"), "a_idx": list(self.a), "b_idx": list(self.b)}
        if self.group.abelian_lm:
            d["l"], d["m"] = self.group.abelian_lm
        return d


# ------------------------------------------------------------------ constructors

_TERM = re.compile(r"^(?:1|(?:x(?:\^(\d+))?)?(?:y(?:\^(\d+))?)?)$")


def parse_monomial(s: str) -> tuple[int, int]:
    """'x^3' -> (3,0); 'y' -> (0,1); '1' -> (0,0); 'x^2y^5' or 'x^2*y^5' -> (2,5)."""
    t = s.replace(" ", "").replace("*", "")
    if t == "1":
        return 0, 0
    m = re.fullmatch(r"(x(?:\^(\d+))?)?(y(?:\^(\d+))?)?", t)
    if not m or not (m.group(1) or m.group(3)):
        raise ValueError(f"bad monomial {s!r}")
    i = (int(m.group(2) or 1)) if m.group(1) else 0
    j = (int(m.group(4) or 1)) if m.group(3) else 0
    return i, j


def parse_poly(s) -> list[tuple[int, int]]:
    if isinstance(s, str):
        s = s.split("+")
    return [parse_monomial(t) for t in s]


def bb_code(l: int, m: int, A, B, name: str = "") -> GroupAlgebraCode:
    """BB code QC(A, B) on Z_l x Z_m.  A, B: '1+x^2+x^7' or ['x^9','y','y^2'] or [(i,j), ...]."""
    G = abelian_group(l, m)

    def idx(terms):
        if isinstance(terms, str) or (len(terms) and isinstance(terms[0], str)):
            terms = parse_poly(terms)
        return tuple((i % l) * m + (j % m) for i, j in terms)

    return GroupAlgebraCode(G, idx(A), idx(B), family="BB", name=name)


def coprime_bb_code(l: int, m: int, a_pi_exps, b_pi_exps, name: str = "") -> GroupAlgebraCode:
    """Wang–Mueller coprime BB (arXiv:2408.10001): polynomials in pi = xy, gcd(l, m) = 1."""
    A = [(e % l, e % m) for e in a_pi_exps]
    B = [(e % l, e % m) for e in b_pi_exps]
    return bb_code(l, m, A, B, name=name)


def two_bga_code(group: FiniteGroup, a, b, name: str = "") -> GroupAlgebraCode:
    """2BGA code (arXiv:2306.16400) for a group given by its multiplication table.
    a, b: lists of group element indices (weight-6 case: 3 + 3)."""
    fam = "BB" if group.abelian_lm else "2BGA"
    return GroupAlgebraCode(group, tuple(a), tuple(b), family=fam, name=name)


def from_dict(d: dict) -> GroupAlgebraCode:
    if "l" in d:
        return bb_code(d["l"], d["m"], [_split(d["l"], d["m"], g) for g in d["a_idx"]],
                       [_split(d["l"], d["m"], g) for g in d["b_idx"]])
    raise NotImplementedError("non-abelian from_dict: rebuild the group and call two_bga_code")


def _split(l, m, g):
    return divmod(int(g), m)


def to_baseline_bbcode(code: GroupAlgebraCode):
    """baselines.bb_code.BBCode when every term is a pure power of x or of y (IBM form); else None."""
    from baselines.bb_code import BBCode
    if not code.group.abelian_lm:
        return None
    l, m = code.group.abelian_lm

    def term(g):
        i, j = divmod(g, m)
        if i and j:
            return None
        return f"x^{i}" if i else f"y^{j}"   # identity -> 'y^0'

    A = [term(g) for g in code.a]
    B = [term(g) for g in code.b]
    if None in A or None in B:
        return None
    return BBCode(l, m, A, B)
