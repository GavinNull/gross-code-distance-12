"""E-041 audit (fresh auditor, 2026-11-01): own pipelined finite-R circuit for a qec-schedule/v1 spec.

Imports nothing from search/experiments/e041 (or e038/e039 experiment code).  Reused audited auditor code:
e039_audit.fcore (code conventions KS/SUPP from e036_audit.core, own GF(2) logicals, exact weight<=3 search
min_weight3, dem_mechs).  The spec JSON is parsed here directly (not with the evaluator): each row is identified by
its data-qubit SUPPORT, not by row order.

Absolute-time schedule: check k has prep pi_k, CNOT times T_k(q) and meas mu_k with pi < T < mu (times that wrap in
the spec, i.e. are <= prep, get +P).  Instance j of check k is shifted by j * Pstretch.  Pstretch = P reproduces the
spec; Pstretch = P + 1 is the 'non-wrapping stretch' (an extra layer appended to every period; for E-041 this is the
period-10 picture in which rounds do not overlap).

Own SD6: reset flip after every reset (data + ancilla), DEPOLARIZE2(p) after each CX, DEPOLARIZE1(p) on every qubit
not acted on in a layer, measurement flip on every measurement incl. final data readout.  Data reset at layer 0;
final data readout in its own layer after the last ancilla measurement.  no-reset: the ancilla is reset only for
instance 0; later 'prep' layers do nothing (qubit idles).  Detectors (memory basis only, 14 measured checks):
reset D_j = m_j ^ m_{j-1}; no-reset D_j = m_j ^ m_{j-2}; final = data parity ^ m_{R-1} (^ m_{R-2} for no-reset).
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np
import stim

from search.experiments.e039_audit import fcore as F

KS, SUPP, ND = F.KS, F.SUPP, F.ND


def load(path):
    """-> dict(P, sched={k: (pi, mu_abs, {q: t_abs})}).  Row identification by support."""
    obj = json.loads(open(path).read())
    P = obj["period"]
    bysupp = {(k[0], frozenset(SUPP[k])): k for k in KS}
    sched = {}
    for typ in ("x_checks", "z_checks"):
        for row in obj[typ]:
            qs = frozenset(c for c, _ in row["cnots"])
            k = bysupp[(typ[0].upper(), qs)]
            assert k[0] == typ[0].upper(), (k, typ)
            assert k not in sched
            pi = row["prep"]
            mu = row["meas"] if row["meas"] > pi else row["meas"] + P
            T = {}
            for c, t in row["cnots"]:
                T[c] = t if t > pi else t + P
            sched[k] = (pi, mu, T)
    assert set(sched) == set(KS)
    return dict(P=P, sched=sched)


def from_fcore_tau(tau, S):
    """non-wrapping N(S) schedule given as fcore tau[(k, a)] -> same format (period S + 2)."""
    sched = {}
    for k in KS:
        sched[k] = (0, S + 1, {SUPP[k][a]: tau[(k, a)] for a in range(6)})
    return dict(P=S + 2, sched=sched)


def legal(S):
    """returns list of problems (empty = legal)."""
    P, sch = S["P"], S["sched"]
    out = []
    for k, (pi, mu, T) in sch.items():
        ts = list(T.values())
        if sorted(T) != sorted(SUPP[k]):
            out.append(f"{k}: support mismatch")
        if len(set(ts)) != 6:
            out.append(f"{k}: two CNOTs in one layer")
        if not all(pi < t < mu for t in ts):
            out.append(f"{k}: CNOT outside (prep, meas)")
        if mu - pi > P - 1:
            out.append(f"{k}: window {mu - pi} > P-1 (instance overlap)")
    # per layer mod P: each data qubit at most one CNOT
    for q in range(ND):
        rs = [T[q] % P for (pi, mu, T) in sch.values() if q in T]
        if len(set(rs)) != len(rs):
            out.append(f"data {q}: two CNOTs in the same layer mod P")
    return out


def events(S, R, Pst):
    """absolute layer -> list of ops; ('R', k, j), ('C', k, q), ('M', k, j).  Data reset is at layer 0 (separate)."""
    ev = {}
    for k, (pi, mu, T) in S["sched"].items():
        for j in range(R):
            o = j * Pst
            ev.setdefault(pi + o, []).append(("R", k, j))
            ev.setdefault(mu + o, []).append(("M", k, j))
            for q, t in T.items():
                ev.setdefault(t + o, []).append(("C", k, q))
    return ev


def circuit(S, basis, R, p=0.0, reset=True, Pst=None, inject=(), allow_m_before=False):
    Pst = Pst or S["P"]
    anc = {k: ND + i for i, k in enumerate(KS)}
    nq = ND + len(KS)
    ev = events(S, R, Pst)
    tmin = min(ev)
    assert tmin >= 0
    # data CNOTs must come after the data reset layer 0
    assert min(t for t, ops in ev.items() for o in ops if o[0] == "C") >= 1
    last = max(ev)
    inj = {}
    for (layer, when, q, pa) in inject:
        inj.setdefault((layer, when), []).append((q, pa))
    c = stim.Circuit()
    rec, nm = {}, 0

    def do_inj(t, w):
        for q, pa in inj.get((t, w), []):
            c.append(pa + "_ERROR", [q], 1.0)

    for t in range(0, last + 2):
        do_inj(t, "pre")
        if t == last + 1:
            c.append("M" if basis == "Z" else "MX", list(range(ND)), p)
            for q in range(ND):
                rec[("D", q)] = nm
                nm += 1
            do_inj(t, "post")
            break
        used = set()
        ops = ev.get(t, [])
        if t == 0:
            c.append("R" if basis == "Z" else "RX", list(range(ND)))
            if p:
                c.append("X_ERROR" if basis == "Z" else "Z_ERROR", list(range(ND)), p)
            used |= set(range(ND))
        # measurements (instance j) first, then resets (instance j') -- a qubit is never both in one layer here
        for o, k, j in ops:
            if o == "M":
                a = anc[k]
                assert a not in used, ("clash M", t, k)
                c.append("MX" if k[0] == "X" else "M", [a], p)
                rec[(k, j)] = nm
                nm += 1
                used.add(a)
        for o, k, j in ops:
            if o == "R":
                a = anc[k]
                assert a not in used, ("clash R", t, k)
                if reset or j == 0:
                    c.append("RX" if k[0] == "X" else "R", [a])
                    if p:
                        c.append("Z_ERROR" if k[0] == "X" else "X_ERROR", [a], p)
                    used.add(a)
        pairs = []
        for o, k, q in ops:
            if o == "C":
                a = anc[k]
                assert q not in used and a not in used, ("clash C", t, k, q)
                used |= {q, a}
                pairs += [a, q] if k[0] == "X" else [q, a]
        if pairs:
            c.append("CX", pairs)
            if p:
                c.append("DEPOLARIZE2", pairs, p)
        if p:
            idle = [q for q in range(nq) if q not in used]
            if idle:
                c.append("DEPOLARIZE1", idle, p)
        do_inj(t, "post")
        c.append("TICK")

    def m(key):
        return stim.target_rec(rec[key] - nm)
    readers = [k for k in KS if k[0] == basis]
    dmap, nd = {}, 0
    for j in range(R):
        for k in readers:
            tg = [m((k, j))]
            if reset and j >= 1:
                tg.append(m((k, j - 1)))
            if not reset and j >= 2:
                tg.append(m((k, j - 2)))
            c.append("DETECTOR", tg)
            dmap[(k, j)] = nd
            nd += 1
    for k in readers:
        tg = [m(("D", q)) for q in SUPP[k]] + [m((k, R - 1))]
        if not reset and R >= 2:
            tg.append(m((k, R - 2)))
        c.append("DETECTOR", tg)
        dmap[(k, R)] = nd
        nd += 1
    for i, v in enumerate(F.logicals(basis)):
        c.append("OBSERVABLE_INCLUDE", [m(("D", q)) for q in np.nonzero(v)[0]], i)
    return c, dmap


def mechs(S, basis, R, reset=True, Pst=None):
    c, _ = circuit(S, basis, R, p=1e-3, reset=reset, Pst=Pst)
    return F.dem_mechs(c)


def has_w4(ms):
    """given no undetectable logical of weight <= 3: is there one of weight exactly 4?  (pair collisions)"""
    by = {}
    lst = list(ms)
    for i in range(len(lst)):
        di, oi = lst[i]
        for j in range(i + 1, len(lst)):
            dj, oj = lst[j]
            key = di ^ dj
            ob = oi ^ oj
            s = by.setdefault(key, {})
            if s and any(o != ob for o in s):
                return True
            s.setdefault(ob, (i, j))
    return False
