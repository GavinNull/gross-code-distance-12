"""Theory A: own enumeration of translation-invariant schedules T(P) and their signatures (pi_X, pi_Z, G), and the
flat-hook necessary conditions (Lemma F of the note).  Independent of search/experiments/e040.

Class T(P) (same as E-040): tx[label], tz[label] absolute CNOT times (labels A1 A2 A3 B1 B2 B3), each side distinct,
span <= P-3; L data qubits: tx[A*], tz[B*] distinct mod P; R data qubits: tx[B*], tz[A*] distinct mod P;
determinism: floor((tx[Ak]-tz[Bl])/P) == floor((tx[Bl]-tz[Ak])/P) for all k, l.  G[k][l] := that floor.

    uv run python search/theory/A/sigs.py --P 8 --code bb90
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from collections import Counter

import numpy as np

A, B = (0, 1, 2), (3, 4, 5)
LAB = ["A1", "A2", "A3", "B1", "B2", "B3"]


def side_configs(P):
    out = []
    for S in itertools.combinations(range(1, P - 2), 5):
        for perm in itertools.permutations((0,) + S):
            out.append(perm)
    return np.array(out, dtype=np.int64)


def Eset(S):
    """E(S) = {(k,l): [A_k in S] xor [B_l in S]} as flat indices 3k+l."""
    return [3 * k + l for k in range(3) for l in range(3) if (A[k] in S) != (B[l] in S)]


def cost(Gflat, S):
    """min over v of sum_{e in E(S)} |G(e) - v|  (0 iff flat)."""
    v = Gflat[:, Eset(S)]
    lo, hi = v.min(axis=1), v.max(axis=1)
    best = None
    for c in range(int(lo.min()), int(hi.max()) + 1):
        s = np.abs(v - c).sum(axis=1)
        best = s if best is None else np.minimum(best, s)
    return best


def enumerate_sigs(P):
    X = side_configs(P)
    sigs = {}
    nlegal = 0
    for tx in X:
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
                    gr = np.floor_divide(tx[B[l]] - TZ[:, A[k]], P)
                    m &= gl == gr
                    G[:, 3 * k + l] = gl
            if not m.any():
                continue
            nlegal += int(m.sum())
            Z, G = TZ[m], G[m]
            G = G - G.min(axis=1, keepdims=True)
            ox = tuple(int(v) for v in np.argsort(tx))
            oz = np.argsort(Z, axis=1)
            for i in range(len(Z)):
                key = (ox, tuple(int(v) for v in oz[i]), tuple(int(v) for v in G[i]))
                if key not in sigs:
                    sigs[key] = (tuple(int(v) for v in tx), tuple(int(v) for v in Z[i]))
    return nlegal, sigs


def hooks(order):
    """the three hook sets of an order (up to complement): last pair S2, first pair (~ S4), last triple (~ S3)."""
    return {"S2": frozenset(order[4:]), "P2": frozenset(order[:2]), "T3": frozenset(order[3:])}


def required(pairs_json, d):
    """from the (iii) table: which term subsets lie in a logical of weight d (pair -> config weight d-1;
    triple -> d-2) or d+1 (triple -> d-1)."""
    R = json.load(open(pairs_json))
    out = {}
    for key, v in R.items():
        S = frozenset(LAB.index(key[i:i + 2]) for i in range(0, len(key), 2))
        if v.get(str(d)) == "found":
            out[S] = d
        elif v.get(str(d + 1)) == "found":
            out[S] = d + 1
    return out


def config_weight(S, req, d):
    """weight of the cheapest flat-hook configuration (hook S + data) we have a witness for, or None.
    Uses S and its complement (same image)."""
    best = None
    for T in (S, frozenset(range(6)) - S):
        if T in req:
            w = 1 + req[T] - len(T)
            best = w if best is None else min(best, w)
    return best
