"""E-028: tabu local search over per-check type assignments minimising the number of violated eager clauses
(eager.py, valid "not all present" clauses from weight-<=W code logicals).  Heuristic (finds assignments; proves
nothing).  An assignment with 0 violations is then tested by the complete W=8 DFS (dext.dext_dfs).

    PYTHONPATH=.:tests uv run python -m search.experiments.e028.ls_types --kind X --W 10 --seed 1 --sec 300
"""
from __future__ import annotations

import argparse
import json
import pickle
import random
import time
from collections import defaultdict

from search.experiments.e028 import common as C
from search.experiments.e028.dext import dext_dfs, types
from search.experiments.e028.eager import eager_clauses

N2 = C.N2


def build(kind, W):
    TY = types(kind)
    RS = [C.resid_sets(o) for o in TY]
    real = C.realisations(kind)
    ecl = eager_clauses(kind, pickle.load(open(C.OUT / f"codelog_{kind}_W{W}.pkl", "rb")))
    # clause -> list of (check, frozenset of types realising); key realised at a single check for these keys
    cls = []
    for ks in ecl:
        lits = []
        for k in ks:
            per = defaultdict(set)
            for a, U in real[k]:
                for t in range(len(TY)):
                    if U in RS[t]:
                        per[a].add(t)
            lits.append(tuple((a, frozenset(ts)) for a, ts in per.items()))
        cls.append(lits)
    return TY, cls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True)
    ap.add_argument("--W", type=int, default=10)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--sec", type=float, default=300)
    ap.add_argument("--tabu", type=int, default=10)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    TY, cls = build(a.kind, a.W)
    nt = len(TY)
    byc = defaultdict(list)
    for ci, lits in enumerate(cls):
        for key in lits:
            for a_, _ in key:
                if ci not in byc[a_]:
                    byc[a_].append(ci)
    asg = [rng.randrange(nt) for _ in range(N2)]

    def viol(ci, asg):
        return all(any(asg[c] in ts for c, ts in key) for key in cls[ci])
    nv = sum(viol(ci, asg) for ci in range(len(cls)))
    best = nv
    tabu = {}
    T0 = time.time(); it = 0
    found = []
    while time.time() - T0 < a.sec:
        it += 1
        if nv == 0:
            E = C.ext_general(a.kind, [TY[t] for t in asg])
            sols, nodes, comp = dext_dfs(E, 8, stopfirst=1, workers=1)
            rec = {"orders": [C.name(TY[t]) for t in asg], "dext_ge9": not sols, "it": it}
            print("ZERO", json.dumps(rec), flush=True)
            found.append(rec)
            if not sols:
                break
            # perturb
            for _ in range(3):
                asg[rng.randrange(N2)] = rng.randrange(nt)
            nv = sum(viol(ci, asg) for ci in range(len(cls)))
            continue
        vio = [ci for ci in range(len(cls)) if viol(ci, asg)] if it % 1 == 0 else None
        ci = rng.choice(vio)
        cands = []
        for c in sorted({c for key in cls[ci] for c, _ in key}):
            old = asg[c]
            base = sum(viol(cj, asg) for cj in byc[c])
            for t in range(nt):
                if t == old:
                    continue
                asg[c] = t
                d = sum(viol(cj, asg) for cj in byc[c]) - base
                asg[c] = old
                if tabu.get((c, t), -1) > it and nv + d >= best:
                    continue
                cands.append((d, rng.random(), c, t))
        if not cands:
            continue
        d, _, c, t = min(cands)
        tabu[(c, asg[c])] = it + a.tabu
        asg[c] = t
        nv += d
        if nv < best:
            best = nv
            print(f"it {it} best {best} {time.time() - T0:.0f}s", flush=True)
    print("END", json.dumps({"kind": a.kind, "W": a.W, "seed": a.seed, "best": best, "it": it,
                             "zeros": len(found)}), flush=True)


if __name__ == "__main__":
    main()
