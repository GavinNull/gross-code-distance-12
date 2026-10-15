"""E-028: complete list of low-weight code logicals of [[90,8,10]] (data columns only), per side, by the audited DFS
(E-014 algorithm) with the 45 translations (two data orbits).  Saved as sorted qubit tuples (orbit-expanded, verified).

    PYTHONPATH=.:tests uv run python -m search.experiments.e028.codelog --kind X --W 10
"""
from __future__ import annotations

import argparse
import json
import pickle
import time

import numpy as np

from search.experiments.e028 import common as C


def data_ext(kind):
    lab = [tuple(range(6))] * C.N2
    E = C.ext_general(kind, lab, group=C.GROUP)
    keep = [j for j in range(E["N"]) if any(len(s) == 1 for s in E["col_sups"][j])]
    assert len(keep) == C.NQ
    q_of = [next(s[0] for s in E["col_sups"][j] if len(s) == 1) for j in keep]
    pos = {j: k for k, j in enumerate(keep)}
    F = {"He": E["He"][:, keep], "Le": E["Le"][:, keep], "col_sups": [[(q,)] for q in q_of], "N": len(keep),
         "group": E["group"]}
    F["perms"] = np.array([[pos[int(P[j])] for j in keep] for P in E["perms"]])
    orb = np.full(len(keep), -1); reps = []
    for j in range(len(keep)):
        if orb[j] >= 0:
            continue
        o = sorted({int(P[j]) for P in F["perms"]})
        orb[o] = len(reps); reps.append(j)
    F["orbit"], F["reps"] = orb, reps
    return F, q_of


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True)
    ap.add_argument("--W", type=int, default=10)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--split", type=int, default=1)
    a = ap.parse_args()
    F, q_of = data_ext(a.kind)
    t0 = time.time()
    log = []
    sols, nodes, comp = C.dfs(F, a.W, stopfirst=0, workers=a.workers, split=a.split, log=log)
    assert comp
    allS = C.expand(F, sols)
    C.verify_logicals(F, allS)
    qs = sorted({tuple(sorted(q_of[j] for j in S)) for S in allS})
    from collections import Counter
    cnt = Counter(len(S) for S in qs)
    res = {"kind": a.kind, "W": a.W, "reps": len(sols), "total": len(qs), "by_weight": dict(sorted(cnt.items())),
           "nodes": nodes, "sec": round(time.time() - t0, 1)}
    print(json.dumps(res), flush=True)
    pickle.dump(qs, open(C.OUT / f"codelog_{a.kind}_W{a.W}.pkl", "wb"))
    with open(C.OUT / "codelog_summary.jsonl", "a") as f:
        f.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    main()
