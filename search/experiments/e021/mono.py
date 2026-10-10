"""E-021: monomial labels of the gross code's check supports and Fig. 12 orders in monomial language.

X check i (row of HX = [A | B]) touches L[A_p(i)] (labels A1..A3 = p 0..2) and R[B_p(i)] (labels B1..B3 = 3..5).
Z check i (row of HZ = [B^T | A^T]) touches L[B_p^T(i)] (labels 3..5 -> "B") and R[A_p^T(i)] (labels 0..2 -> "A").
Label k of check i -> data column `col(kind, i, k)`.  Translations (a,b) act on rows/cols as in e018.common.tr.

    PYTHONPATH=. uv run python -m search.experiments.e021.mono
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from baselines.bb_code import gross_code
from search.experiments.e018 import common as C

N2 = 72
LAB = ["A1", "A2", "A3", "B1", "B2", "B3"]


@lru_cache(maxsize=None)
def table():
    """T[kind][i][k] = data column of label k in check i (kind 'X' = X checks / rows of HX, 'Z' = rows of HZ)."""
    g = gross_code()
    T = {"X": np.zeros((N2, 6), int), "Z": np.zeros((N2, 6), int)}
    for i in range(N2):
        for p in range(3):
            T["X"][i, p] = int(np.nonzero(g.A_mats[p][i])[0][0])
            T["X"][i, 3 + p] = N2 + int(np.nonzero(g.B_mats[p][i])[0][0])
            T["Z"][i, 3 + p] = int(np.nonzero(g.B_mats[p].T[i])[0][0])
            T["Z"][i, p] = N2 + int(np.nonzero(g.A_mats[p].T[i])[0][0])
    HX, HZ = np.asarray(g.HX) % 2, np.asarray(g.HZ) % 2
    for kind, H in (("X", HX), ("Z", HZ)):
        for i in range(N2):
            assert sorted(T[kind][i]) == sorted(np.nonzero(H[i])[0].tolist())
    return T


def orders_from_labels(kind, lab_orders):
    """lab_orders: list (len 72) of label permutations -> data-column orders."""
    T = table()[kind]
    return [[int(T[i][k]) for k in lab_orders[i]] for i in range(N2)]


def fig12_labels():
    """Fig. 12 per-check orders as label sequences, plus the colour (0,1,2) class of each row (by label pattern)."""
    xo, zo = C.orders()
    T = table()
    out = {}
    for kind, o in (("X", xo), ("Z", zo)):
        inv = [{int(T[kind][i][k]): k for k in range(6)} for i in range(N2)]
        out[kind] = [tuple(inv[i][q] for q in o[i]) for i in range(N2)]
    return out


def colour_of_rows():
    """Colour class of each check row = index of its Fig. 12 X-label pattern among distinct patterns."""
    f = fig12_labels()
    pats = sorted(set(f["X"]))
    return [pats.index(p) for p in f["X"]], pats


if __name__ == "__main__":
    f = fig12_labels()
    for kind in "XZ":
        pats = {}
        for i, p in enumerate(f[kind]):
            pats.setdefault(p, []).append(i)
        print(kind, len(pats), "distinct label orders")
        for p, rows in pats.items():
            print("  ", [LAB[k] for k in p], len(rows), "rows; first", rows[:6], "(a,b)=", [divmod(r, 6) for r in rows[:4]])
