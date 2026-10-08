"""E-018: independent cross-check of the DP (lift.solve) by plain meet-in-the-middle over the same augmented groups
(full product, left half 5 groups, right half 6) on random logicals, lifting and non-lifting.

    PYTHONPATH=.:tests uv run python -m search.experiments.e018.crosscheck --schedule <json> --R 1 2 --n 40
"""
import argparse
import itertools
import random

from search.experiments.e018.lift import KIND_OF_BASIS, build_groups, solve, spec_of
from search.experiments.e018.common import load_logicals


def mitm(S, groups):
    G = [sorted(set(groups[j])) for j in S]
    left = set()
    for c in itertools.product(*G[:5]):
        x = 0
        for m in c:
            x ^= m
        left.add(x)
    for c in itertools.product(*G[5:]):
        x = 0
        for m in c:
            x ^= m
        if x in left:
            return True
    return False


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--schedule", required=True)
    ap.add_argument("--R", type=int, nargs="+", default=[1, 2])
    ap.add_argument("--n", type=int, default=40)
    a = ap.parse_args()
    spec = spec_of(a.schedule).canonical()
    rng = random.Random(0)
    for R in a.R:
        for b in "ZX":
            groups, _, _, _ = build_groups(spec, R, b)
            sols = load_logicals(KIND_OF_BASIS[b])
            sample = rng.sample(sols, a.n)
            agree = 0; pos = 0
            for S in sample:
                d = solve(S, groups)[0] is not None
                m = mitm(S, groups)
                agree += d == m; pos += m
            print(f"R={R} {b}: {agree}/{a.n} agree (MITM lifting {pos})", flush=True)
