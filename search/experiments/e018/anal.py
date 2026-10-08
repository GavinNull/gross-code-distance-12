"""E-018: which weight-11 orbits lift on a candidate, grouped by composition (data / r2 / r3 / r4 columns)."""
import collections
import json
import sys

import numpy as np

from search.experiments.e018.common import ext
from search.experiments.e018.cpgen import spec_from_times
from search.experiments.e018.lift import KIND_OF_BASIS, build_groups, solve
from search.experiments.e018.screen import logicals


def typ(E, j):
    if any(len(s) == 1 for s in E["col_sups"][j]):
        return "d"
    return "r" + str(len(E["col_sups"][j][0]))


def comp(E, S):
    c = collections.Counter(typ(E, j) for j in S)
    return " ".join(f"{k}{c[k]}" for k in ("d", "r2", "r3", "r4") if c[k])


def analyse(T, P, R=1):
    spec = spec_from_times(np.asarray(T), P).canonical()
    out = {}
    for b in "ZX":
        kind = KIND_OF_BASIS[b]
        E = ext(kind)
        groups, _, _, _ = build_groups(spec, R, b)
        tot, lif = collections.Counter(), collections.Counter()
        for S in logicals(kind, True):
            k = comp(E, S)
            tot[k] += 1
            if solve(S, groups)[0] is not None:
                lif[k] += 1
        out[b] = {k: f"{lif[k]}/{tot[k]}" for k in sorted(tot, key=lambda k: -tot[k])}
    return out


if __name__ == "__main__":
    T = json.loads(sys.argv[1]); P = int(sys.argv[2]); R = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    for b, d in analyse(T, P, R).items():
        print(b, d)
