"""E-020: legal + deterministic per-check-free pipelined schedules at period P (Fig. 12 per-check CNOT orders).

Per check an *option* = absolute CNOT times t_1 < ... < t_6 with t_1 in [1, P] and t_6 - t_1 <= P - 3 (room for
prep before t_1 and meas after t_6 inside one period; where exactly prep / meas sit inside the idle gap only adds
ancilla idle locations equivalent to prep / meas faults, so it does not change which weight-11 logicals exist up to
equivalent faults -- see journal).  #options = P * C(P-3, 5): P=8: 8, P=9: 54, P=10: 210, P=11: 616.
Legal: data qubit's 6 CNOT times distinct mod P.  Deterministic (audit-validated 121/121 vs stim):
for every X check a and Z check c sharing data u, v: floor((t_a(u)-t_c(u))/P) == floor((t_a(v)-t_c(v))/P).
Global time shift fixed by t_1(X check 0) = 1 (an option-level shift by P is a no-op for both criteria).

    PYTHONPATH=.:tests uv run python -m search.experiments.e020.plegal --P 9 --cap 100000
"""
from __future__ import annotations

import argparse
import itertools
import json
import time

from pysat.card import CardEnc, EncType
from pysat.formula import IDPool
from pysat.solvers import Cadical153

from search.experiments.e018.common import orders

OUT = "results/E-020-gross-perchk-pipeline"


def options(P):
    res = []
    for t1 in range(1, P + 1):
        for rest in itertools.combinations(range(1, P - 2), 5):
            res.append((t1,) + tuple(t1 + r for r in rest))
    return res


def checks():
    xo, zo = orders()
    return [("X", i, list(o)) for i, o in enumerate(xo)] + [("Z", j, list(o)) for j, o in enumerate(zo)]


def det_ok(P, ta_u, tc_u, ta_v, tc_v):
    return (ta_u - tc_u) // P == (ta_v - tc_v) // P


def build(P, fix0=True, extra=None, lazy_det=False):
    """lazy_det: do not add the forbidden-pair determinism clauses; instead return them in pool.det_table
    {(a, c): (ga, gc, set of forbidden (g1, g2))} for lazy addition (sound: they are only added when violated)."""
    C = checks()
    O = options(P)
    pool = IDPool()
    x = [[pool.id(("x", ci, k)) for k in range(len(O))] for ci in range(len(C))]
    cnf = []
    for ci in range(len(C)):
        cnf += CardEnc.equals(lits=x[ci], bound=1, vpool=pool, encoding=EncType.seqcounter).clauses
    # time literal y[ci][pos][t mod P] <-> OR of options putting CNOT pos at t
    y = {}
    for ci in range(len(C)):
        for p in range(6):
            for r in range(P):
                v = pool.id(("y", ci, p, r))
                y[ci, p, r] = v
                opts = [x[ci][k] for k, o in enumerate(O) if o[p] % P == r]
                cnf.append([-v] + opts)
                for l in opts:
                    cnf.append([-l, v])
    touch = [[] for _ in range(144)]
    for ci, (_, _, o) in enumerate(C):
        for p, q in enumerate(o):
            touch[q].append((ci, p))
    for q in range(144):
        for r in range(P):
            cnf += CardEnc.atmost(lits=[y[ci, p, r] for ci, p in touch[q]], bound=1, vpool=pool,
                                  encoding=EncType.pairwise).clauses
    # determinism: forbidden option pairs, via per-(check, qubit-pair) absolute-time literals
    ndet = 0
    nx = 72
    for a in range(nx):
        oa = C[a][2]
        for c in range(nx, 2 * nx):
            oc = C[c][2]
            sh = sorted(set(oa) & set(oc))
            if not sh:
                continue
            u, v = sh
            pa_u, pa_v, pc_u, pc_v = oa.index(u), oa.index(v), oc.index(u), oc.index(v)
            # signature of an option on (u, v): absolute times; group options by signature to shrink clauses
            sa, sc = {}, {}
            for k, o in enumerate(O):
                sa.setdefault((o[pa_u], o[pa_v]), []).append(k)
                sc.setdefault((o[pc_u], o[pc_v]), []).append(k)
            ga = {g: pool.id(("ga", a, c, g)) for g in sa}
            gc = {g: pool.id(("gc", a, c, g)) for g in sc}
            for g, ks in sa.items():
                cnf.append([-ga[g]] + [x[a][k] for k in ks])
                for k in ks:
                    cnf.append([-x[a][k], ga[g]])
            for g, ks in sc.items():
                cnf.append([-gc[g]] + [x[c][k] for k in ks])
                for k in ks:
                    cnf.append([-x[c][k], gc[g]])
            if lazy_det:
                pool_det = getattr(pool, "det_table", {})
                forb = [(g1, g2) for g1 in sa for g2 in sc if not det_ok(P, g1[0], g2[0], g1[1], g2[1])]
                pool_det[(a, c)] = (ga, gc, (pa_u, pa_v, pc_u, pc_v), forb)
                pool.det_table = pool_det
                continue
            for g1 in sa:
                for g2 in sc:
                    if not det_ok(P, g1[0], g2[0], g1[1], g2[1]):
                        cnf.append([-ga[g1], -gc[g2]])
                        ndet += 1
    if fix0:
        cnf.append([x[0][k] for k, o in enumerate(O) if o[0] == 1])
    return C, O, x, cnf, pool


def enumerate_(P, cap, solver_cls=Cadical153):
    C, O, x, cnf, pool = build(P)
    t0 = time.time()
    sols = []
    with solver_cls(bootstrap_with=cnf) as S:
        while len(sols) < cap and S.solve():
            mdl = S.get_model()
            pos = set(l for l in mdl if l > 0)
            sv = [next(k for k in range(len(O)) if x[ci][k] in pos) for ci in range(len(C))]
            sols.append(sv)
            S.add_clause([-x[ci][sv[ci]] for ci in range(len(C))])
            if len(sols) % 100 == 0:
                print(len(sols), f"{time.time() - t0:.0f}s", flush=True)
    complete = len(sols) < cap
    return C, O, sols, complete, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--P", type=int, default=9)
    ap.add_argument("--cap", type=int, default=100000)
    a = ap.parse_args()
    C, O, sols, complete, sec = enumerate_(a.P, a.cap)
    print(f"P={a.P}: legal+deterministic (t1(X0)=1): {len(sols)} complete={complete} {sec:.1f}s", flush=True)
    json.dump({"P": a.P, "complete": complete, "sec": sec,
               "sols": [[list(O[k]) for k in sv] for sv in sols]}, open(f"{OUT}/plegal_P{a.P}.json", "w"))


if __name__ == "__main__":
    main()
