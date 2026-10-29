"""E-040: enumerate every legal translation-invariant single-ancilla schedule at period P (code independent: for both
[[90,8,10]] and gross the X check i overlaps 9 Z checks, each on one L qubit via (X Ai, Z Bj) and one R qubit via
(X Bj, Z Ai), i, j = 1..3 -- verified in sigs_check) and reduce it to its bulk signature

    sig = (sigma_X, sigma_Z, G),  G[i][j] = floor((tX[Ai] - tZ[Bj]) / P)  (= floor((tX[Bj] - tZ[Ai]) / P), determinism)

Class (period P): every X check uses CNOT times tX[label] (absolute, instance k at +kP), every Z check tZ[label];
ancilla needs a prep layer before its first CNOT and a measurement layer after its last, next prep >= P later, so each
side's 6 CNOT times are distinct with span <= P-3; on every data qubit the 6 CNOT times are distinct mod P
(L: tX[A*], tZ[B*]; R: tX[B*], tZ[A*]); determinism: equal floor on both shared qubits of every overlapping pair.
Normalisation: global time shift (min tX = 0) and Z instance relabel (tZ -> tZ + P) => G normalised to min G = 0.

    uv run python -m search.experiments.e040.enum --P 8
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np

OUT = Path("results/E-040-min-period")
A, B = (0, 1, 2), (3, 4, 5)


def side_configs(P):
    """all 6-tuples of distinct CNOT times (indexed by label A1..B3) with min 0 and span <= P-3."""
    out = []
    for S in itertools.combinations(range(1, P - 2), 5):
        S = (0,) + S
        for perm in itertools.permutations(S):
            out.append(perm)
    return np.array(out, dtype=np.int64)


def legal_mask(tx, TZ, P):
    """tx: (6,), TZ: (n,6) absolute.  returns bool mask of legal combos."""
    m = np.ones(len(TZ), bool)
    for xs, zs in ((A, B), (B, A)):
        vals = np.concatenate([np.broadcast_to(tx[list(xs)] % P, (len(TZ), 3)), TZ[:, list(zs)] % P], axis=1)
        s = np.sort(vals, axis=1)
        m &= (np.diff(s, axis=1) != 0).all(axis=1)
    for i in range(3):
        for j in range(3):
            gl = np.floor_divide(tx[A[i]] - TZ[:, B[j]], P)
            gr = np.floor_divide(tx[B[j]] - TZ[:, A[i]], P)
            m &= gl == gr
    return m


def enumerate_P(P):
    X = side_configs(P)
    sigs = {}
    nlegal = 0
    for tx in X:
        ox = tuple(int(v) for v in np.argsort(tx, kind="stable"))
        for s in range(P):
            TZ = X + s
            m = legal_mask(tx, TZ, P)
            if not m.any():
                continue
            nlegal += int(m.sum())
            Z = TZ[m]
            G = np.stack([np.floor_divide(tx[A[i]] - Z[:, B[j]], P) for i in range(3) for j in range(3)], axis=1)
            G = G - G.min(axis=1, keepdims=True)
            oz = np.argsort(Z, axis=1, kind="stable")
            for k in range(len(Z)):
                key = (ox, tuple(int(v) for v in oz[k]), tuple(int(v) for v in G[k]))
                if key not in sigs:
                    sigs[key] = (tx.tolist(), Z[k].tolist())
    return nlegal, sigs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--P", type=int, required=True)
    a = ap.parse_args()
    nlegal, sigs = enumerate_P(a.P)
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [{"ox": k[0], "oz": k[1], "G": k[2], "tx": v[0], "tz": v[1]} for k, v in sorted(sigs.items())]
    (OUT / f"sigs_P{a.P}.json").write_text(json.dumps(rows))
    nox = len({k[0] for k in sigs})
    print(json.dumps({"P": a.P, "legal_time_vectors": nlegal, "signatures": len(sigs), "distinct_sigmaX": nox}))


if __name__ == "__main__":
    main()
