"""E-020: cross-check of cegar.bellman_ford (my model encoding on option schedules) against E-018's
frame_model.feasible_general (evaluator ScheduleSpec route), on given option schedules.

    PYTHONPATH=.:tests uv run python -m search.experiments.e020.xcheck results/.../plegal_P9.json [n]
"""
from __future__ import annotations

import json
import sys

from evaluators.candidate import CheckTiming, ScheduleSpec
from search.experiments.e018.common import orders
from search.experiments.e018.frame_model import abs_tables, feasible_general
from search.experiments.e018.lift import KIND_OF_BASIS
from search.experiments.e020.cegar import bellman_ford, prep_logicals


def spec_of_options(opts, P):
    """opts: list of 144 option tuples (X checks then Z checks, plegal order)."""
    xo, zo = orders()

    def mk(o, order):
        return CheckTiming((o[0] - 1) % P, (o[5] + 1) % P, tuple(sorted((int(q), t % P) for q, t in zip(order, o))))
    return ScheduleSpec(P, tuple(mk(opts[i], xo[i]) for i in range(72)),
                        tuple(mk(opts[72 + j], zo[j]) for j in range(72)))


def times(opts):
    return {(ci, p): t for ci, o in enumerate(opts) for p, t in enumerate(o)}


def main():
    d = json.load(open(sys.argv[1]))
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    P = d["P"]
    L, _ = prep_logicals("XZ", "all")
    agree = dis = nlift = 0
    for opts in d["sols"][:n]:
        spec = spec_of_options(opts, P)
        T = times(opts)
        tabs = {b: abs_tables(spec, b) for b in "ZX"}
        for kind, S, cp, cons in L:
            b = "Z" if kind == "X" else "X"
            mine = bellman_ford(cons, T, P) is not None
            theirs = feasible_general(list(S), kind, *tabs[b])
            if mine == theirs:
                agree += 1
            else:
                dis += 1
            nlift += mine
    print(f"agree {agree} disagree {dis} (model-lifting {nlift})")


if __name__ == "__main__":
    main()
