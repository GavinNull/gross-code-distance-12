"""E-018 stage c: how many single-hook weight-11 orbits (10 data columns + one r2 or r4 hook) lift, per candidate,
using the frame model (exact for disjoint supports in the bulk; validated against the DP in the journal).
Samples random legal schedules with cpgen (random objective) and reports the distribution.

    PYTHONPATH=.:tests uv run python -m search.experiments.e018.single_hook --P 14 --n 200 --seed 0
"""
import argparse
import collections
import json

import numpy as np

from search.experiments.e018.anal import comp
from search.experiments.e018.common import ext
from search.experiments.e018.cpgen import sample, spec_from_times
from search.experiments.e018.frame_model import feasible, read_tables
from search.experiments.e018.lift import KIND_OF_BASIS
from search.experiments.e018.screen import logicals

SINGLE = {}
for b in "ZX":
    k = KIND_OF_BASIS[b]
    E = ext(k)
    SINGLE[b] = [S for S in logicals(k, True) if comp(E, S) in ("d10 r21", "d10 r41")]


def single_lift(T, P):
    raw = spec_from_times(np.asarray(T), P)
    out = {}
    for b in "ZX":
        reads, ht = read_tables(raw, b)
        out[b] = sum(bool(feasible(S, KIND_OF_BASIS[b], reads, ht)) for S in SINGLE[b])
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--P", type=int, default=14)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    sols, st = sample(a.P, a.n, a.seed, time_limit=5)
    dist = collections.Counter()
    best = None
    for T in sols:
        r = single_lift(T, a.P)
        dist[(r["Z"], r["X"])] += 1
        if best is None or r["Z"] + r["X"] < best[0]:
            best = (r["Z"] + r["X"], T, r)
    print(f"P={a.P}: {len(sols)} schedules; (Z, X) single-hook lifting orbits (of {len(SINGLE['Z'])}, {len(SINGLE['X'])}):",
          sorted(dist.items()), "best", best, flush=True)
