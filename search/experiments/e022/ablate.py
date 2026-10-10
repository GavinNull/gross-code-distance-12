"""E-022: ablation of the expansion-half code (start view): which fault classes are needed to reach d_circ?
Fault classes: D = data_start, Rs = reset, and CNOT faults after Fd0/Fd1/Fd2 (layers 1/2/3) split by the qubit
side (L/R) and component (single / pair).  usage: ablate.py <key> <basis> [Wmax]
"""
from __future__ import annotations

import itertools
import json
import sys

import numpy as np

from search.experiments.e019.dfsrun import min_weight
from search.experiments.e022.ext import Ext
from search.experiments.e022.solve22 import instance

RES = "/Users/ephemeral/Desktop/qec-ai-search/results/E-022-morphing-criterion"


def fclass(E, f):
    kind, k, qs = f
    if kind in ("data_start", "reset", "data_end", "meas"):
        return kind
    side = "".join("L" if q < E.N else "R" for q in qs)
    return f"cx{k}{side}"


def dist(E, allowed, Wmax, tag):
    keep = np.array([fclass(E, f) in allowed and f[1] <= 3 for f in E.faults])
    path, norb, groups, Hd, Ld, _ = instance(E, "start", keep=keep, tag="_abl" + tag)
    W, sol, log = min_weight(path, norb, Wmax, npar=1)
    return W, ([fclass(E, E.faults[groups[c][0]]) for c in sol] if sol else None)


def main(key, basis, Wmax):
    E = Ext(key, basis)
    classes = sorted(set(fclass(E, f) for f in E.faults if f[1] <= 3))
    base = {"data_start", "reset"}
    out = dict(key=key, basis=basis, classes=classes)
    full, wit = dist(E, set(classes), Wmax, "full")
    out["full"] = full
    out["full_witness_classes"] = wit
    cx = [c for c in classes if c.startswith("cx")]
    # leave-one-out
    loo = {}
    for c in cx:
        loo[c] = dist(E, set(classes) - {c}, Wmax, "loo" + c)[0]
    out["leave_one_out"] = loo
    # smallest subsets of CNOT classes (plus D, Rs) that already reach 'full'
    best = None
    for s in range(0, len(cx) + 1):
        hits = []
        for sub in itertools.combinations(cx, s):
            d, w = dist(E, base | set(sub), Wmax, "sub" + "".join(sub))
            if d == full:
                hits.append(list(sub))
        if hits:
            best = dict(size=s, subsets=hits)
            break
    out["minimal_sufficient"] = best
    json.dump(out, open(f"{RES}/ablate_{key}_{basis}.json", "w"), indent=1)
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 9)
