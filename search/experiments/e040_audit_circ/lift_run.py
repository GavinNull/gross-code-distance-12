"""Item (3a): Theorem 5 bulk lift check with the theory-B auditor's CP-SAT solver (B_audit.lift.solve_bulk, every
solution re-verified by check_bulk_solution), on the auditor's own lists (lists.py).

Translation reduction: the schedule is strictly translation invariant (legal.py: same absolute times for
translated checks), so the bulk realisations of a translated column set are the translated realisations with the
same base values, and liftability is constant on translation orbits.  Default = one representative per orbit;
--all does every set (used as a cross-check of the reduction).

  uv run python -m search.experiments.e040_audit_circ.lift_run g10 Z 10 --flips 1 [--all] [--spec other.json]
"""
from __future__ import annotations

import argparse
import pickle
import time

from search.experiments.e040_audit_circ.common import OUT, gross, jdump, load


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("basis")
    ap.add_argument("w", type=int)
    ap.add_argument("--flips", type=int, default=0)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--spec", default="", help="lift on another schedule with the same extended code (control)")
    ap.add_argument("--part", default="0/1")
    a = ap.parse_args()
    from search.experiments.e040_audit_circ.lists import build
    from search.theory.B_audit.common import Bulk
    from search.theory.B_audit.lift import bulk_columns, check_bulk_solution, solve_bulk
    B, cols, zero, keys, colperm = build(a.name, a.basis)
    target = a.spec or a.name
    if a.spec:
        B2 = Bulk(load(a.spec), gross(), a.basis)
        cols, zero = bulk_columns(B2)
        assert set(cols) == set(keys), "control schedule has a different extended code"
    d = pickle.load(open(OUT / f"list_{a.name}_{a.basis}_w{a.w}.pkl", "rb"))
    assert set(d["colset"]) == set(keys)
    kidx = {k: i for i, k in enumerate(keys)}
    L = [tuple(sorted(kidx[k] for k in S)) for S in d["keys"]]
    if a.all:
        todo = list(range(len(L)))
    else:
        seen, todo = set(), []
        for i, S in enumerate(L):
            if S in seen:
                continue
            todo.append(i)
            for pm in colperm:
                seen.add(tuple(sorted(pm[j] for j in S)))
        assert len(seen) == len(L), (len(seen), len(L))
    pi, pn = map(int, a.part.split("/"))
    todo = todo[pi::pn]
    t0 = time.time()
    lifted, maxshift = [], 0
    for i in todo:
        S = d["keys"][i]
        r = solve_bulk(S, cols, a.flips)
        if r is not None:
            sol, nfl = r
            assert check_bulk_solution(sol, nfl, a.flips)
            maxshift = max(maxshift, max(abs(x) for _, x in sol))
            lifted.append(i)
    rec = {"list_of": a.name, "schedule": target, "basis": a.basis, "w": a.w, "flips<=": a.flips,
           "n_list": len(L), "checked": len(todo), "mode": "all" if a.all else "orbit_reps", "part": a.part,
           "zero_key_hooks": len(zero), "lifted": len(lifted), "first_lifted": lifted[:10],
           "max_abs_shift": maxshift, "sec": round(time.time() - t0, 1)}
    jdump(rec, "lift.jsonl")


if __name__ == "__main__":
    main()
