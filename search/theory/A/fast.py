"""Theory A: vectorised enumeration of T(P) signatures + flat-hook filter (same lemma as flatcheck.py), for P = 10.
Signature rows: 6 (pi_X) + 6 (pi_Z) + 9 (G, min 0) small ints; representative time vectors kept.

    uv run python search/theory/A/fast.py --P 10
"""
from __future__ import annotations

import argparse
import itertools
import json
import pickle
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, "search/theory/A")
from sigs import Eset, config_weight, required  # noqa: E402

A, B = (0, 1, 2), (3, 4, 5)
OUT = Path("results/theoryA")


def side_configs(P):
    out = []
    for S in itertools.combinations(range(1, P - 2), 5):
        for perm in itertools.permutations((0,) + S):
            out.append(perm)
    return np.array(out, dtype=np.int64)


def enumerate_fast(P, part=0, nparts=1):
    X = side_configs(P)
    oX = np.argsort(X, axis=1)
    rows, reps = [], []
    nlegal = 0
    for ix, tx in enumerate(X):
        if ix % nparts != part:
            continue
        for s in range(P):
            TZ = X + s
            m = np.ones(len(TZ), bool)
            for xs, zs in ((A, B), (B, A)):
                vals = np.concatenate([np.broadcast_to(tx[list(xs)] % P, (len(TZ), 3)), TZ[:, list(zs)] % P], axis=1)
                m &= (np.diff(np.sort(vals, axis=1), axis=1) != 0).all(axis=1)
            G = np.empty((len(TZ), 9), dtype=np.int64)
            for k in range(3):
                for l in range(3):
                    gl = np.floor_divide(tx[A[k]] - TZ[:, B[l]], P)
                    m &= gl == np.floor_divide(tx[B[l]] - TZ[:, A[k]], P)
                    G[:, 3 * k + l] = gl
            if not m.any():
                continue
            nlegal += int(m.sum())
            G = G[m] - G[m].min(axis=1, keepdims=True)
            key = np.concatenate([np.broadcast_to(oX[ix], (len(G), 6)), oX[m], G], axis=1).astype(np.int8)
            u, first = np.unique(key, axis=0, return_index=True)
            rows.append(u)
            reps.append(np.concatenate([np.broadcast_to(tx, (len(u), 6)), TZ[m][first]], axis=1))
    K = np.concatenate(rows)
    Rp = np.concatenate(reps)
    K, first = np.unique(K, axis=0, return_index=True)
    return nlegal, K, Rp[first]


def flat_filter(K, code, d):
    req = {k: required(OUT / f"pairs_{code}_{k}.json", d) for k in ("X", "Z")}
    G = K[:, 12:].astype(np.int64)
    best = np.full(len(K), 99)
    for side, off in (("X", 0), ("Z", 6)):
        O = K[:, off:off + 6]
        for sl in (slice(4, 6), slice(0, 2), slice(3, 6)):
            # group rows by hook set
            hs = np.zeros(len(K), dtype=np.int64)
            for c in range(sl.start, sl.stop):
                hs |= 1 << O[:, c].astype(np.int64)
            for hmask in np.unique(hs):
                S = frozenset(i for i in range(6) if hmask >> i & 1)
                w = config_weight(S, req[side], d)
                if w is None:
                    continue
                sel = hs == hmask
                v = G[sel][:, Eset(S)]
                cost = None
                for c in range(int(v.min()), int(v.max()) + 1):
                    cc = np.abs(v - c).sum(axis=1)
                    cost = cc if cost is None else np.minimum(cost, cc)
                best[sel] = np.minimum(best[sel], w + cost)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--part", type=int, default=-1)
    ap.add_argument("--nparts", type=int, default=3)
    a = ap.parse_args()
    if a.part >= 0:
        nl, K, Rp = enumerate_fast(a.P, a.part, a.nparts)
        np.savez_compressed(OUT / f"fast_P{a.P}_part{a.part}.npz", nlegal=nl, K=K, Rp=Rp)
        print("part", a.part, nl, len(K))
        return
    parts = sorted(OUT.glob(f"fast_P{a.P}_part*.npz"))
    if parts and not (OUT / f"fast_P{a.P}.npz").exists():
        zs = [np.load(f) for f in parts]
        K = np.concatenate([z["K"] for z in zs]); Rp = np.concatenate([z["Rp"] for z in zs])
        K, first = np.unique(K, axis=0, return_index=True)
        np.savez_compressed(OUT / f"fast_P{a.P}.npz", nlegal=sum(int(z["nlegal"]) for z in zs), K=K, Rp=Rp[first])
    t0 = time.time()
    cache = OUT / f"fast_P{a.P}.npz"
    if cache.exists():
        z = np.load(cache)
        nlegal, K, Rp = int(z["nlegal"]), z["K"], z["Rp"]
    else:
        nlegal, K, Rp = enumerate_fast(a.P)
        np.savez_compressed(cache, nlegal=nlegal, K=K, Rp=Rp)
    print("enum", a.P, nlegal, len(K), round(time.time() - t0), flush=True)
    for code, d in (("bb90", 10), ("gross", 12)):
        best = flat_filter(K, code, d)
        kill = best <= d - 1
        surv = [(tuple(int(v) for v in k[:6]), tuple(int(v) for v in k[6:12]), tuple(int(v) for v in k[12:]))
                for k in K[~kill]]
        times = [(tuple(int(v) for v in r[:6]), tuple(int(v) for v in r[6:])) for r in Rp[~kill]]
        pickle.dump({"surv": surv, "times": times}, open(OUT / f"surv_{code}_P{a.P}.pkl", "wb"))
        print(json.dumps({"code": code, "P": a.P, "signatures": len(K), "killed": int(kill.sum()),
                          "survivors": int((~kill).sum()), "hist": dict(Counter(int(b) for b in best))}), flush=True)


if __name__ == "__main__":
    main()
