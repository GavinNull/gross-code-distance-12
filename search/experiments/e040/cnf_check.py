"""E-040: checks of the certificate CNF encoding.
  legal P:   enumerate every model of the legality part (projected on the time variables) and compare with enum.py's
             legal time vectors (exact set equality; feasible for P = 8, 9).
  pat P code sector witnesses.jsonl n: for n random (pattern, time vector) pairs (time vectors = signature
             representatives, half from rows where vec.test says the pattern applies), fix the time variables, unit
             propagate, and compare the CNF value of applies(k) with vec.test.
"""
from __future__ import annotations

import json
import random
import sys

import numpy as np
from pysat.solvers import Cadical153

from search.experiments.e040 import vec
from search.experiments.e040.bulk import Sector
from search.experiments.e040.cnf import Enc
from search.experiments.e040.codes import MOD, OUT
from search.experiments.e040.enum import legal_mask, side_configs


def times_of(E, model):
    pos = set(l for l in model if l > 0)
    t = {}
    for (s, l, v), var in E.e.items():
        if var in pos:
            t[(s, l)] = v
    return tuple(t[("X", l)] for l in range(6)), tuple(t[("Z", l)] for l in range(6))


def legal_check(P):
    E = Enc(P)
    S = Cadical153(bootstrap_with=E.cl)
    evars = list(E.e.values())
    got = set()
    while S.solve():
        m = S.get_model()
        tx, tz = times_of(E, m)
        got.add((tx, tz))
        S.add_clause([-E.e[("X", l, tx[l])] for l in range(6)] + [-E.e[("Z", l, tz[l])] for l in range(6)])
    X = side_configs(P)
    ref = set()
    for tx in X:
        for s in range(P):
            TZ = X + s
            mk = legal_mask(tx, TZ, P)
            for z in TZ[mk]:
                ref.add((tuple(int(v) for v in tx), tuple(int(v) for v in z)))
    print(json.dumps({"P": P, "cnf_models": len(got), "enum_vectors": len(ref), "equal": got == ref}))


def pat_check(P, code, sector, wpath, n, seed=1):
    C = MOD[code]
    rows = json.loads((OUT / f"sigs_P{P}.json").read_text())
    pats = [[tuple(x) for x in json.loads(l)["faults"]] for l in open(wpath)]
    rng = random.Random(seed)
    E = Enc(P)
    conds = [E.pattern(sector, f, C) for f in pats]
    tH = np.array([(r["tx"] if sector == "X" else r["tz"]) for r in rows])
    tR = np.array([(r["tz"] if sector == "X" else r["tx"]) for r in rows])
    S0 = Sector(code, sector, rows[0]["tx"], rows[0]["tz"], P)
    agree = pos = 0
    for _ in range(n):
        k = rng.randrange(len(pats))
        m = vec.test(S0, pats[k], tH, tR, P)
        idx = int(rng.choice(list(np.flatnonzero(m)))) if (rng.random() < 0.5 and m.any()) else rng.randrange(len(rows))
        r = rows[idx]
        # a random time vector with this row's signature-defining times shifted by a global constant is NOT in the
        # CNF's normal form; use the row itself (normal form by construction)
        assum = [E.e[("X", l, r["tx"][l])] for l in range(6)] + [E.e[("Z", l, r["tz"][l])] for l in range(6)]
        ok = sat_applies(E, conds[k], assum)
        # independent recomputation with bulk.Sector on this row
        Sr = Sector(code, sector, r["tx"], r["tz"], P)
        hooks_ok = all(frozenset(f[2]) in Sr.suffixes() for f in pats[k] if f[0] == "h")
        bulk = hooks_ok and Sr.is_witness([(f[0], f[1], frozenset(f[2]), f[3]) if f[0] == "h" else f for f in pats[k]])[0]
        agree += (ok == bool(m[idx]) == bulk)
        pos += bool(m[idx])
    print(json.dumps({"P": P, "code": code, "sector": sector, "tested": n, "applies": pos, "agree": agree}))


_defsolver = {}


def sat_applies(E, conds, assum):
    key = id(E)
    if key not in _defsolver:
        # definitions + legality only: every clause except the per-pattern blocking clauses
        blocking = set(map(tuple, E.blocking))
        _defsolver[key] = Cadical153(bootstrap_with=[c for c in E.cl if tuple(c) not in blocking])
    S = _defsolver[key]
    assert S.solve(assumptions=assum), "time vector not legal in CNF"
    mdl = set(S.get_model())
    return all((x in mdl) for x in conds if x != E.TRUE) and all(x != -E.TRUE for x in conds)


if __name__ == "__main__":
    if sys.argv[1] == "legal":
        legal_check(int(sys.argv[2]))
    else:
        pat_check(int(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5], int(sys.argv[6]))
