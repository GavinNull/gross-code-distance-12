"""E-021 follow-up (2b): period-8 circuits in the Fig. 12 extended-code class (evaluator task gross-dcirc limit).

At P = 8 every check is prep, 6 CNOTs at offsets 1..6, meas at 7 (E-020 / audit: forced by 0 < off(cnot) < off(meas)
< P).  Free per check (or per Hs-class): the order (one of the 8 orders with Fig. 12's extended code: within-pair
swaps of positions 1-2, 5-6, and reversal) and the start s in Z_8.  Constraints: data conflicts (times mod 8
distinct on each data qubit) and determinism (floor((T_x(u)-T_z(u))/8) == floor((T_x(v)-T_z(v))/8) on the two
shared qubits of every overlapping X/Z pair, absolute T = s + offset).  Complete SAT enumeration (global shift fixed
by s = 0 for X check/class 0); each solution's circuit then goes to the exact lift (lift21 --fig12class) R = 1..6.

    PYTHONPATH=.:tests uv run python -m search.experiments.e021.p8class --sub "1,2;0,3"      # colour-symmetric
    PYTHONPATH=.:tests uv run python -m search.experiments.e021.p8class --sub ""             # per-check free
"""
from __future__ import annotations

import argparse
import itertools
import json
import time
from pathlib import Path

from pysat.formula import IDPool
from pysat.solvers import Cadical153

from search.experiments.e021.mono import fig12_labels, table
from search.experiments.e021.nwsat import Family, parse_sub

OUT = Path("results/E-021-gross-new-orders")
N2 = 72
P = 8


def class_orders(o):
    """8 orders with the extended code of order o."""
    out = set()
    for sw1, sw2, rev in itertools.product((0, 1), (0, 1), (0, 1)):
        x = list(o)
        if sw1:
            x[0], x[1] = x[1], x[0]
        if sw2:
            x[4], x[5] = x[5], x[4]
        if rev:
            x = x[::-1]
        out.add(tuple(x))
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sub", default="1,2;0,3")
    ap.add_argument("--max_sol", type=int, default=100000)
    ap.add_argument("--max_sec", type=float, default=3600)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    t0 = time.time()
    F = Family(parse_sub(a.sub) if a.sub else [(0, 0)])
    T = table()
    f12 = fig12_labels()
    units = [(ty, k) for ty in "XZ" for k in range(F.nc)]          # one unit per (type, class)
    opts = {}
    for ty, k in units:
        o = f12[ty][F.reps[k]]
        opts[(ty, k)] = [(oo, s) for oo in class_orders(o) for s in range(P)]
    pool = IDPool()
    S = Cadical153()
    x = {u: [pool.id(("x",) + u + (n,)) for n in range(len(opts[u]))] for u in units}
    for u in units:
        S.add_clause(x[u])
        for i, j in itertools.combinations(x[u], 2):
            S.add_clause([-i, -j])
    # fix global shift
    for n, (oo, s) in enumerate(opts[("X", 0)]):
        if s != 0:
            S.add_clause([-x[("X", 0)][n]])

    def tm(u, n, i, q):
        oo, s = opts[u][n]
        lab = list(T[u[0]][i]).index(q)
        return s + 1 + oo.index(lab)
    # data conflicts: for each data qubit, CNOT (unit, check) pairs; forbid option pairs with equal time mod 8
    touch = [[] for _ in range(144)]
    for ty in "XZ":
        for i in range(N2):
            for q in T[ty][i]:
                touch[int(q)].append(((ty, F.cls[i]), i))
    done = set()
    ncl = 0
    for q in range(144):
        for (u1, i1), (u2, i2) in itertools.combinations(touch[q], 2):
            key = (u1, u2, tuple(sorted([list(T[u1[0]][i1]).index(q)])), list(T[u2[0]][i2]).index(q)) \
                if u1 != u2 else None
            for n1 in range(len(opts[u1])):
                for n2 in range(len(opts[u2])):
                    if u1 == u2 and n1 != n2:
                        continue
                    if tm(u1, n1, i1, q) % P == tm(u2, n2, i2, q) % P:
                        cl = (-x[u1][n1], -x[u2][n2]) if u1 != u2 else (-x[u1][n1],)
                        if cl not in done:
                            done.add(cl); S.add_clause(list(cl)); ncl += 1
    # determinism
    for ia in range(N2):
        qa = set(int(q) for q in T["X"][ia])
        for ic in range(N2):
            ov = sorted(qa & set(int(q) for q in T["Z"][ic]))
            if not ov:
                continue
            ua, uc = ("X", F.cls[ia]), ("Z", F.cls[ic])
            for n1 in range(len(opts[ua])):
                for n2 in range(len(opts[uc])):
                    d = [(tm(ua, n1, ia, q) - tm(uc, n2, ic, q)) // P for q in ov]
                    if d[0] != d[1]:
                        cl = (-x[ua][n1], -x[uc][n2])
                        if cl not in done:
                            done.add(cl); S.add_clause(list(cl)); ncl += 1
    print(f"units {len(units)} options/unit {len(opts[units[0]])} clauses {ncl} {time.time() - t0:.0f}s", flush=True)
    sols = []
    status = "COMPLETE"
    while True:
        if time.time() - t0 > a.max_sec or len(sols) >= a.max_sol:
            status = "TRUNCATED"; break
        if not S.solve():
            break
        m = set(l for l in S.get_model() if l > 0)
        sel = {u: next(n for n in range(len(opts[u])) if x[u][n] in m) for u in units}
        sols.append({f"{u[0]},{u[1]}": [list(opts[u][sel[u]][0]), opts[u][sel[u]][1]] for u in units})
        S.add_clause([-x[u][sel[u]] for u in units])
    print(f"{status}: {len(sols)} legal+deterministic solutions (global shift fixed) {time.time() - t0:.0f}s", flush=True)
    tag = a.tag or f"p8class_H{len(F.Hs)}"
    (OUT / f"{tag}.json").write_text(json.dumps({"sub": a.sub, "status": status, "sols": sols}))
    # specs
    for n, sol in enumerate(sols):
        d = {"format": "qec-schedule/v1", "period": P, "x_checks": [], "z_checks": []}
        for ty, key in (("X", "x_checks"), ("Z", "z_checks")):
            for i in range(N2):
                oo, s = sol[f"{ty},{F.cls[i]}"]
                cn = [[int(T[ty][i][lab]), (s + 1 + p) % P] for p, lab in enumerate(oo)]
                d[key].append({"prep": s % P, "meas": (s + 7) % P, "cnots": cn})
        (OUT / f"{tag}_spec{n}.json").write_text(json.dumps(d))


if __name__ == "__main__":
    main()
