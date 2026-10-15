"""Auditor's independent library for E-028 (no import of search/ or evaluators/ code).

- BB code [[90,8,10]] built from scratch: l=15, m=3, A = x^9 + y + y^2, B = 1 + x^2 + x^7 (2308.07915 Table 3),
  x = S_l (x) I_m, y = I_l (x) S_m, HX = [A|B], HZ = [B^T|A^T].
- GF(2) linear algebra, logical operators.
- Own memory-circuit encoder from a qec-schedule/v1 JSON (only for the simple, non-wrapping case
  prep < cnots < meas inside one period, checked), own SD6 noise insertion.
"""
from __future__ import annotations

import json

import numpy as np
import stim

L_, M_ = 15, 3
N2 = L_ * M_
N = 2 * N2


def shift(n, k):
    S = np.zeros((n, n), np.uint8)
    for i in range(n):
        S[i, (i + k) % n] = 1
    return S


def mono(a, b):
    return np.kron(shift(L_, a), shift(M_, b)) % 2


def bb_code():
    A = (mono(9, 0) + mono(0, 1) + mono(0, 2)) % 2
    B = (mono(0, 0) + mono(2, 0) + mono(7, 0)) % 2
    HX = np.concatenate([A, B], 1) % 2
    HZ = np.concatenate([B.T, A.T], 1) % 2
    assert not ((HX.astype(int) @ HZ.T.astype(int)) % 2).any()
    return HX.astype(np.uint8), HZ.astype(np.uint8)


def rref(M):
    M = (np.array(M, np.uint8) % 2).copy()
    r, piv = 0, []
    for c in range(M.shape[1]):
        p = next((i for i in range(r, M.shape[0]) if M[i, c]), None)
        if p is None:
            continue
        M[[r, p]] = M[[p, r]]
        for i in range(M.shape[0]):
            if i != r and M[i, c]:
                M[i] ^= M[r]
        piv.append(c)
        r += 1
        if r == M.shape[0]:
            break
    return M[:r], piv


def rank(M):
    return len(rref(M)[1])


def kernel(M):
    R, piv = rref(M)
    n = M.shape[1]
    free = [c for c in range(n) if c not in piv]
    out = []
    for f in free:
        v = np.zeros(n, np.uint8)
        v[f] = 1
        for i, c in enumerate(piv):
            v[c] = R[i, f]
        out.append(v)
    return np.array(out, np.uint8)


def logicals(Hker, Hrow):
    """basis of ker(Hker) modulo rowspace(Hrow)."""
    K = kernel(Hker)
    base = list(Hrow)
    r0 = rank(np.array(base))
    out = []
    for v in K:
        if rank(np.array(base + [v])) > r0:
            base.append(v)
            r0 += 1
            out.append(v)
    return np.array(out, np.uint8)


def code_with_logicals():
    HX, HZ = bb_code()
    LX = logicals(HZ, HX)    # X logicals: commute with Z checks, not X stabilisers
    LZ = logicals(HX, HZ)
    return HX, HZ, LX, LZ


# ---------------------------------------------------------------- circuit

def load_spec(path):
    d = json.load(open(path))
    assert d["format"] == "qec-schedule/v1"
    return d


def memory_circuit(spec, basis, R, p=1e-3, noise=True):
    """Own encoder.  Layout: data 0..89, X anc 90..134, Z anc 135..179.  Layer 16j+t holds the period-t operations of
    round j (requires prep < cnot times < meas for every check, i.e. a non-wrapping frame); data reset at layer 0;
    a final layer measures the data.  SD6: reset flip p, DEPOLARIZE2 p after CX, pre-measurement flip p, DEPOLARIZE1 p on
    every qubit not acted on in a layer."""
    HX, HZ, LX, LZ = code_with_logicals()
    D = spec["period"]
    ops = {}   # t -> list of (kind, payload)
    for typ, chk, H, off in (("X", spec["x_checks"], HX, N), ("Z", spec["z_checks"], HZ, N + N2)):
        assert len(chk) == N2
        for i, c in enumerate(chk):
            q = off + i
            cols = sorted(a for a, _ in c["cnots"])
            assert cols == sorted(np.nonzero(H[i])[0].tolist()), (typ, i)
            ts = [t for _, t in c["cnots"]]
            assert len(set(ts)) == 6 and c["prep"] < min(ts) and max(ts) < c["meas"] < D, "wrapping frame"
            ops.setdefault(c["prep"], []).append(("RX" if typ == "X" else "R", q))
            for a, t in c["cnots"]:
                ops.setdefault(t, []).append(("CX", (q, a) if typ == "X" else (a, q)))
            ops.setdefault(c["meas"], []).append(("MX" if typ == "X" else "M", q))
    nq = N + 2 * N2
    allq = set(range(nq))
    circ = stim.Circuit()
    rec = {}
    nm = 0
    flip = {"R": "X_ERROR", "M": "X_ERROR", "RX": "Z_ERROR", "MX": "Z_ERROR"}
    T = D * R
    for t in range(T):
        j, tt = divmod(t, D)
        touched = []
        if t == 0:
            g = "R" if basis == "Z" else "RX"
            circ.append(g, list(range(N)))
            if noise:
                circ.append(flip[g], list(range(N)), p)
            touched += list(range(N))
        lay = ops.get(tt, [])
        for g in ("R", "RX"):
            qs = sorted(q for k, q in lay if k == g)
            if qs:
                circ.append(g, qs)
                if noise:
                    circ.append(flip[g], qs, p)
                touched += qs
        cx = sorted(pr for k, pr in lay if k == "CX")
        if cx:
            flat = [x for pr in cx for x in pr]
            circ.append("CX", flat)
            if noise:
                circ.append("DEPOLARIZE2", flat, p)
            touched += flat
        for g in ("M", "MX"):
            qs = sorted(q for k, q in lay if k == g)
            if qs:
                if noise:
                    circ.append(flip[g], qs, p)
                circ.append(g, qs)
                for q in qs:
                    rec[(q, j)] = nm
                    nm += 1
                touched += qs
        assert len(touched) == len(set(touched)), t
        idle = sorted(allq - set(touched))
        if noise and idle:
            circ.append("DEPOLARIZE1", idle, p)
        circ.append("TICK")
    # final layer
    g = "M" if basis == "Z" else "MX"
    if noise:
        circ.append(flip[g], list(range(N)), p)
        circ.append("DEPOLARIZE1", list(range(N, nq)), p)
    circ.append(g, list(range(N)))
    drec = {q: nm + q for q in range(N)}
    nm += N
    H, Lg = (HZ, LZ) if basis == "Z" else (HX, LX)
    off = N + N2 if basis == "Z" else N
    for j in range(R):
        for i in range(N2):
            q = off + i
            tg = [stim.target_rec(rec[(q, j)] - nm)]
            if j:
                tg.append(stim.target_rec(rec[(q, j - 1)] - nm))
            circ.append("DETECTOR", tg, [i, j])
    for i in range(N2):
        tg = [stim.target_rec(drec[c] - nm) for c in np.nonzero(H[i])[0]]
        tg.append(stim.target_rec(rec[(off + i, R - 1)] - nm))
        circ.append("DETECTOR", tg, [i, R])
    for k, row in enumerate(Lg):
        circ.append("OBSERVABLE_INCLUDE", [stim.target_rec(drec[c] - nm) for c in np.nonzero(row)[0]], k)
    return circ


def dem_matrix(circ):
    """distinct DEM error columns: list of (frozenset detectors, frozenset observables)."""
    dem = circ.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    cols = []
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        d, o = set(), set()
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                d ^= {t.val}
            elif t.is_logical_observable_id():
                o ^= {t.val}
        if d or o:
            cols.append((frozenset(d), frozenset(o)))
    return cols, dem.num_detectors, dem.num_observables
