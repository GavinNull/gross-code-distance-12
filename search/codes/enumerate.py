"""Enumerators of weight-6 BB code candidates (as (l, m, a_idx, b_idx) tuples, cheap to pickle).

Families
--------
"ibm"      : A = x^a + y^b + y^c,  B = y^d + x^e + x^f   (the form of all codes in arXiv:2308.07915
             Table 3; "1" = x^0 = y^0 is allowed, e.g. B = 1 + x^2 + x^7).  Enumerated for l >= m only:
             the family on (m, l) maps onto the family on (l, m) by x <-> y followed by A <-> B.
"general"  : A, B arbitrary 3-term subsets of Z_l x Z_m (2BGA / general BB).  Using translations (E1)
             we fix 1 in both A and B, so A = 1 + g + g', B = 1 + h + h'.
In both cases the caller should de-duplicate with search.codes.equivalence.canonical_key_abelian.
"""
from __future__ import annotations

import itertools


def bb_shapes(n_max: int, min_side: int = 2, l_ge_m: bool = True):
    """(l, m) with l*m*2 <= n_max, l, m >= min_side."""
    out = []
    for l in range(min_side, n_max // 2 + 1):
        for m in range(min_side, n_max // 2 + 1):
            if 2 * l * m <= n_max and (not l_ge_m or l >= m):
                out.append((l, m))
    return out


def ibm_family(l: int, m: int):
    """Yield (a_idx, b_idx) for A = x^a + y^b + y^c, B = y^d + x^e + x^f (b<c, e<f)."""
    for a in range(l):
        for b, c in itertools.combinations(range(m), 2):
            A = (a * m, b, c)
            if len(set(A)) < 3:
                continue
            for d in range(m):
                for e, f in itertools.combinations(range(l), 2):
                    B = (d, e * m, f * m)
                    if len(set(B)) < 3:
                        continue
                    yield A, B


def general_family(l: int, m: int):
    """Yield (a_idx, b_idx) with 0 in both (translation-normalised)."""
    N = l * m
    pairs = list(itertools.combinations(range(1, N), 2))
    for p, q in pairs:
        for r, s in pairs:
            yield (0, p, q), (0, r, s)


def family_size(family: str, l: int, m: int) -> int:
    from math import comb
    if family == "ibm":
        # A: a in [0,l), {b<c}; distinctness fails only if a=0 and 0 in {b,c}: then x^0 = y^0
        nA = l * comb(m, 2) - (m - 1)
        nB = m * comb(l, 2) - (l - 1)
        return nA * nB
    return comb(l * m - 1, 2) ** 2
