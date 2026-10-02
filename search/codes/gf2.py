"""Small fast GF(2) helpers on python-int bitsets (used in the enumeration inner loop).
For anything that is handed to the evaluator we use evaluators.codes (CSSCode) instead."""
from __future__ import annotations

import numpy as np


def rank_rows(rows: list[int]) -> int:
    """Rank over GF(2) of a list of row bitsets."""
    pivots: dict[int, int] = {}
    r = 0
    for v in rows:
        while v:
            hb = v.bit_length() - 1
            p = pivots.get(hb)
            if p is None:
                pivots[hb] = v
                r += 1
                break
            v ^= p
    return r


def matrix_to_rows(M: np.ndarray) -> list[int]:
    M = np.asarray(M, dtype=np.uint8)
    out = []
    for row in M:
        out.append(int("".join("1" if b else "0" for b in row[::-1]) or "0", 2))
    return out
