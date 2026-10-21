"""Auditor's independent library for the E-032 audit (no import of search/ or evaluators/ code).

- gross code [[144,12,12]] from scratch: l=12, m=6, A = x^3 + y + y^2, B = y^3 + x + x^2 (2308.07915 Table 3),
  x = S_l (x) I_m, y = I_l (x) S_m, HX = [A|B], HZ = [B^T|A^T].
- own GF(2) logicals.
- own unroll of a qec-schedule/v1 JSON following the template rules written in the evaluator's module docstring
  (cyclic offsets from prep, per-check earliest start for a global shift sigma, the sigma with fewest layers,
  ties -> smallest sigma), WRAPPING allowed; own SD6 insertion; optional "image" observables (rows of H and L on
  the final data readout) so every DEM term carries its residual-data image.
"""
from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import stim

L_, M_ = 12, 6
N2 = L_ * M_
N = 2 * N2


def shift(n, k):
    S = np.zeros((n, n), np.uint8)
    for i in range(n):
        S[i, (i + k) % n] = 1
    return S


def mono(a, b):
    return np.kron(shift(L_, a), shift(M_, b)) % 2


def gross():
    A = (mono(3, 0) + mono(0, 1) + mono(0, 2)) % 2
    B = (mono(0, 3) + mono(1, 0) + mono(2, 0)) % 2
    HX = np.concatenate([A, B], 1) % 2
    HZ = np.concatenate([B.T, A.T], 1) % 2
    assert not ((HX.astype(int) @ HZ.T.astype(int)) % 2).any()
    return HX.astype(np.uint8), HZ.astype(np.uint8), A, B


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
    K = kernel(Hker)
    base = [np.array(r, np.uint8) for r in rref(Hrow)[0]]
    r0 = len(base)
    out = []
    for v in K:
        if rank(np.array(base + [v])) > r0:
            base.append(v)
            r0 += 1
            out.append(v)
    return np.array(out, np.uint8)


@lru_cache(maxsize=None)
def code():
    HX, HZ, A, B = gross()
    LX = logicals(HZ, HX)
    LZ = logicals(HX, HZ)
    return HX, HZ, LX, LZ


def translation(a, b):
    """data permutation of the translation x^a y^b (column i of L block -> p[i])."""
    p = np.array([((i // M_ + a) % L_) * M_ + (i % M_ + b) % M_ for i in range(N2)])
    return np.concatenate([p, p + N2]), p


# ---------------------------------------------------------------- circuit

def load_spec(path):
    d = json.load(open(path))
    assert d["format"] == "qec-schedule/v1"
    return d


def my_unroll(spec, R):
    """returns D, start{(typ,i)}, info{(typ,i): (dm, [(off, col)])}, n_layers (excluding readout)."""
    D = spec["period"]
    info = {}
    for typ in ("X", "Z"):
        for i, c in enumerate(spec[typ.lower() + "_checks"]):
            dm = (c["meas"] - c["prep"]) % D
            offs = sorted(((t - c["prep"]) % D, a) for a, t in c["cnots"])
            assert dm > 0 and all(0 < o < dm for o, _ in offs) and len({o for o, _ in offs}) == len(offs)
            info[(typ, i)] = (c["prep"], dm, offs)
    best = None
    for sg in range(D):
        st = {}
        for k, (tp, dm, offs) in info.items():
            s = (sg + tp) % D          # earliest start >= 0 congruent to sigma + prep (mod D)
            if s + offs[0][0] < 1:
                s += D
            st[k] = s
        end = max(st[k] + D * (R - 1) + info[k][1] for k in info)
        if best is None or end < best[0]:
            best = (end, sg, st)
    end, sg, st = best
    return D, st, {k: (v[1], v[2]) for k, v in info.items()}, end + 1, sg


def memory_circuit(spec, basis, R, p=1e-3, noise=True, image_obs=False, Lover=None):
    HX, HZ, LX, LZ = code()
    if Lover is not None:
        LX, LZ = (Lover, LZ) if basis == "X" else (LX, Lover)
    D, st, info, nl, _ = my_unroll(spec, R)
    xa = {i: N + i for i in range(N2)}
    za = {i: N + N2 + i for i in range(N2)}
    qof = lambda k: xa[k[1]] if k[0] == "X" else za[k[1]]
    ops = {}
    for k, (dm, offs) in info.items():
        q = qof(k)
        for j in range(R):
            s = st[k] + D * j
            ops.setdefault(s, []).append(("RX" if k[0] == "X" else "R", q, None))
            for o, a in offs:
                ops.setdefault(s + o, []).append(("CX", (q, a) if k[0] == "X" else (a, q), None))
            ops.setdefault(s + dm, []).append(("MX" if k[0] == "X" else "M", q, j))
    nq = N + 2 * N2
    allq = set(range(nq))
    circ = stim.Circuit()
    rec, nm = {}, 0
    flip = {"R": "X_ERROR", "M": "X_ERROR", "RX": "Z_ERROR", "MX": "Z_ERROR"}
    for t in range(nl):
        touched = []
        lay = ops.get(t, [])
        if t == 0:
            g = "R" if basis == "Z" else "RX"
            circ.append(g, list(range(N)))
            if noise:
                circ.append(flip[g], list(range(N)), p)
            touched += list(range(N))
        for g in ("RX", "R"):
            qs = sorted(q for kk, q, _ in lay if kk == g)
            if qs:
                circ.append(g, qs)
                if noise:
                    circ.append(flip[g], qs, p)
                touched += qs
        cx = sorted(q for kk, q, _ in lay if kk == "CX")
        if cx:
            flat = [x for pr in cx for x in pr]
            circ.append("CX", flat)
            if noise:
                circ.append("DEPOLARIZE2", flat, p)
            touched += flat
        for g in ("M", "MX"):
            ms = sorted((q, j) for kk, q, j in lay if kk == g)
            if ms:
                if noise:
                    circ.append(flip[g], [q for q, _ in ms], p)
                circ.append(g, [q for q, _ in ms])
                for q, j in ms:
                    rec[(q, j)] = nm
                    nm += 1
                touched += [q for q, _ in ms]
        assert len(touched) == len(set(touched)), ("qubit used twice", t)
        idle = sorted(allq - set(touched))
        if noise and idle:
            circ.append("DEPOLARIZE1", idle, p)
        circ.append("TICK")
    g = "M" if basis == "Z" else "MX"
    if noise:
        circ.append(flip[g], list(range(N)), p)
        circ.append("DEPOLARIZE1", list(range(N, nq)), p)
    circ.append(g, list(range(N)))
    drec = {q: nm + q for q in range(N)}
    nm += N
    H, Lg = (HZ, LZ) if basis == "Z" else (HX, LX)
    anc = za if basis == "Z" else xa
    for j in range(R):
        for i in range(N2):
            q = anc[i]
            tg = [stim.target_rec(rec[(q, j)] - nm)]
            if j:
                tg.append(stim.target_rec(rec[(q, j - 1)] - nm))
            circ.append("DETECTOR", tg, [i, j])
    for i in range(N2):
        tg = [stim.target_rec(drec[c] - nm) for c in np.nonzero(H[i])[0]]
        tg.append(stim.target_rec(rec[(anc[i], R - 1)] - nm))
        circ.append("DETECTOR", tg, [i, R])
    k0 = Lg.shape[0]
    for k, row in enumerate(Lg):
        circ.append("OBSERVABLE_INCLUDE", [stim.target_rec(drec[c] - nm) for c in np.nonzero(row)[0]], k)
    if image_obs:
        for r_i, row in enumerate(list(H) + list(Lg)):
            circ.append("OBSERVABLE_INCLUDE", [stim.target_rec(drec[c] - nm) for c in np.nonzero(row)[0]], k0 + r_i)
    return circ


def dem_terms(circ):
    """list of (detector bitmask int, observable bitmask int) for each DEM error term (dedup kept as list)."""
    dem = circ.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    out = []
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        d = o = 0
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                d ^= 1 << t.val
            elif t.is_logical_observable_id():
                o ^= 1 << t.val
        out.append((d, o))
    return out, dem.num_detectors, dem.num_observables
