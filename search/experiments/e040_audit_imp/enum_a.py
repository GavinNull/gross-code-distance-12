"""E-040 impossibility audit (independent code): enumerate every legal T(P) schedule in the canonical form
   min tX = 0,   0 <= tX[A1] - tZ[B1] <= P-1      (labels 0..5 = A1 A2 A3 B1 B2 B3)
Legality (class T(P)): per side the 6 CNOT times distinct, span <= P-3; on every data qubit the six CNOT times distinct
mod P (left qubit: X A_i with Z B_j; right qubit: X B_j with Z A_i); determinism
floor((tX[A_i]-tZ[B_j])/P) == floor((tX[B_j]-tZ[A_i])/P) for all i, j.
Every legal circuit (absolute times up to global shift and independent relabelling of X / Z instances) has exactly one
canonical representative: shift so min tX = 0 (X relabel = shift by P, absorbed), then relabel Z instances (tZ += kP)
-- exactly one k puts tX[A1]-tZ[B1] in [0, P-1].
Writes results/E-040-audit-imp/canon_P{P}.npz (TX, TZ int8) and prints counts:
   vectors, signatures (ox, oz, raw G), signatures with G normalised to min 0.
   uv run python -m search.experiments.e040_audit_imp.enum_a 8
"""
import itertools
import json
import sys
from pathlib import Path

import numpy as np

OUT = Path("results/E-040-audit-imp")


def side(P):
    """all (6,) vectors of distinct times with min 0 and max <= P-3."""
    out = []
    for vals in itertools.combinations(range(P - 2), 6):
        if vals[0] != 0:
            continue
        out.extend(itertools.permutations(vals))
    return np.array(out, dtype=np.int64)


def legal(tx, TZ, P):
    n = len(TZ)
    ok = np.ones(n, bool)
    for i in range(3):          # A_i
        for j in range(3):      # B_j
            # left qubit: X A_i vs Z B_j ; right qubit: X B_j vs Z A_i  -- distinct mod P
            ok &= (tx[i] - TZ[:, 3 + j]) % P != 0
            ok &= (tx[3 + j] - TZ[:, i]) % P != 0
            ok &= np.floor_divide(tx[i] - TZ[:, 3 + j], P) == np.floor_divide(tx[3 + j] - TZ[:, i], P)
    return ok


def run(P):
    S = side(P)
    TXs, TZs = [], []
    for tx in S:
        # Z vectors: S + shift, with tZ[B1] in [tX[A1]-P+1, tX[A1]]
        lo = tx[0] - P + 1 - S[:, 3]
        cand = np.concatenate([S + (lo + d)[:, None] for d in range(P)])
        m = legal(tx, cand, P)
        z = cand[m]
        TZs.append(z)
        TXs.append(np.broadcast_to(tx, z.shape))
    TX = np.concatenate(TXs).astype(np.int8)
    TZ = np.concatenate(TZs).astype(np.int8)
    return TX, TZ


PERM = {p: i for i, p in enumerate(itertools.permutations(range(6)))}


def sig_keys(TX, TZ, P, norm=False):
    TX = TX.astype(np.int64)
    TZ = TZ.astype(np.int64)
    ox = np.argsort(TX, axis=1)
    oz = np.argsort(TZ, axis=1)
    pw = 6 ** np.arange(6)
    # order code (injective on permutations)
    kx = (ox * pw).sum(1)
    kz = (oz * pw).sum(1)
    G = np.stack([np.floor_divide(TX[:, i] - TZ[:, 3 + j], P) for i in range(3) for j in range(3)], 1)
    if norm:
        G = G - G.min(1, keepdims=True)
    kg = ((G + 4) * (9 ** np.arange(9))).sum(1)
    return (kx * 6 ** 6 + kz) * 9 ** 9 + kg


def main():
    P = int(sys.argv[1])
    OUT.mkdir(parents=True, exist_ok=True)
    TX, TZ = run(P)
    np.savez_compressed(OUT / f"canon_P{P}.npz", TX=TX, TZ=TZ)
    k = sig_keys(TX, TZ, P)
    kn = sig_keys(TX, TZ, P, norm=True)
    print(json.dumps({"P": P, "vectors": len(TX), "signatures_rawG": int(len(np.unique(k))),
                      "signatures_normG": int(len(np.unique(kn)))}))


if __name__ == "__main__":
    main()
