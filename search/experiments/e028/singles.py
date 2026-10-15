"""E-028 step 0: single-check extended codes (data columns + the residual columns of ONE check with a given type).
Any extended logical of weight <= 9 < d = 10 must contain a hook column, so only the hook-column orbit cases are run
(orbits: each hook column its own orbit first, data columns after; case c = contains hook c, not hooks < c).
Reproduces E-005 (Prop. 4 single-check bound, MILP): per side 36 types with value 8, 54 with value 9.

    PYTHONPATH=.:tests uv run python -m search.experiments.e028.singles
"""
from __future__ import annotations

import json

import numpy as np

from search.experiments.e028 import common as C


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
            s8, n8, c8 = C.dfs(F, 8, stopfirst=1, workers=4, cases=range(h))
            if s8:
                C.verify_logicals(F, s8[:1]); v = 8
            else:
                assert c8; v = 9
            res[f"{kind}:{C.name(o)}"] = {"value_le": v, "hooks": h, "T": sorted(o[:3])}
            cnt[v] = cnt.get(v, 0) + 1
        print(kind, cnt, flush=True)
    (C.OUT / "singles.json").write_text(json.dumps(res, indent=0))


if __name__ == "__main__":
    main()
