"""E-020 step 1: complete enumeration of data-conflict-free per-check start assignments at period 8.

At P = 8 the evaluator rule 0 < off(cnot) < off(meas) < P with 6 CNOTs in Fig. 12's per-check order forces offsets
1..6 and meas offset 7, so a period-8 candidate keeping Fig. 12's orders is exactly a start s_c in Z_8 per check
(144 checks).  CNOT k (k = 1..6) of check c acts at time s_c + k (mod 8).  Legal iff each data qubit's 6 CNOT times
are distinct mod 8.  Global shift s -> s + 1 is a symmetry; we fix s of X check 0 to its Fig. 12 value.

Encoding: one-hot booleans x[c][s]; for each data qubit q and time t: at most one of the 6 checks c on q has
s_c = t - k_c(q).  Enumeration by a SAT solver with blocking clauses on the s-vector (complete when the solver
returns UNSAT after the last blocking clause).

    PYTHONPATH=.:tests uv run python -m search.experiments.e020.p8legal
"""
from __future__ import annotations

import json
import sys
import time

import numpy as np
from pysat.card import CardEnc, EncType
from pysat.formula import IDPool
from pysat.solvers import Cadical153

from search.experiments.e018.gen import SPEC0

D = 8
OUT = "results/E-020-gross-perchk-pipeline"


def checks():
    """list of (kind, i, {q: k}) with k = CNOT offset 1..6 (Fig. 12)."""
    res = []
    for kind, chk in (("X", SPEC0.x_checks), ("Z", SPEC0.z_checks)):
        for i, c in enumerate(chk):
            _, offs = c.offsets(D)
            res.append((kind, i, {q: o for o, q in offs}, c.prep))
    return res


def build(fix0=True):
    C = checks()
    pool = IDPool()
    x = [[pool.id(("x", ci, s)) for s in range(D)] for ci in range(len(C))]
    cnf = []
    for ci in range(len(C)):
        cnf += CardEnc.equals(lits=x[ci], bound=1, vpool=pool, encoding=EncType.pairwise).clauses
    touch = [[] for _ in range(144)]
    for ci, (_, _, mp, _) in enumerate(C):
        for q, k in mp.items():
            touch[q].append((ci, k))
    for q in range(144):
        for t in range(D):
            lits = [x[ci][(t - k) % D] for ci, k in touch[q]]
            cnf += CardEnc.atmost(lits=lits, bound=1, vpool=pool, encoding=EncType.pairwise).clauses
    if fix0:
        cnf.append([x[0][C[0][3]]])
    return C, x, cnf


def main(cap=200000):
    C, x, cnf = build()
    t0 = time.time()
    sols = []
    with Cadical153(bootstrap_with=cnf) as S:
        while S.solve():
            mdl = set(l for l in S.get_model() if l > 0)
            sv = [next(s for s in range(D) if x[ci][s] in mdl) for ci in range(len(C))]
            sols.append(sv)
            S.add_clause([-x[ci][sv[ci]] for ci in range(len(C))])
            if len(sols) % 1000 == 0:
                print(len(sols), f"{time.time() - t0:.0f}s", flush=True)
            if len(sols) >= cap:
                print("CAP reached", flush=True)
                break
        else:
            pass
        complete = len(sols) < cap
    print(f"legal assignments (s_X0 fixed): {len(sols)} complete={complete} {time.time() - t0:.1f}s", flush=True)
    json.dump({"complete": complete, "sols": sols, "checks": [(k, i) for k, i, _, _ in C]},
              open(f"{OUT}/p8_legal.json", "w"))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 200000)
