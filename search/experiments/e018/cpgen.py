"""E-018 stage c: CP-SAT generator of legal, deterministic, translation-symmetric single-ancilla schedules that keep
Fig. 12's per-check CNOT orders but may interleave and may have ancilla gaps (non-wrapping frame of depth P).

Variables: for each (type, colour) class, the times t_1 < ... < t_6 of its 6 CNOTs (Fig. 12 order) in [1, P-2]
(prep at t_1 - 1, meas at t_6 + 1; every check of the class uses the same times -> invariant under the 24
translations, which preserve colours).  Constraints: data qubit conflict-free; determinism: for every overlapping
X check a / Z check c (shared qubits u, v): [t_a(u) < t_c(u)] == [t_a(v) < t_c(v)].
Optionally `contiguous`: t_{k+1} = t_k + 1 (pure time shifts).  Random objective for diversity.

    PYTHONPATH=.:tests uv run python -m search.experiments.e018.cpgen --P 10 --n 50 --seed 0
"""
from __future__ import annotations

import argparse
import json

import numpy as np
from ortools.sat.python import cp_model

from evaluators.candidate import CheckTiming, ScheduleSpec
from search.experiments.e018.common import css, orders
from search.experiments.e018.gen import XCOL, ZCOL


def structure():
    xo, zo = orders()
    c = css()
    HX, HZ = np.asarray(c.HX), np.asarray(c.HZ)
    # data qubit -> list of (cls, pos) ; cls = 0..2 X colours, 3..5 Z colours
    touch = [[] for _ in range(144)]
    for i, o in enumerate(xo):
        for k, q in enumerate(o):
            touch[q].append((int(XCOL[i]), k))
    for j, o in enumerate(zo):
        for k, q in enumerate(o):
            touch[q].append((3 + int(ZCOL[j]), k))
    pairs = set()
    for i in range(72):
        for j in range(72):
            sh = sorted(set(xo[i]) & set(zo[j]))
            if not sh:
                continue
            assert len(sh) == 2
            u, v = sh
            pairs.add((int(XCOL[i]), list(xo[i]).index(u), 3 + int(ZCOL[j]), list(zo[j]).index(u),
                       list(xo[i]).index(v), list(zo[j]).index(v)))
    return touch, sorted(pairs)


def model(P, contiguous=False, extra=None):
    touch, pairs = structure()
    m = cp_model.CpModel()
    t = [[m.NewIntVar(1, P - 2, f"t{c}_{k}") for k in range(6)] for c in range(6)]
    for c in range(6):
        for k in range(5):
            if contiguous:
                m.Add(t[c][k + 1] == t[c][k] + 1)
            else:
                m.Add(t[c][k + 1] > t[c][k])
    seen = set()
    for q in range(144):
        key = tuple(sorted(touch[q]))
        if key in seen:
            continue
        seen.add(key)
        m.AddAllDifferent([t[c][k] for c, k in touch[q]])
    before = {}

    def bvar(a, i, c, k):
        key = (a, i, c, k)
        if key not in before:
            b = m.NewBoolVar(f"b{key}")
            m.Add(t[a][i] < t[c][k]).OnlyEnforceIf(b)
            m.Add(t[a][i] > t[c][k]).OnlyEnforceIf(b.Not())
            before[key] = b
        return before[key]
    for a, i, c, k, j, l in pairs:
        m.Add(bvar(a, i, c, k) == bvar(a, j, c, l))
    return m, t, before, touch, pairs


def spec_from_times(T, P, name=""):
    xo, zo = orders()

    def mk(o, times):
        return CheckTiming(int(times[0] - 1), int(times[5] + 1), tuple(sorted((int(q), int(tt)) for q, tt in zip(o, times))))
    return ScheduleSpec(P, tuple(mk(xo[i], T[XCOL[i]]) for i in range(72)),
                        tuple(mk(zo[j], T[3 + ZCOL[j]]) for j in range(72)), name=name)


def sample(P, n, seed, contiguous=False, time_limit=20):
    rng = np.random.default_rng(seed)
    m, t, before, touch, pairs = model(P, contiguous)
    out = []
    bs = list(before.values())
    for it in range(n):
        w = rng.integers(-5, 6, len(bs))
        tw = rng.integers(-3, 4, (6, 6))
        m.Maximize(sum(int(a) * b for a, b in zip(w, bs)) + sum(int(tw[c][k]) * t[c][k] for c in range(6) for k in range(6)))
        s = cp_model.CpSolver()
        s.parameters.max_time_in_seconds = time_limit
        s.parameters.num_workers = 1
        s.parameters.random_seed = int(seed * 1000 + it)
        st = s.Solve(m)
        if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return out, s.StatusName(st)
        T = [[s.Value(t[c][k]) for k in range(6)] for c in range(6)]
        if T not in out:
            out.append(T)
    return out, "ok"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--P", type=int, default=10)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--contiguous", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out, st = sample(a.P, a.n, a.seed, a.contiguous)
    print(f"P={a.P} contiguous={a.contiguous}: {len(out)} distinct solutions ({st})")
    json.dump({"P": a.P, "times": out}, open(a.out, "w"))
