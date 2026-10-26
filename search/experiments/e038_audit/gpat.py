"""E-038 audit: general (wrapping / pipelined) version of my pattern semantics and a periodic physical check.
Nothing imported from e038.

Schedule: period P; per check k prep pi[k], meas mu[k]; per event e = (k, q) an absolute time tau[e] of instance 0;
instance j of everything at +jP.  Semantics (doubled times avoid ties):
  data Pauli on u present right after (doubled) time t2: reader f on u first sees it in instance
      j0 = floor((t2 - 2 tau_f) / 2P) + 1      -> toggles detector D(f, j0) = s(f, j0) xor s(f, j0 - 1)
  D(q, r) with attacker's reader f*: t2 = 2 (tau_f* + rP) - 1;  H(k, U, r): U = time suffix of k, t2 = 2 (tau_g + rP)
  for each g = (k, u), u in U;  M(c, r): toggles D(c, r), D(c, r + 1).
Physical: noiseless periodic stim circuit, faults injected as X_ERROR / Z_ERROR(1), returns fired detector set and
observable flips.
"""
from __future__ import annotations

import itertools

import numpy as np

from search.experiments.e038_audit import acore as C
from search.experiments.e038_audit.npat import norm_pattern  # noqa: F401  (pattern json -> my slot format)


class GSem:
    def __init__(self, P, meas=C.MEASURED):
        self.P = P
        self.ks = C.check_list(meas)
        self.readers = {b: {q: [k for k in self.ks if k[0] == b and q in C.supp(k)] for q in range(18)} for b in "ZX"}

    def j0(self, tf, t2):
        return (t2 - 2 * tf) // (2 * self.P) + 1

    def choices(self, pat):
        b, slots = pat
        return list(itertools.product(*[self.readers[b][s[1]] for s in slots if s[0] == "D"]))

    def toggles(self, pat, ch, tau):
        b, slots = pat
        P = self.P
        tog = {}

        def t(key):
            tog[key] = tog.get(key, 0) ^ 1

        di = 0
        for s in slots:
            if s[0] == "D":
                _, q, r = s
                fs = ch[di]
                di += 1
                t2 = 2 * (tau[(fs, q)] + r * P) - 1
                for f in self.readers[b][q]:
                    t((f, self.j0(tau[(f, q)], t2)))
            elif s[0] == "H":
                _, k, U, r = s
                lay = {q: tau[(k, q)] for q in C.supp(k)}
                if max(lay[q] for q in lay if q not in U) > min(lay[u] for u in U):
                    return None
                for u in U:
                    t2 = 2 * (lay[u] + r * P)
                    for f in self.readers[b][u]:
                        t((f, self.j0(tau[(f, u)], t2)))
            else:
                _, c, r = s
                t((c, r))
                t((c, r + 1))
        return {k for k, v in tog.items() if v}

    def cancels(self, pat, tau):
        return [ch for ch in self.choices(pat) if self.toggles(pat, ch, tau) == set()]


def legal(P, pi, mu, tau, meas=C.MEASURED):
    """my own legality of a periodic single-ancilla schedule (python)."""
    ks = C.check_list(meas)
    for k in ks:
        ts = [tau[(k, q)] for q in C.supp(k)]
        if len(set(ts)) != 6 or not all(pi[k] < t < mu[k] for t in ts) or mu[k] - pi[k] > P - 1:
            return False, f"window {k}"
    for q in range(18):
        rs = [tau[(k, q)] % P for k in ks if q in C.supp(k)]
        if len(set(rs)) != len(rs):
            return False, f"qubit {q}"
    for kx in ks:
        for kz in ks:
            if kx[0] != "X" or kz[0] != "Z":
                continue
            sh = sorted(set(C.supp(kx)) & set(C.supp(kz)))
            for i in range(-4, 5):
                if sum(tau[(kx, q)] < tau[(kz, q)] + i * P for q in sh) % 2:
                    return False, f"parity {kx} {kz} {i}"
    return True, ""


def circuit(P, pi, mu, tau, basis, R, inject=(), meas=C.MEASURED, p=0.0):
    """periodic memory circuit.  inject: list of (global_time, 'pre'|'post', qubit, 'X'|'Z').
    Returns (circuit, detector names)."""
    import stim
    ks = C.check_list(meas)
    nd = 18
    anc = {k: nd + i for i, k in enumerate(ks)}
    allq = list(range(nd + len(ks)))
    ev = {}
    for k in ks:
        for j in range(R):
            ev.setdefault(pi[k] + j * P, []).append(("R", k, j))
            ev.setdefault(mu[k] + j * P, []).append(("M", k, j))
            for q in C.supp(k):
                ev.setdefault(tau[(k, q)] + j * P, []).append(("C", k, q))
    pre, post = {}, {}
    for (T, w, q, pa) in inject:
        (pre if w == "pre" else post).setdefault(T, []).append((q, pa))
    c = stim.Circuit()
    c.append("R" if basis == "Z" else "RX", list(range(nd)))
    if p:
        c.append("X_ERROR" if basis == "Z" else "Z_ERROR", list(range(nd)), p)
    c.append("TICK")
    rec, nm = {}, 0
    Tmax = max(ev)
    for T in range(0, Tmax + 1):
        for q, pa in pre.get(T, []):
            c.append(pa + "_ERROR", [q], 1.0)
        ops = ev.get(T, [])
        used = set()
        for o, k, j in ops:
            if o == "R":
                c.append("RX" if k[0] == "X" else "R", [anc[k]])
                if p:
                    c.append("Z_ERROR" if k[0] == "X" else "X_ERROR", [anc[k]], p)
                assert anc[k] not in used
                used.add(anc[k])
        pairs = []
        for o, k, q in ops:
            if o == "C":
                a = anc[k]
                assert a not in used and q not in used, ("clash", T, k, q)
                pairs += [a, q] if k[0] == "X" else [q, a]
                used |= {a, q}
        if pairs:
            c.append("CX", pairs)
            if p:
                c.append("DEPOLARIZE2", pairs, p)
        for q, pa in post.get(T, []):
            c.append(pa + "_ERROR", [q], 1.0)
        for o, k, j in ops:
            if o == "M":
                assert anc[k] not in used
                c.append("MX" if k[0] == "X" else "M", [anc[k]], p)
                used.add(anc[k])
                rec[(k, j)] = nm
                nm += 1
        if p:
            rest = [q for q in allq if q not in used]
            if rest:
                c.append("DEPOLARIZE1", rest, p)
        c.append("TICK")
    names = []
    for k in ks:
        for j in range(R):
            if k[0] != basis and j == 0:
                continue
            lst = [rec[(k, j)]] + ([rec[(k, j - 1)]] if j else [])
            c.append("DETECTOR", [stim.target_rec(x - nm) for x in lst])
            names.append((k, j))
    c.append("M" if basis == "Z" else "MX", list(range(nd)), p)
    dm = {q: nm + q for q in range(nd)}
    nm += nd
    for k in ks:
        if k[0] == basis:
            c.append("DETECTOR", [stim.target_rec(x - nm) for x in [dm[q] for q in C.supp(k)] + [rec[(k, R - 1)]]])
            names.append((k, "final"))
    for i, v in enumerate(C.logicals(basis, meas)):
        c.append("OBSERVABLE_INCLUDE", [stim.target_rec(dm[q] - nm) for q in np.nonzero(v)[0]], i)
    return c, names


def physical(pat, ch, P, pi, mu, tau, shift=2, meas=C.MEASURED):
    b, slots = pat
    rel = "X" if b == "Z" else "Z"
    ks = C.check_list(meas)
    anc = {k: 18 + i for i, k in enumerate(ks)}
    inj = []
    di = 0
    for s in slots:
        if s[0] == "D":
            _, q, r = s
            fs = ch[di]
            di += 1
            inj.append((tau[(fs, q)] + (r + shift) * P, "pre", q, rel))
        elif s[0] == "H":
            _, k, U, r = s
            tl = max(tau[(k, q)] for q in C.supp(k) if q not in U)
            inj.append((tl + (r + shift) * P, "post", anc[k], rel))
        else:
            _, cc, r = s
            inj.append((mu[cc] + (r + shift) * P, "pre", anc[cc], "X" if cc[0] == "Z" else "Z"))
    rmax = max(s[-1] for s in slots)
    R = rmax + shift + 4
    c, names = circuit(P, pi, mu, tau, b, R, inj, meas)
    det, obs = c.compile_detector_sampler(seed=0).sample(1, separate_observables=True)
    fired = {names[i] for i in np.nonzero(det[0])[0]}
    return {(k, j - shift) if j != "final" else (k, j) for k, j in fired}, int(obs.sum())


def deterministic(P, pi, mu, tau, R=6, meas=C.MEASURED):
    """stim must accept all detectors as deterministic in the noiseless periodic circuit (both bases)."""
    for b in "ZX":
        c, _ = circuit(P, pi, mu, tau, b, R, (), meas, p=1e-3)
        try:
            c.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
        except Exception as ex:  # noqa: BLE001
            return False, str(ex)[:200]
    return True, ""
