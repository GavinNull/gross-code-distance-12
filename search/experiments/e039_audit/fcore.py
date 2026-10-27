"""E-039 audit (fresh auditor, 2026-10-27): own finite-R core for the non-wrapping class N(S).
Imports nothing from search/experiments/e039 or e038.  Only the term-index convention (term a of check k touches data
qubit support(k)[a]) and the list of the 14 measured checks are taken from e036_audit.core, so that schedules written
as tau[(k, a)] mean the same thing as in E-039.

Schedule: tau[(k, a)] in 1..S = CNOT layer of check k's term a.  Round j occupies layers jP .. jP + S + 1, P = S + 2:
ancilla prep at jP (round 0: together with the data reset), CNOTs at jP + tau, measurement at jP + S + 1.  After the
last round one extra layer with the final data readout (evaluator template).

Circuit (own SD6): DEPOLARIZE2(p) after each CX; DEPOLARIZE1(p) on every qubit not acted on in a layer; reset flip
after every reset (data and ancilla); measurement flip (M(p) / MX(p)) on every measurement incl. the final readout.
Detectors only for the 14 measured checks of the memory basis (evaluator convention): reset ancilla
D(c,0) = m0, D(c,j) = m_j ^ m_{j-1}, D(c,R) = final parity ^ m_{R-1}; no-reset ancilla: m_j = s_j ^ m_{j-1}, so
D(c,j) = m_j ^ m_{j-2} and D(c,R) = final parity ^ m_{R-1} ^ m_{R-2}.  Observables: a basis of the logicals of the
memory basis (own GF(2)).  Injection: X_ERROR(1)/Z_ERROR(1) at (layer, 'pre'|'post', qubit).
"""
from __future__ import annotations

import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np
import stim

from search.experiments.e036_audit.core import checks as _checks, support as _support

KS = _checks("bb18")
SUPP = {k: list(_support(k)) for k in KS}
ND = 18


def gf2_rref(M):
    M = (np.array(M, np.uint8) % 2).copy()
    r = 0
    piv = []
    for c in range(M.shape[1]):
        rows = [i for i in range(r, M.shape[0]) if M[i, c]]
        if not rows:
            continue
        M[[r, rows[0]]] = M[[rows[0], r]]
        for i in range(M.shape[0]):
            if i != r and M[i, c]:
                M[i] ^= M[r]
        piv.append(c)
        r += 1
    return M[:r], piv


def rank(M):
    return len(gf2_rref(M)[1]) if len(M) else 0


def hmat(t):
    rows = []
    for k in KS:
        if k[0] == t:
            v = np.zeros(ND, np.uint8)
            v[SUPP[k]] = 1
            rows.append(v)
    return np.array(rows)


def kernel(M):
    R, piv = gf2_rref(M)
    free = [c for c in range(M.shape[1]) if c not in piv]
    out = []
    for f in free:
        v = np.zeros(M.shape[1], np.uint8)
        v[f] = 1
        for i, c in enumerate(piv):
            if R[i, f]:
                v[c] = 1
        out.append(v)
    return np.array(out)


def logicals(basis):
    """basis-type logicals (Z logicals for Z memory): ker(H_other) modulo rowspace(H_basis); returns list of vectors."""
    Hb = hmat(basis)
    Ho = hmat("X" if basis == "Z" else "Z")
    K = kernel(Ho)
    out = []
    cur = list(Hb)
    for v in K:
        if rank(np.array(cur + [v])) > rank(np.array(cur)):
            cur.append(v)
            out.append(v)
    return out


def is_logical_residual(e, basis):
    """e: 0/1 vector of the relevant Pauli (X for Z memory).  True iff commutes with all measured readers and is not a
    product of measured spreaders... i.e. a non-trivial logical."""
    Hb = hmat(basis)
    if (Hb @ e % 2).any():
        return False
    Ho = hmat("X" if basis == "Z" else "Z")
    return rank(np.vstack([Ho, e])) > rank(Ho)


def circuit(tau, S, basis, R, p=0.0, reset=True, inject=()):
    P = S + 2
    anc = {k: ND + i for i, k in enumerate(KS)}
    nq = ND + len(KS)
    inj = {}
    for (layer, when, q, pa) in inject:
        inj.setdefault((layer, when), []).append((q, pa))
    T = R * P + 1           # layers 0..R*P-1 rounds, layer R*P = final readout
    c = stim.Circuit()
    rec = {}
    nm = 0

    def do_inj(layer, when):
        for q, pa in inj.get((layer, when), []):
            c.append("X_ERROR" if pa == "X" else "Z_ERROR", [q], 1.0)

    for t in range(T):
        do_inj(t, "pre")
        used = set()
        if t == R * P:
            # final readout
            c.append("M" if basis == "Z" else "MX", list(range(ND)), p)
            for q in range(ND):
                rec[("D", q)] = nm
                nm += 1
            do_inj(t, "post")
            break
        j, l = divmod(t, P)
        if t == 0:
            c.append("R" if basis == "Z" else "RX", list(range(ND)))
            if p:
                c.append("X_ERROR" if basis == "Z" else "Z_ERROR", list(range(ND)), p)
            used |= set(range(ND))
        if l == 0 and (reset or j == 0):
            for typ in "XZ":
                qs = [anc[k] for k in KS if k[0] == typ]
                c.append("RX" if typ == "X" else "R", qs)
                if p:
                    c.append("Z_ERROR" if typ == "X" else "X_ERROR", qs, p)
                used |= set(qs)
        if 1 <= l <= S:
            pairs = []
            for k in KS:
                for a in range(6):
                    if tau[(k, a)] == l:
                        q = SUPP[k][a]
                        assert q not in used and anc[k] not in used, ("clash", t, k, a)
                        pairs += [anc[k], q] if k[0] == "X" else [q, anc[k]]
                        used |= {q, anc[k]}
            if pairs:
                c.append("CX", pairs)
                if p:
                    c.append("DEPOLARIZE2", pairs, p)
        if l == S + 1:
            for typ in "XZ":
                ks = [k for k in KS if k[0] == typ]
                c.append("MX" if typ == "X" else "M", [anc[k] for k in ks], p)
                for k in ks:
                    rec[(k, j)] = nm
                    nm += 1
                used |= {anc[k] for k in ks}
        if p:
            idle = [q for q in range(nq) if q not in used]
            if idle:
                c.append("DEPOLARIZE1", idle, p)
        do_inj(t, "post")
        c.append("TICK")
    dmap = {}
    nd = 0
    readers = [k for k in KS if k[0] == basis]

    def m(key):
        return stim.target_rec(rec[key] - nm)
    for j in range(R):
        for k in readers:
            tg = [m((k, j))]
            if reset and j >= 1:
                tg.append(m((k, j - 1)))
            if not reset and j >= 2:       # m_j = s_j ^ m_{j-1}  ->  s_j ^ s_{j-1} = m_j ^ m_{j-2}; D1 = m1
                tg.append(m((k, j - 2)))
            c.append("DETECTOR", [x for x in tg])
            dmap[(k, j)] = nd
            nd += 1
    for k in readers:
        tg = [m(("D", q)) for q in SUPP[k]] + [m((k, R - 1))]
        if not reset and R >= 2:
            tg.append(m((k, R - 2)))
        c.append("DETECTOR", tg)
        dmap[(k, R)] = nd
        nd += 1
    for i, v in enumerate(logicals(basis)):
        c.append("OBSERVABLE_INCLUDE", [m(("D", q)) for q in np.nonzero(v)[0]], i)
    return c, dmap


def dem_mechs(c):
    dem = c.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    out = set()
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        d = o = 0
        for tg in inst.targets_copy():
            if tg.is_relative_detector_id():
                d ^= 1 << tg.val
            elif tg.is_logical_observable_id():
                o ^= 1 << tg.val
        if d or o:
            out.add((d, o))
    return sorted(out)


def min_weight3(ms):
    """exact: smallest w <= 3 with an undetectable logical (XOR of w mechanisms: det 0, obs != 0), else None."""
    if any(d == 0 and o for d, o in ms):
        return 1
    by = {}
    for d, o in ms:
        by.setdefault(d, set()).add(o)
    if any(len(s) >= 2 for s in by.values()):
        return 2
    lst = [(d, next(iter(s))) for d, s in by.items()]
    for i in range(len(lst)):
        di, oi = lst[i]
        for j in range(i + 1, len(lst)):
            dj, oj = lst[j]
            s = by.get(di ^ dj)
            if s is not None:
                for ok in s:
                    if ok != oi ^ oj:
                        return 3
    return None


def dist(tau, S, basis, R, reset=True):
    c, _ = circuit(tau, S, basis, R, p=1e-3, reset=reset)
    return min_weight3(dem_mechs(c))


def fires(c):
    """noiseless circuit with injections: (any detector fired, observable flip mask)."""
    s = c.compile_detector_sampler()
    d, o = s.sample(1, separate_observables=True)
    return bool(d[0].any()), int(sum(int(b) << i for i, b in enumerate(o[0])))


def legal(tau, S):
    """own legality of an N(S) schedule (non-wrapping): layers in 1..S, distinct per check, distinct per data qubit,
    and the X/Z determinism parity (#shared qubits where the X CNOT precedes the Z CNOT is even)."""
    for k in KS:
        ts = [tau[(k, a)] for a in range(6)]
        if len(set(ts)) != 6 or not all(1 <= t <= S for t in ts):
            return False
    for q in range(ND):
        ts = [tau[(k, a)] for k in KS for a in range(6) if SUPP[k][a] == q]
        if len(set(ts)) != len(ts):
            return False
    for kx in KS:
        if kx[0] != "X":
            continue
        for kz in KS:
            if kz[0] != "Z":
                continue
            sh = set(SUPP[kx]) & set(SUPP[kz])
            n = sum(tau[(kx, SUPP[kx].index(q))] < tau[(kz, SUPP[kz].index(q))] for q in sh)
            if n % 2:
                return False
    return True
