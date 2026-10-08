"""E-018 stage c: simulated annealing over translation-symmetric class-level CNOT times (non-wrapping frame of depth
P, Fig. 12 per-check orders), objective = number of lifting weight-11 orbits (exact checker, R=1, both bases);
candidates with objective 0 are re-checked at R=2,3 (orbits).  `--random` = classical control: same budget of
evaluations on independent random legal schedules (random-objective CP-SAT samples), no annealing.

    PYTHONPATH=.:tests uv run python -m search.experiments.e018.sa --P 14 --seed 0 --evals 200 --out ...
"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np

from search.experiments.e018.cpgen import sample, spec_from_times, structure
from search.experiments.e018.lift import check_orders
from search.experiments.e018.screen import interleaved_qubits, lift_counts

TOUCH, PAIRS = structure()
TOUCH_KEYS = sorted({tuple(sorted(t)) for t in TOUCH})


def legal_det(T, P):
    T = np.asarray(T)
    if (T[:, 0] < 1).any() or (T[:, 5] > P - 2).any() or (np.diff(T, axis=1) <= 0).any():
        return False
    for key in TOUCH_KEYS:
        ts = [T[c, k] for c, k in key]
        if len(set(ts)) != len(ts):
            return False
    for a, i, c, k, j, l in PAIRS:
        if (T[a, i] < T[c, k]) != (T[a, j] < T[c, l]):
            return False
    return True


def objective(T, P, Rs=(1,)):
    spec = spec_from_times(np.asarray(T), P).canonical()
    check_orders(spec)
    lc = lift_counts(spec, list(Rs), reps=True)
    return sum(lc.values()), lc, interleaved_qubits(spec)


def neighbour(T, P, rng):
    T = np.array(T)
    for _ in range(200):
        U = T.copy()
        c = rng.integers(6)
        r = rng.random()
        if r < 0.4:      # shift one CNOT time
            k = rng.integers(6); U[c, k] += rng.choice([-2, -1, 1, 2])
        elif r < 0.7:    # shift a suffix / prefix of the class
            k = rng.integers(1, 6); d = rng.choice([-1, 1])
            if rng.random() < 0.5:
                U[c, k:] += d
            else:
                U[c, :k] += d
        else:            # shift whole class
            U[c] += rng.choice([-2, -1, 1, 2])
        if legal_det(U, P):
            return U.tolist()
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--P", type=int, default=14)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--evals", type=int, default=200)
    ap.add_argument("--T0", type=float, default=8.0)
    ap.add_argument("--random", action="store_true")
    ap.add_argument("--start", default=None, help="JSON 6x6 times to start from")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    f = open(a.out, "a")
    cache = {}

    def ev(T):
        k = json.dumps(T)
        if k not in cache:
            o, lc, iq = objective(T, a.P)
            rec = {"T": T, "P": a.P, "obj": o, "lift": lc, "iq": iq}
            if o == 0:
                o2, lc2, _ = objective(T, a.P, Rs=(2, 3))
                rec["lift23"] = lc2
            cache[k] = rec
            f.write(json.dumps(rec) + "\n"); f.flush()
        return cache[k]

    t0 = time.time()
    if a.random:
        n = 0
        while n < a.evals:
            sols, st = sample(a.P, 10, int(rng.integers(1 << 20)), time_limit=10)
            for T in sols:
                if n >= a.evals:
                    break
                r = ev(T); n += 1
                print(n, r["obj"], r["lift"], r["iq"], flush=True)
        return
    if a.start:
        cur = json.loads(a.start)
    else:
        sols, _ = sample(a.P, 5, a.seed, time_limit=10)
        recs = [ev(T) for T in sols]
        cur = min(recs, key=lambda r: r["obj"])["T"]
    cr = ev(cur)
    best = cr
    for it in range(a.evals):
        nb = neighbour(cur, a.P, rng)
        if nb is None:
            continue
        r = ev(nb)
        temp = a.T0 * (1 - it / a.evals) + 0.1
        if r["obj"] <= cr["obj"] or rng.random() < np.exp((cr["obj"] - r["obj"]) / temp):
            cur, cr = nb, r
        if r["obj"] < best["obj"]:
            best = r
            print(f"[{time.time() - t0:.0f}s] it {it} best {best['obj']} {best['lift']} iq {best['iq']} T {best['T']}", flush=True)
        if best["obj"] == 0:
            print("objective 0 reached:", best, flush=True)
            break
    print("final best", best, flush=True)


if __name__ == "__main__":
    main()
