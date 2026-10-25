"""E-038 periodic (wraparound / pipelined) single-ancilla schedules for the Kunlun [[18,4,4]] / [[18,6,3]] codes.

Code, check labels, supports and logical bases are imported from the audited independent core
(search/experiments/e036_audit/core.py): event e = (k, a), k = ("X"|"Z", row), a = term 0..5, qubit support(k)[a].

Schedule (Sched): period P; per check k a prep time pi[k] and a measurement time mu[k]; per event an absolute time
tau[e] of the round-0 instance.  Instance j of check k occupies [pi + jP, mu + jP].  Requirements (legal()):
  pi < tau(k, a) < mu  for all a,  mu - pi <= P - 1,  the 6 tau of a check distinct,
  events on one data qubit have distinct tau mod P,
  determinism: for every X check kx, Z check kz with shared qubits Q and every instance shift i,
      #{q in Q : tau(kx, q) < tau(kz, q) + iP} is even.
Non-wrapping class N(S): P = S + 2, pi = 0, mu = S + 1 for every check (E-036's template).

Bulk model (infinite memory, memory basis b; readers = type-b checks, spreaders = the other type; relevant Pauli =
X for b = Z, Z for b = X).  Detector D(c, j) = s(c, j) xor s(c, j-1).  Single-fault mechanisms (relevant part):
  D(q, f*, r)  data error on q just before reader event f* of instance r (every cut position on q is of this form):
               each reader f on q first sees it in instance j0 = min{j : tau_f + jP > tau_f* + rP - 1/2}
               -> toggles D(c_f, j0); residual {q}.
  H(k, U, r)   spreader ancilla error after its p-th CNOT (p = 1..4, |U| = 6 - p = suffix of its time order),
               instance r: for each suffix event g on qubit u and each reader f on u,
               j0 = min{j : tau_f + jP > tau_g + rP}; toggles D(c_f, j0); residual U.  (p = 5 equals a data cut;
               an error before the first CNOT acts trivially on the prepared ancilla.)
  M(c, r)      reader measurement / reset / reader-ancilla error: D(c, r), D(c, r + 1); residual 0.
An undetectable logical = set of mechanisms with zero total detector mask and residual a non-trivial logical
(observable mask = residual . logical basis of the opposite type).
"""
from __future__ import annotations

import itertools
import os
import random

os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np

from search.experiments.e036_audit.core import (checks, min_weight_le, observables, support)

PAD = 4  # detector round offset


class Sched:
    def __init__(self, variant, P, pi, mu, tau):
        self.variant, self.P = variant, P
        self.pi, self.mu, self.tau = dict(pi), dict(mu), dict(tau)
        self.ks = checks(variant)

    @staticmethod
    def nonwrap(variant, T, S):
        """from the audit format T[k] = [layer of term 0..5] (layers 1..S)."""
        ks = checks(variant)
        tau = {(k, a): T[k][a] for k in ks for a in range(6)}
        return Sched(variant, S + 2, {k: 0 for k in ks}, {k: S + 1 for k in ks}, tau)

    def to_json(self):
        return {"variant": self.variant, "P": self.P,
                "checks": [{"check": list(k), "prep": self.pi[k], "meas": self.mu[k],
                            "tau": [self.tau[(k, a)] for a in range(6)]} for k in self.ks]}

    @staticmethod
    def from_json(d):
        pi, mu, tau = {}, {}, {}
        for row in d["checks"]:
            k = tuple(row["check"])
            pi[k], mu[k] = row["prep"], row["meas"]
            for a, t in enumerate(row["tau"]):
                tau[(k, a)] = t
        return Sched(d["variant"], d["P"], pi, mu, tau)

    def spec(self):
        """evaluator qec-schedule/v1 dict (only measured checks; rows in the variant's order)."""
        P = self.P
        xs = [k for k in self.ks if k[0] == "X"]
        zs = [k for k in self.ks if k[0] == "Z"]
        out = {}
        for nm, lst in (("x_checks", xs), ("z_checks", zs)):
            out[nm] = [{"prep": self.pi[k] % P, "meas": self.mu[k] % P,
                        "cnots": sorted([[support(k)[a], self.tau[(k, a)] % P] for a in range(6)])} for k in lst]
        return {"format": "qec-schedule/v1", "period": P, **out}


def legal(s: Sched):
    P = s.P
    ks = s.ks
    for k in ks:
        ts = [s.tau[(k, a)] for a in range(6)]
        if len(set(ts)) != 6:
            return False, f"{k} repeated time"
        if not all(s.pi[k] < t < s.mu[k] for t in ts):
            return False, f"{k} event outside window"
        if s.mu[k] - s.pi[k] > P - 1:
            return False, f"{k} window too long"
    onq = {}
    for k in ks:
        for a, q in enumerate(support(k)):
            onq.setdefault(q, []).append(s.tau[(k, a)] % P)
    for q, rs in onq.items():
        if len(set(rs)) != len(rs):
            return False, f"qubit {q} collision mod P"
    for kx in ks:
        if kx[0] != "X":
            continue
        for kz in ks:
            if kz[0] != "Z":
                continue
            sx, sz = support(kx), support(kz)
            sh = [q for q in sx if q in sz]
            if not sh:
                continue
            for i in range(-3, 4):
                n = sum(s.tau[(kx, sx.index(q))] < s.tau[(kz, sz.index(q))] + i * P for q in sh)
                if n % 2:
                    return False, f"{kx},{kz} shift {i} odd"
    return True, ""


class Bulk:
    """bulk mechanisms of a schedule for memory basis b, faults in rounds 0..W-1."""

    def __init__(self, s: Sched, basis, W=6):
        self.s, self.b, self.W = s, basis, W
        self.readers = [k for k in s.ks if k[0] == basis]
        self.spreaders = [k for k in s.ks if k[0] != basis]
        self.ridx = {k: i for i, k in enumerate(self.readers)}
        self.NJ = W + 2 * PAD
        L = observables(s.variant, basis)
        self.obsq = [sum(1 << i for i in range(len(L)) if L[i][q]) for q in range(18)]
        self.rev = {q: [] for q in range(18)}
        for k in self.readers:
            for a, q in enumerate(support(k)):
                self.rev[q].append((k, a))

    def bit(self, c, j):
        jj = j + PAD
        assert 0 <= jj < self.NJ, (c, j)
        return 1 << (self.ridx[c] * self.NJ + jj)

    def j0(self, f, t2):
        """first instance of reader event f with 2*tau_f + 2jP > t2 (t2 = doubled time)."""
        P, tf = self.s.P, self.s.tau[f]
        return (t2 - 2 * tf) // (2 * P) + 1

    def mechs(self):
        s, P, W = self.s, self.s.P, self.W
        out = []
        for r in range(W):
            for q in range(18):
                for fs in self.rev[q]:
                    t2 = 2 * (s.tau[fs] + r * P) - 1
                    d = 0
                    for f in self.rev[q]:
                        d ^= self.bit(f[0], self.j0(f, t2))
                    out.append((d, self.obsq[q], ("D", q, fs, r)))
            for k in self.spreaders:
                order = sorted(range(6), key=lambda a: s.tau[(k, a)])
                for p in range(1, 5):
                    suf = order[p:]
                    d = o = 0
                    for a in suf:
                        g = (k, a)
                        u = support(k)[a]
                        t2 = 2 * (s.tau[g] + r * P)
                        for f in self.rev[u]:
                            d ^= self.bit(f[0], self.j0(f, t2))
                        o ^= self.obsq[u]
                    out.append((d, o, ("H", k, frozenset(suf), r)))
            for c in self.readers:
                out.append((self.bit(c, r) ^ self.bit(c, r + 1), 0, ("M", c, r)))
        return out


def bulk_min(s: Sched, wmax=3, W=6, want_all=False, limit=200, bases=("Z", "X")):
    """smallest bulk weight <= wmax over the bases (None if none) and witnesses [(basis, [tags])]."""
    best, wits = None, []
    for b in bases:
        bk = Bulk(s, b, W)
        ms = bk.mechs()
        w, ww = min_weight_le(ms, wmax, want_all=want_all, limit=limit)
        if w is None:
            continue
        if best is None or w < best:
            best, wits = w, []
        if w == best:
            wits += [(b, [ms[i][2] for i in t]) for t in ww]
    return best, wits


# ----------------------------------------------------------------------------- own stim circuit (periodic)
def stim_circuit(s: Sched, basis, R, p=1e-3):
    """SD6 memory circuit of the periodic schedule: data reset at layer 0; instance j of check k: reset at
    pi + jP + 1, CNOTs at tau + jP + 1, measurement at mu + jP + 1 (all instances 0..R-1 of every check);
    final data readout in a separate last layer.  DEPOLARIZE2 after CX, DEPOLARIZE1 on every qubit idle in a layer,
    reset flip, measurement flip.  Detectors only for the memory-basis checks: m_0, m_j ^ m_{j-1}, final parity ^ m_{R-1}.
    Returns (circuit, detector index map {(check, j): idx})."""
    import stim
    P = s.P
    ks = s.ks
    nd = 18
    anc = {k: nd + i for i, k in enumerate(ks)}
    allq = list(range(nd + len(ks)))
    ev = {}
    for k in ks:
        for j in range(R):
            off = j * P + 1
            ev.setdefault(s.pi[k] + off, []).append(("R", k, j))
            ev.setdefault(s.mu[k] + off, []).append(("M", k, j))
            for a in range(6):
                ev.setdefault(s.tau[(k, a)] + off, []).append(("C", k, a))
    T = max(ev) + 1
    c = stim.Circuit()
    c.append("R" if basis == "Z" else "RX", list(range(nd)))
    c.append("X_ERROR" if basis == "Z" else "Z_ERROR", list(range(nd)), p)
    c.append("TICK")
    rec, nm = {}, 0
    for t in range(1, T):
        ops = ev.get(t, [])
        used = set()
        rx = [anc[k] for o, k, _ in ops if o == "R" and k[0] == "X"]
        rz = [anc[k] for o, k, _ in ops if o == "R" and k[0] == "Z"]
        if rx:
            c.append("RX", rx)
            c.append("Z_ERROR", rx, p)
        if rz:
            c.append("R", rz)
            c.append("X_ERROR", rz, p)
        used |= set(rx + rz)
        pairs = []
        for o, k, a in ops:
            if o == "C":
                q = support(k)[a]
                pairs += [anc[k], q] if k[0] == "X" else [q, anc[k]]
                assert anc[k] not in used and q not in used, ("clash", t, k, a)
                used |= {anc[k], q}
        if pairs:
            c.append("CX", pairs)
            c.append("DEPOLARIZE2", pairs, p)
        ms = [(k, j) for o, k, j in ops if o == "M"]
        for k, j in ms:
            assert anc[k] not in used
            c.append("MX" if k[0] == "X" else "M", [anc[k]], p)
            used.add(anc[k])
            rec[(k, j)] = nm
            nm += 1
        rest = [q for q in allq if q not in used]
        if rest:
            c.append("DEPOLARIZE1", rest, p)
        c.append("TICK")
    c.append("M" if basis == "Z" else "MX", list(range(nd)), p)
    dm = {q: nm + q for q in range(nd)}
    nm += nd
    dets = {}
    nd_ = 0
    for k in ks:
        if k[0] != basis:
            continue
        for j in range(R + 1):
            if j < R:
                lst = [rec[(k, j)]] + ([rec[(k, j - 1)]] if j else [])
            else:
                lst = [dm[q] for q in support(k)] + [rec[(k, R - 1)]]
            c.append("DETECTOR", [stim.target_rec(x - nm) for x in lst])
            dets[(k, j)] = nd_
            nd_ += 1
    for i, v in enumerate(observables(s.variant, basis)):
        c.append("OBSERVABLE_INCLUDE", [stim.target_rec(dm[q] - nm) for q in np.nonzero(v)[0]], i)
    return c, dets


def stim_mechs(circ):
    dem = circ.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    out = set()
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        d = o = 0
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                d ^= 1 << t.val
            elif t.is_logical_observable_id():
                o ^= 1 << t.val
        if d or o:
            out.add((d, o))
    return sorted(out)
