"""Item (2b): Theorem 5 bulk lift (B_audit.lift.solve_bulk, CP-SAT; every solution re-checked by
check_bulk_solution) on the auditor's own lists.  Default: EVERY set of the list (no orbit reduction);
--reps: orbit representatives only.

  uv run python -m search.experiments.e043_audit.lift ibm90 Z 7 --flips 1
"""
from __future__ import annotations

import argparse
import pickle
import time

from search.experiments.e043_audit.common import OUT, jdump


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("basis")
    ap.add_argument("w", type=int)
    ap.add_argument("--flips", type=int, default=0)
    ap.add_argument("--reps", action="store_true")
    a = ap.parse_args()
    from search.experiments.e043_audit.lists import build
    from search.theory.B_audit.lift import check_bulk_solution, solve_bulk
    B, cols, zero, keys, colperm = build(a.name, a.basis)
    d = pickle.load(open(OUT / f"list_{a.name}_{a.basis}_w{a.w}.pkl", "rb"))
    assert set(d["colset"]) == set(keys)
    kidx = {k: i for i, k in enumerate(keys)}
    L = [tuple(sorted(kidx[k] for k in S)) for S in d["keys"]]
    todo = list(range(len(L)))
    if a.reps:
        seen, todo = set(), []
        for i, S in enumerate(L):
            if S in seen:
                continue
            todo.append(i)
            for pm in colperm:
                seen.add(tuple(sorted(pm[j] for j in S)))
    t0 = time.time()
    lifted, maxshift = [], 0
    for i in todo:
        r = solve_bulk(d["keys"][i], cols, a.flips)
        if r is not None:
            sol, nfl = r
            assert check_bulk_solution(sol, nfl, a.flips)
            maxshift = max(maxshift, max(abs(x) for _, x in sol))
            lifted.append(i)
    jdump({"name": a.name, "basis": a.basis, "w": a.w, "flips<=": a.flips, "n_list": len(L), "checked": len(todo),
           "mode": "reps" if a.reps else "all", "zero_key_hooks": len(zero), "lifted": len(lifted),
           "first_lifted": lifted[:10], "max_abs_shift": maxshift, "sec": round(time.time() - t0, 1)}, "lift.jsonl")


if __name__ == "__main__":
    main()
