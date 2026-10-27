"""E-039 audit: own periodic (pipelined) noiseless circuit with injected Paulis, for W(P) and merged Mg(P) schedules,
plus own legality.  Schedule: P, pi[k], mu[k], tau[(k, a)] (round-0 instance, absolute layers); instance j at +jP.
Merged layer (mu_k = pi_k + P): the ancilla is measured (instance j) and then reset (instance j+1) in the same layer.
Detectors: memory-basis checks, D(c, 0) = m0, D(c, j) = m_j ^ m_{j-1}, final parity ^ m_{R-1}; observables = own
logical basis (fcore).  Everything here is my own code (fcore conventions)."""
from __future__ import annotations

import numpy as np
import stim

from search.experiments.e039_audit import fcore as F


def legal(P, pi, mu, tau, merged=False):
    gap = P if merged else P - 1
    for k in F.KS:
        ts = [tau[(k, a)] for a in range(6)]
        if len(set(ts)) != 6 or not all(pi[k] < t < mu[k] for t in ts) or mu[k] - pi[k] > gap:
            return False
    for q in range(F.ND):
        rs = [tau[(k, a)] % P for k in F.KS for a in range(6) if F.SUPP[k][a] == q]
        if len(set(rs)) != len(rs):
            return False
    for kx in F.KS:
        for kz in F.KS:
            if kx[0] != "X" or kz[0] != "Z":
                continue
            sh = set(F.SUPP[kx]) & set(F.SUPP[kz])
            for i in range(-5, 6):
                if sum(tau[(kx, F.SUPP[kx].index(q))] < tau[(kz, F.SUPP[kz].index(q))] + i * P for q in sh) % 2:
                    return False
    return True


def circuit(P, pi, mu, tau, basis, R, inject=()):
    anc = {k: F.ND + i for i, k in enumerate(F.KS)}
    ev = {}
    for k in F.KS:
        for j in range(R):
            ev.setdefault(pi[k] + j * P, []).append(("R", k, j))
            ev.setdefault(mu[k] + j * P, []).append(("M", k, j))
            for a in range(6):
                ev.setdefault(tau[(k, a)] + j * P, []).append(("C", k, a))
    pre, post = {}, {}
    for (T, w, q, pa) in inject:
        (pre if w == "pre" else post).setdefault(T, []).append((q, pa))
    c = stim.Circuit()
    c.append("R" if basis == "Z" else "RX", list(range(F.ND)))
    c.append("TICK")
    rec, nm = {}, 0
    for T in range(0, max(ev) + 1):
        for q, pa in pre.get(T, []):
            c.append(pa + "_ERROR", [q], 1.0)
        ops = ev.get(T, [])
        busy = {}
        for o, k, x in ops:
            if o == "C":
                q = F.SUPP[k][x]
                for z in (anc[k], q):
                    assert z not in busy, ("clash", T, k, x)
                    busy[z] = "C"
        pairs = []
        for o, k, a in ops:
            if o == "C":
                q = F.SUPP[k][a]
                pairs += [anc[k], q] if k[0] == "X" else [q, anc[k]]
        if pairs:
            c.append("CX", pairs)
        for q, pa in post.get(T, []):
            c.append(pa + "_ERROR", [q], 1.0)
        # measurements first, then resets (merged layer: measure instance j, reset instance j+1)
        for o, k, j in ops:
            if o == "M":
                assert anc[k] not in busy
                c.append("MX" if k[0] == "X" else "M", [anc[k]])
                rec[(k, j)] = nm
                nm += 1
        for o, k, j in ops:
            if o == "R":
                assert busy.get(anc[k]) is None
                c.append("RX" if k[0] == "X" else "R", [anc[k]])
        c.append("TICK")
    for k in F.KS:
        if k[0] != basis:
            continue
        for j in range(R):
            lst = [rec[(k, j)]] + ([rec[(k, j - 1)]] if j else [])
            c.append("DETECTOR", [stim.target_rec(x - nm) for x in lst])
    c.append("M" if basis == "Z" else "MX", list(range(F.ND)))
    dm = {q: nm + q for q in range(F.ND)}
    nm += F.ND
    for k in F.KS:
        if k[0] == basis:
            c.append("DETECTOR", [stim.target_rec(x - nm) for x in [dm[q] for q in F.SUPP[k]] + [rec[(k, R - 1)]]])
    for i, v in enumerate(F.logicals(basis)):
        c.append("OBSERVABLE_INCLUDE", [stim.target_rec(dm[q] - nm) for q in np.nonzero(v)[0]], i)
    return c


def inject_bulk(P, pi, mu, tau, pat, ch, shift=3):
    """pattern slots in E-039 format (D(q, r), H(k, U-term-indices, r), M(c, r)), choice ch = reader events (k, a)."""
    b, slots = pat
    rel = "X" if b == "Z" else "Z"
    inj = []
    e = np.zeros(F.ND, np.uint8)
    di = 0
    for s in slots:
        if s[0] == "D":
            _, q, r = s
            fs = ch[di]
            di += 1
            assert F.SUPP[fs[0]][fs[1]] == q
            inj.append((tau[fs] + (r + shift) * P, "pre", q, rel))
            e[q] ^= 1
        elif s[0] == "H":
            _, k, U, r = s
            order = sorted(range(6), key=lambda a: tau[(k, a)])
            p = 6 - len(U)
            if set(order[p:]) != set(U):
                return None, None, None
            inj.append((tau[(k, order[p - 1])] + (r + shift) * P, "post", F.ND + F.KS.index(k), rel))
            for a in U:
                e[F.SUPP[k][a]] ^= 1
        else:
            _, cc, r = s
            inj.append((mu[cc] + (r + shift) * P, "pre", F.ND + F.KS.index(cc), "X" if cc[0] == "Z" else "Z"))
    rmax = max(s[-1] for s in slots)
    return inj, rmax + shift + 4, e
