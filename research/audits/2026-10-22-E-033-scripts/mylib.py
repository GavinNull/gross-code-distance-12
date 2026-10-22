"""Auditor E-033: E-030 auditor library adapted to gross [[144,12,12]] (l=12, m=6, A = x^3+y+y^2, B = y^3+x+x^2, 2308.07915) (no import of search/ or evaluators/ code).

- [[90,8,10]] BB code from scratch (2308.07915 Table 3): l=15, m=3, A = x^9 + y + y^2, B = 1 + x^2 + x^7,
  x = S_15 (x) I_3, y = I_15 (x) S_3, HX = [A|B], HZ = [B^T|A^T].  Own GF(2) logicals.
- Own memory-circuit encoder for qec-schedule/v1 specs, INCLUDING wrapping checks (prep after meas mod period):
  instance of check q in round j: reset at s_q + jD, CNOT at s_q + jD + ((t - prep) mod D), measure at
  s_q + jD + ((meas - prep) mod D).  Start rule: common shift sigma in [0, D), s_q = (prep_q + sigma) mod D,
  plus D if its first CNOT would be at layer 0 (layer 0 = data reset); sigma minimises the last measurement layer.
  Data reset in layer 0; final data readout in its own last layer.  Own qubit layout: data 0..89, X anc 90..134,
  Z anc 135..179.  Local detectors (memory-basis checks only): m(c,0); m(c,j)^m(c,j-1); H_c.readout ^ m(c,R-1).
- Own SD6-lambda noise: R -> X_ERROR(p) after, RX -> Z_ERROR(p) after, CX -> DEPOLARIZE2(p) after,
  M -> X_ERROR(p) before, MX -> Z_ERROR(p) before, every qubit of the circuit not acted on in a layer ->
  DEPOLARIZE1(lam*p) (omitted for lam = 0).
"""
from __future__ import annotations

import json

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


def bb_code():
    A = (mono(3, 0) + mono(0, 1) + mono(0, 2)) % 2
    B = (mono(0, 3) + mono(1, 0) + mono(2, 0)) % 2
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


def nullspace(M):
    M = np.array(M, np.uint8) % 2
    R_, piv = rref(M)
    n = M.shape[1]
    free = [c for c in range(n) if c not in piv]
    out = []
    for f in free:
        v = np.zeros(n, np.uint8); v[f] = 1
        for i, pc in enumerate(piv):
            if R_[i, f]:
                v[pc] = 1
        out.append(v)
    return np.array(out, np.uint8)


def logicals(Hcomm, Hstab):
    """basis of ker(Hcomm) modulo rowspace(Hstab): independent representatives."""
    K = nullspace(Hcomm)
    base = rank(Hstab)
    cur = np.array(Hstab, np.uint8) % 2
    out = []
    for v in K:
        t = np.vstack([cur, v])
        if rank(t) > base + len(out):
            out.append(v); cur = t
    return np.array(out, np.uint8)


def code_with_logicals():
    HX, HZ = bb_code()
    LZ = logicals(HX, HZ)   # Z-type logicals: commute with X checks
    LX = logicals(HZ, HX)
    assert LZ.shape[0] == LX.shape[0] == 12
    return HX, HZ, LX, LZ


QX0, QZ0 = N, N + N2          # own layout


def load_spec(path):
    d = json.load(open(path))
    return d


def unroll(d, R):
    D = d["period"]
    HX, HZ = bb_code()
    info = {}
    for typ, key, H, q0 in (("X", "x_checks", HX, QX0), ("Z", "z_checks", HZ, QZ0)):
        assert len(d[key]) == N2
        for i, c in enumerate(d[key]):
            assert sorted(q for q, _ in c["cnots"]) == sorted(np.flatnonzero(H[i]).tolist()), (typ, i)
            dm = (c["meas"] - c["prep"]) % D
            offs = sorted(((t - c["prep"]) % D, q) for q, t in c["cnots"])
            assert 0 < offs[0][0] and offs[-1][0] < dm <= D - 1 and len({o for o, _ in offs}) == 6, (typ, i)
            info[q0 + i] = (typ, c["prep"], dm, offs)
    best = None
    for sigma in range(D):
        st = {}
        for q, (_, pr, dm, offs) in info.items():
            s = (pr + sigma) % D
            if s + offs[0][0] < 1:
                s += D
            st[q] = s
        end = max(st[q] + D * (R - 1) + info[q][2] for q in info)
        if best is None or end < best[0]:
            best = (end, st)
    end, st = best
    layers = [dict(R=[], RX=[], CX=[], M=[], MX=[]) for _ in range(end + 1)]
    meas_at = {}
    for q, (typ, _, dm, offs) in info.items():
        for j in range(R):
            s = st[q] + D * j
            layers[s]["RX" if typ == "X" else "R"].append(q)
            for o, dq in offs:
                layers[s + o]["CX"].append((q, dq) if typ == "X" else (dq, q))
            layers[s + dm]["MX" if typ == "X" else "M"].append(q)
            meas_at[(q, j)] = s + dm
    for t, L in enumerate(layers):
        used = L["R"] + L["RX"] + [a for pr in L["CX"] for a in pr] + L["M"] + L["MX"]
        if t == 0:
            used = used + list(range(N))
        assert len(used) == len(set(used)), f"layer {t}: qubit used twice"
    return layers, st, info, meas_at


def memory_circuit(d, basis, R, p=0.0, lam=1.0, image_obs=False, inject=None):
    """own circuit; p = 0 -> noiseless.  image_obs: extra observables = rows of H_basis and L_basis on the final
    data readout (indices 8.. after the 8 logical observables).  inject: list of data qubits to flip right after
    the data reset (X for basis Z, Z for basis X), as a deterministic fault."""
    HX, HZ, LX, LZ = code_with_logicals()
    H, Lg = (HZ, LZ) if basis == "Z" else (HX, LX)
    layers, st, info, meas_at = unroll(d, R)
    allq = list(range(N + 2 * N2))
    c = stim.Circuit()
    rec = {}
    nm = 0
    for t, L in enumerate(layers):
        touched = set()
        resets = [("R" if basis == "Z" else "RX", list(range(N)))] if t == 0 else []
        resets += [(g, L[g]) for g in ("RX", "R") if L[g]]
        for g, qs in resets:
            c.append(g, sorted(qs)); touched.update(qs)
            if p > 0:
                c.append("Z_ERROR" if g == "RX" else "X_ERROR", sorted(qs), p)
        if t == 0 and inject:
            c.append("X_ERROR" if basis == "Z" else "Z_ERROR", sorted(inject), 1.0)
        if L["CX"]:
            prs = sorted(L["CX"])
            c.append("CX", [a for pr in prs for a in pr])
            for pr in prs:
                touched.update(pr)
            if p > 0:
                c.append("DEPOLARIZE2", [a for pr in prs for a in pr], p)
        for g, fl in (("M", "X_ERROR"), ("MX", "Z_ERROR")):
            qs = sorted(L[g])
            if qs:
                touched.update(qs)
                if p > 0:
                    c.append(fl, qs, p)
                c.append(g, qs)
                for q in qs:
                    rec[q] = rec.get(q, []) + [nm]; nm += 1
        idle = [q for q in allq if q not in touched]
        if p > 0 and lam > 0 and idle:
            c.append("DEPOLARIZE1", idle, lam * p)
        c.append("TICK")
    # final readout layer (data only measured; ancillas idle -- irrelevant, no later measurement)
    g = "M" if basis == "Z" else "MX"
    if p > 0:
        c.append("X_ERROR" if basis == "Z" else "Z_ERROR", list(range(N)), p)
    c.append(g, list(range(N)))
    data = {q: nm + q for q in range(N)}
    nm += N
    q0 = QZ0 if basis == "Z" else QX0
    tg = lambda a: stim.target_rec(a - nm)
    for j in range(R):
        for i in range(N2):
            r = rec[q0 + i]
            assert len(r) == R
            c.append("DETECTOR", [tg(r[j])] + ([tg(r[j - 1])] if j else []), [i, j])
    for i in range(N2):
        c.append("DETECTOR", [tg(data[x]) for x in np.flatnonzero(H[i])] + [tg(rec[q0 + i][R - 1])], [i, R])
    for k in range(Lg.shape[0]):
        c.append("OBSERVABLE_INCLUDE", [tg(data[x]) for x in np.flatnonzero(Lg[k])], k)
    if image_obs:
        rows = list(H) + list(Lg)
        for k, row in enumerate(rows):
            c.append("OBSERVABLE_INCLUDE", [tg(data[x]) for x in np.flatnonzero(row)], Lg.shape[0] + k)
    return c


def dem_terms(circ):
    """list of (detector bitmask int, observable bitmask int, prob) for each DEM error (no decomposition)."""
    dem = circ.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    out = []
    for ins in dem.flattened():
        if ins.type != "error":
            continue
        dm, om = 0, 0
        for t in ins.targets_copy():
            if t.is_relative_detector_id():
                dm ^= 1 << t.val
            elif t.is_logical_observable_id():
                om ^= 1 << t.val
        out.append((dm, om, ins.args_copy()[0]))
    return out, dem.num_detectors, dem.num_observables
