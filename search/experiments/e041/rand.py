"""E-041 random legal schedules for W(P)/Mg(P) with 'window' representation: each check's 6 CNOTs inside
`win` consecutive layers (W9: win 7, P 9; Mg8: win 7, P 8), found by min-conflicts repair from a random start."""
from __future__ import annotations

import numpy as np

from search.experiments.e041.fast import NK, viol


def random_check(rng, P, win):
    s = int(rng.integers(0, P)) + 1
    slots = rng.permutation(win)[:6]
    return s + slots


def normalise(tau, P):
    for k in range(tau.shape[0]):
        tau[k] -= ((tau[k].min() - 1) // P) * P
    return tau


def mutate(tau, k, rng, win):
    m = rng.random()
    if m < 0.5:
        a, b = rng.choice(6, 2, replace=False)
        tau[k, a], tau[k, b] = tau[k, b], tau[k, a]
    elif m < 0.8:
        a = int(rng.integers(6))
        lo = tau[k].max() - (win - 1)
        hi = tau[k].min() + (win - 1)
        used = set(tau[k].tolist())
        cand = [t for t in range(lo, hi + 1) if t not in used]
        tau[k, a] = cand[int(rng.integers(len(cand)))]
    else:
        tau[k] += int(rng.choice([-1, 1]))


def random_legal(rng, P, win=7, iters=200000):
    tau = np.array([random_check(rng, P, win) for _ in range(NK)], np.int64)
    v = viol(tau, P, win - 1)
    for _ in range(iters):
        if v == 0:
            return normalise(tau, P)
        k = int(rng.integers(NK))
        old = tau[k].copy()
        mutate(tau, k, rng, win)
        v2 = viol(tau, P, win - 1)
        if v2 <= v or rng.random() < 0.01:
            v = v2
        else:
            tau[k] = old
    return None
