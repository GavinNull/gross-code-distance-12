"""Theory A: apply the flat-hook lemma (Lemma F + readout-flip extension F') to every signature of T(P).

For each signature and each side (X: hooks of pi_X, Z: hooks of pi_Z), for each hook set h in {S2, P2(~S4), T3(~S3)}
with a witness logical (table (iii)): weight of the configuration w_h = 1 + |L| - |h|; bulk lift with uniform data and
c_h = cost(G, h) readout flips  =>  undetected logical of weight w_h + c_h.  A signature is killed if some w_h + c_h <= d-1.

    uv run python search/theory/A/flatcheck.py --code bb90 --P 8
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, "search/theory/A")
from sigs import LAB, config_weight, cost, enumerate_sigs, hooks, required  # noqa: E402

OUT = Path("results/theoryA")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--P", type=int, required=True)
    a = ap.parse_args()
    d = {"bb90": 10, "gross": 12}[a.code]
    req = {k: required(OUT / f"pairs_{a.code}_{k}.json", d) for k in ("X", "Z")}
    cache = OUT / f"sigs_P{a.P}.pkl"
    if cache.exists():
        nlegal, sigs = pickle.load(open(cache, "rb"))
    else:
        nlegal, sigs = enumerate_sigs(a.P)
        pickle.dump((nlegal, sigs), open(cache, "wb"))
    keys = list(sigs)
    G = np.array([k[2] for k in keys], dtype=np.int64)
    best = np.full(len(keys), 99)
    why = [None] * len(keys)
    for side, oi in (("X", 0), ("Z", 1)):
        for hn in ("S2", "P2", "T3"):
            # group by order (hook set depends only on the order)
            for o in set(k[oi] for k in keys):
                h = hooks(o)[hn]
                w = config_weight(h, req[side], d)
                if w is None:
                    continue
                idx = np.array([i for i, k in enumerate(keys) if k[oi] == o])
                c = cost(G[idx], h)
                tot = w + c
                for i, t in zip(idx, tot):
                    if t < best[i]:
                        best[i] = int(t)
                        why[i] = (side, hn, "".join(LAB[s] for s in sorted(h)), int(w), int(t - w))
    kill = best <= d - 1
    print(json.dumps({"code": a.code, "P": a.P, "legal_time_vectors": nlegal, "signatures": len(keys),
                      "killed": int(kill.sum()), "survivors": int((~kill).sum()),
                      "best_bound_hist": dict(Counter(int(b) for b in best))}))
    surv = [keys[i] for i in range(len(keys)) if not kill[i]]
    pickle.dump({"surv": surv, "times": [sigs[k] for k in surv]}, open(OUT / f"surv_{a.code}_P{a.P}.pkl", "wb"))
    for k in surv[:5]:
        print("survivor", [LAB[i] for i in k[0]], [LAB[i] for i in k[1]], np.array(k[2]).reshape(3, 3).tolist(), sigs[k])


if __name__ == "__main__":
    main()
