"""E-032 step 0 (port of e028/singles.py to gross): single-check extended codes (data columns + the residual columns
of ONE check with a given type).  Any extended logical of weight <= 11 < d = 12 must contain a hook column, so only
the hook-column orbit cases are run (orbits: each hook column its own orbit first, data columns after).
value_le = 9 (weight <= 9 found), 10 (none <= 9, one of weight 10), 11 (none <= 10).  E-021 pairs.py predicts:
value 11 exactly for the 45 types whose prefix triple is in one of the 5 allowed triple classes (per side).

    PYTHONPATH=.:tests uv run python -m search.experiments.e032.singles
"""
from __future__ import annotations

import json

import numpy as np

from search.experiments.e032 import common as C


def single_ext(kind, o):
    lab = [o] + [tuple(range(6))] * (C.N2 - 1)   # other checks: identity order (its residual cols are dropped below)
    E = C.ext_general(kind, lab, group=[(0, 0)])
    # keep data columns + residual columns of check 0 only
    T = C.table()[kind]
    q0 = [int(T[0][k]) for k in o]
    mine = {tuple(sorted(s)) for s in C.residuals(q0)}
    keep = [j for j in range(E["N"]) if any(len(s) == 1 for s in E["col_sups"][j]) or
            any(tuple(sorted(s)) in mine for s in E["col_sups"][j])]
    hooks = [j for j in keep if not any(len(s) == 1 for s in E["col_sups"][j])]
    data = [j for j in keep if j not in hooks]
    cols = hooks + data
    F = {"He": E["He"][:, cols], "Le": E["Le"][:, cols], "col_sups": [E["col_sups"][j] for j in cols],
         "N": len(cols), "perms": np.array([np.arange(len(cols))])}
    F["orbit"] = np.arange(len(cols)); F["reps"] = list(range(len(cols)))
    return F, len(hooks)


def main():
    res = {}
    for kind in "XZ":
        cnt = {}
        for o in C.all_types():
            F, h = single_ext(kind, o)
            v = None
            for W in (9, 10):
                s8, n8, c8 = C.dfs(F, W, stopfirst=1, workers=2, cases=range(h))
                if s8:
                    C.verify_logicals(F, s8[:1]); v = W; break
                assert c8
            v = v or 11
            res[f"{kind}:{C.name(o)}"] = {"value_le": v, "hooks": h, "T": sorted(o[:3])}
            cnt[v] = cnt.get(v, 0) + 1
        print(kind, cnt, flush=True)
    (C.OUT / "singles.json").write_text(json.dumps(res, indent=0))


if __name__ == "__main__":
    main()
