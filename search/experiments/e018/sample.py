"""E-018 stage c: random legal per-check time shifts of Fig. 12 (period 8) by min-conflicts local search.
Classical control generator: uniform random restarts, greedy/annealed conflict repair; records distinct legal
solutions and their per-data-qubit X/Z patterns.

    PYTHONPATH=.:tests uv run python -m search.experiments.e018.sample --seed 0 --n 200
"""
import argparse
import json
from collections import Counter

import numpy as np

from search.experiments.e018.gen import _T, D, legal, pattern

KIDX = np.where(_T[:, 1] == 0, _T[:, 2], 72 + _T[:, 2])       # check variable index of each CNOT


def conflicts(sh):
    t = (_T[:, 3] + sh[KIDX]) % D
    key = _T[:, 0] * D + t
    c = np.bincount(key, minlength=144 * D)
    return int((c * (c - 1) // 2).sum())


def search(rng, steps=20000, T0=0.5):
    sh = rng.integers(0, D, 144)
    cur = conflicts(sh)
    for it in range(steps):
        if cur == 0:
            return sh
        v = rng.integers(144)
        old = sh[v]
        sh[v] = rng.integers(D)
        new = conflicts(sh)
        T = T0 * (1 - it / steps) + 1e-3
        if new <= cur or rng.random() < np.exp((cur - new) / T):
            cur = new
        else:
            sh[v] = old
    return None


def interleaved_qubits(sh):
    pat = pattern(sh[:72], sh[72:])
    n = 0
    for p, c in pat.items():
        s = p.replace(".", "")
        # cyclic sequence of 6 letters is non-interleaved iff it has exactly 2 kind changes cyclically
        ch = sum(s[i] != s[(i + 1) % len(s)] for i in range(len(s)))
        if ch > 2:
            n += c
    return n


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--steps", type=int, default=20000)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    sols, tries = [], 0
    while len(sols) < a.n:
        tries += 1
        sh = search(rng, a.steps)
        if sh is None:
            continue
        sh = (sh - sh[0]) % D
        assert legal(sh[:72], sh[72:])
        sols.append(sh.tolist())
        print(len(sols), tries, "interleaved qubits:", interleaved_qubits(sh), flush=True)
    json.dump(sols, open(f"results/E-018-gross-interleaved-12/random_legal_s{a.seed}.json", "w"))
