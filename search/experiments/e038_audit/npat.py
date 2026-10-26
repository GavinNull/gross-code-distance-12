"""E-038 audit: my own semantics of E-038's witness PATTERNS for the non-wrapping class N(S), my own CNF of N(S),
and a physical (stim, noiseless + injected Paulis) check of a pattern instance.  Nothing imported from e038.

Schedule: tau[(k, q)] = CNOT layer (1..S) of check k on its data qubit q; every check prepared at layer 0 and
measured at layer S + 1; the same in every round (non-wrapping).

Pattern (E-038 json): [basis, slots]; slot
  ["D", q, r]          : relevant Pauli (X for Z memory, Z for X memory) on data q in round r, just before the CNOT of
                         some reader f* (reader = check of the memory type on q); f* is chosen by the attacker;
  ["H", k, U, r]       : ancilla error on spreader k (other type) in round r, right after its CNOTs not in U, where U is
                         a set of TERM indices (e036_audit term order A1 A2 A3 B1 B2 B3 -> qubit e036 support(k)[a]);
                         requires U to be the time-suffix of k's CNOTs;
  ["M", c, r]          : measurement flip of reader c in round r.
Effects (my derivation): a relevant Pauli on data u present right after time t of round r is seen by reader f on u
in round r if layer(f, u) > t, else in round r + 1 (persistent -> toggles the detector D(f, r) or D(f, r + 1) once).
The D cut before f*: t = layer(f*, q) - 1/2.  Hook: for each u in U, t = layer(k, u).  M: toggles D(c, r), D(c, r+1).
A pattern instance (pattern + choice of f*) 'cancels' if all toggles cancel; its residual is fixed by the pattern.
"""
from __future__ import annotations

import itertools

import numpy as np

from search.experiments.e038_audit import acore as C
from search.experiments.e036_audit.core import support as e036_support   # only for the term-index convention


def term_qubit(k, a):
    return e036_support(tuple(k))[a]


def norm_pattern(p):
    b, slots = p
    out = []
    for s in slots:
        if s[0] == "D":
            out.append(("D", int(s[1]), int(s[2])))
        elif s[0] == "H":
            k = tuple(s[1])
            out.append(("H", k, tuple(sorted(term_qubit(k, a) for a in s[2])), int(s[3])))
        else:
            out.append(("M", tuple(s[1]), int(s[2])))
    return (b, tuple(out))


class NSem:
    def __init__(self, S, meas=C.MEASURED):
        self.S = S
        self.meas = meas
        self.ks = C.check_list(meas)
        self.readers = {b: {q: [k for k in self.ks if k[0] == b and q in C.supp(k)] for q in range(18)} for b in "ZX"}
        self.L = {b: C.logicals(b, meas) for b in "ZX"}

    def residual_obs(self, pat):
        b, slots = pat
        v = np.zeros(18, np.uint8)
        for s in slots:
            if s[0] == "D":
                v[s[1]] ^= 1
            elif s[0] == "H":
                for u in s[2]:
                    v[u] ^= 1
        return v, (self.L[b] @ v) % 2

    def choices(self, pat):
        b, slots = pat
        return list(itertools.product(*[self.readers[b][s[1]] for s in slots if s[0] == "D"]))

    def toggles(self, pat, ch, tau):
        """set of toggled detectors (check, round) or None if an H slot's U is not a suffix in tau."""
        b, slots = pat
        tog = {}

        def t(key):
            tog[key] = tog.get(key, 0) ^ 1

        di = 0
        for s in slots:
            if s[0] == "D":
                _, q, r = s
                fs = ch[di]
                di += 1
                tf = tau[(fs, q)]
                for f in self.readers[b][q]:
                    t((f, r if tau[(f, q)] >= tf else r + 1))
            elif s[0] == "H":
                _, k, U, r = s
                lay = {q: tau[(k, q)] for q in C.supp(k)}
                if max(lay[q] for q in lay if q not in U) > min(lay[u] for u in U):
                    return None
                for u in U:
                    for f in self.readers[b][u]:
                        t((f, r if tau[(f, u)] > lay[u] else r + 1))
            else:
                _, c, r = s
                t((c, r))
                t((c, r + 1))
        return {k for k, v in tog.items() if v}

    def cancels(self, pat, tau):
        """list of choices for which the pattern instance cancels in tau."""
        return [ch for ch in self.choices(pat) if self.toggles(pat, ch, tau) == set()]


# ----------------------------------------------------------------------------- physical check
def physical(pat, ch, tau, S, meas=C.MEASURED, R=None, want_set=False):
    """noiseless stim memory circuit of tau (reset ancillas, all detectors), with the pattern's faults injected as
    deterministic Paulis / flips; returns (#fired detectors, observable flips).  Rounds shifted by +1."""
    import stim
    b, slots = pat
    rmax = max(s[-1] for s in slots)
    if R is None:
        R = rmax + 4
    ks = C.check_list(meas)
    nd = 18
    anc = {k: nd + i for i, k in enumerate(ks)}
    P = S + 2
    rel = "X" if b == "Z" else "Z"
    pre = {}   # (round, layer) -> list of (qubit, pauli) applied before the gates of that layer
    post = {}  # applied after the gates of that layer
    di = 0
    for s in slots:
        if s[0] == "D":
            _, q, r = s
            fs = ch[di]
            di += 1
            pre.setdefault((r + 1, tau[(fs, q)]), []).append((q, rel))
        elif s[0] == "H":
            _, k, U, r = s
            tl = max(tau[(k, q)] for q in C.supp(k) if q not in U)
            post.setdefault((r + 1, tl), []).append((anc[k], rel))
        else:
            _, c, r = s
            # flip of reader c's outcome: Z-check (Z memory) measured in Z -> X before M; X-check in X -> Z before MX
            pre.setdefault((r + 1, S + 1), []).append((anc[c], "X" if c[0] == "Z" else "Z"))
    c = stim.Circuit()
    c.append("R" if b == "Z" else "RX", list(range(nd)))
    rec, nm = {}, 0
    xa = [anc[k] for k in ks if k[0] == "X"]
    za = [anc[k] for k in ks if k[0] == "Z"]
    for j in range(R):
        for t in range(P):
            for q, pa in pre.get((j, t), []):
                c.append(pa + "_ERROR", [q], 1.0)
            if t == 0:
                c.append("RX", xa)
                c.append("R", za)
            pairs = []
            for k in ks:
                for q in C.supp(k):
                    if tau[(k, q)] == t:
                        pairs += [anc[k], q] if k[0] == "X" else [q, anc[k]]
            if pairs:
                c.append("CX", pairs)
            for q, pa in post.get((j, t), []):
                c.append(pa + "_ERROR", [q], 1.0)
            if t == S + 1:
                c.append("MX", xa)
                c.append("M", za)
                for k in [k for k in ks if k[0] == "X"] + [k for k in ks if k[0] == "Z"]:
                    rec[(k, j)] = nm
                    nm += 1
            c.append("TICK")
        for k in ks:
            if k[0] != b and j == 0:
                continue
            lst = [rec[(k, j)]] + ([rec[(k, j - 1)]] if j else [])
            c.append("DETECTOR", [stim.target_rec(x - nm) for x in lst])
    c.append("M" if b == "Z" else "MX", list(range(nd)))
    dm = {q: nm + q for q in range(nd)}
    nm += nd
    for k in ks:
        if k[0] == b:
            c.append("DETECTOR", [stim.target_rec(x - nm) for x in [dm[q] for q in C.supp(k)] + [rec[(k, R - 1)]]])
    L = C.logicals(b, meas)
    for i, v in enumerate(L):
        c.append("OBSERVABLE_INCLUDE", [stim.target_rec(dm[q] - nm) for q in np.nonzero(v)[0]], i)
    det, obs = c.compile_detector_sampler(seed=0).sample(1, separate_observables=True)
    if want_set:
        names = [(k, j) for j in range(R) for k in ks if not (k[0] != b and j == 0)]
        names += [(k, "final") for k in ks if k[0] == b]
        fired = {names[i] for i in np.nonzero(det[0])[0]}
        return fired, int(obs.sum())
    return int(det.sum()), int(obs.sum())


def physical_noreset(pat, ch, tau, S, meas=C.MEASURED, R=None):
    """same instance injected into the NO-RESET (Kunlun-style) circuit: ancillas reset once; X ancillas H ... H; all
    ancillas measured in Z; detectors m_j ^ m_{j-2} (s_j = m_j ^ m_{j-1}); the reader-flip slot M is an X error right
    before the Z measurement (it persists in the ancilla, as a real no-reset fault would)."""
    import stim
    b, slots = pat
    rmax = max(s[-1] for s in slots)
    R = R or rmax + 5
    ks = C.check_list(meas)
    nd = 18
    anc = {k: nd + i for i, k in enumerate(ks)}
    P = S + 2
    rel = "X" if b == "Z" else "Z"
    pre, post, prem = {}, {}, {}
    di = 0
    for s in slots:
        if s[0] == "D":
            _, q, r = s
            fs = ch[di]
            di += 1
            pre.setdefault((r + 1, tau[(fs, q)]), []).append((q, rel))
        elif s[0] == "H":
            _, k, U, r = s
            tl = max(tau[(k, q)] for q in C.supp(k) if q not in U)
            post.setdefault((r + 1, tl), []).append((anc[k], rel))
        else:
            _, c_, r = s
            prem.setdefault(r + 1, []).append(anc[c_])
    c = stim.Circuit()
    c.append("R" if b == "Z" else "RX", list(range(nd)))
    xa = [anc[k] for k in ks if k[0] == "X"]
    allanc = [anc[k] for k in ks]
    c.append("R", allanc)
    rec, nm = {}, 0
    for j in range(R):
        for t in range(P):
            for q, pa in pre.get((j, t), []):
                c.append(pa + "_ERROR", [q], 1.0)
            if t == 0:
                c.append("H", xa)
            pairs = []
            for k in ks:
                for q in C.supp(k):
                    if tau[(k, q)] == t:
                        pairs += [anc[k], q] if k[0] == "X" else [q, anc[k]]
            if pairs:
                c.append("CX", pairs)
            for q, pa in post.get((j, t), []):
                c.append(pa + "_ERROR", [q], 1.0)
            if t == S + 1:
                c.append("H", xa)
                for a in prem.get(j, []):
                    c.append("X_ERROR", [a], 1.0)
                c.append("M", allanc)
                for k in ks:
                    rec[(k, j)] = nm
                    nm += 1
            c.append("TICK")
        for k in ks:
            if k[0] != b and j == 0:
                continue
            lst = [rec[(k, j)]] + ([rec[(k, j - 2)]] if j >= 2 else [])
            c.append("DETECTOR", [stim.target_rec(x - nm) for x in lst])
    c.append("M" if b == "Z" else "MX", list(range(nd)))
    dm = {q: nm + q for q in range(nd)}
    nm += nd
    for k in ks:
        if k[0] == b:
            lst = [dm[q] for q in C.supp(k)] + [rec[(k, R - 1)], rec[(k, R - 2)]]
            c.append("DETECTOR", [stim.target_rec(x - nm) for x in lst])
    for i, v in enumerate(C.logicals(b, meas)):
        c.append("OBSERVABLE_INCLUDE", [stim.target_rec(dm[q] - nm) for q in np.nonzero(v)[0]], i)
    det, obs = c.compile_detector_sampler(seed=0).sample(8, separate_observables=True)
    if (det != det[0]).any() or (obs != obs[0]).any():
        return -1, -1   # non-deterministic
    return int(det[0].sum()), int(obs[0].sum())


# ----------------------------------------------------------------------------- my CNF of N(S) + pattern clauses
class NCNF:
    """one-hot layers x[e, t] (t = 1..S) for every event e = (k, q); order vars o[e1, e2] <-> layer(e1) < layer(e2)
    for pairs on the same qubit or in the same check; legality: exactly one layer, distinct layers per check and per
    qubit, X/Z determinism parity over shared qubits.  Pattern clauses via Tseitin XOR (own cache)."""

    def __init__(self, S, meas=C.MEASURED):
        self.S = S
        self.nv = 0
        self.cl = []
        self.ks = C.check_list(meas)
        self.ev = [(k, q) for k in self.ks for q in C.supp(k)]
        self.x = {e: {t: self.new() for t in range(1, S + 1)} for e in self.ev}
        for e in self.ev:
            v = list(self.x[e].values())
            self.cl.append(v)
            for a, b_ in itertools.combinations(v, 2):
                self.cl.append([-a, -b_])
        self.o = {}
        pairs = set()
        for k in self.ks:
            for q1, q2 in itertools.combinations(C.supp(k), 2):
                pairs.add(((k, q1), (k, q2)))
        for q in range(18):
            evq = [e for e in self.ev if e[1] == q]
            for e1, e2 in itertools.combinations(evq, 2):
                pairs.add((e1, e2))
        for e1, e2 in sorted(pairs):
            v = self.new()
            self.o[(e1, e2)] = v
            for t1 in range(1, S + 1):
                for t2 in range(1, S + 1):
                    if t1 == t2:
                        self.cl.append([-self.x[e1][t1], -self.x[e2][t2]])   # distinct
                    elif t1 < t2:
                        self.cl.append([-self.x[e1][t1], -self.x[e2][t2], v])
                    else:
                        self.cl.append([-self.x[e1][t1], -self.x[e2][t2], -v])
        for kx in self.ks:
            if kx[0] != "X":
                continue
            for kz in self.ks:
                if kz[0] != "Z":
                    continue
                sh = sorted(set(C.supp(kx)) & set(C.supp(kz)))
                if not sh:
                    continue
                lits = [self.lt((kx, q), (kz, q)) for q in sh]
                for signs in itertools.product([0, 1], repeat=len(lits)):
                    if sum(signs) % 2:     # forbid odd assignments
                        self.cl.append([(-l if s else l) for l, s in zip(lits, signs)])
        self.nleg = len(self.cl)
        self.xc = {}

    def new(self):
        self.nv += 1
        return self.nv

    def lt(self, e1, e2):
        if (e1, e2) in self.o:
            return self.o[(e1, e2)]
        return -self.o[(e2, e1)]

    def xor(self, lits):
        """literal equivalent to XOR(lits) (lits nonzero ints); returns (lit or None, const)."""
        const = 0
        cnt = {}
        for l in lits:
            if l < 0:
                const ^= 1
            cnt[abs(l)] = cnt.get(abs(l), 0) ^ 1
        vs = sorted(v for v, n in cnt.items() if n)
        if not vs:
            return None, const
        key = tuple(vs)
        if key not in self.xc:
            acc = vs[0]
            for v in vs[1:]:
                y = self.new()
                self.cl += [[-y, acc, v], [-y, -acc, -v], [y, -acc, v], [y, acc, -v]]
                acc = y
            self.xc[key] = acc
        return self.xc[key], const

    def pattern_clauses(self, sem: NSem, pat):
        """one clause per choice: (some H suffix condition fails) OR (some detector parity is odd)."""
        b, slots = pat
        out = []
        for ch in sem.choices(pat):
            cond = []      # literals that must all hold
            terms = {}     # detector -> list of literals / True
            di = 0
            for s in slots:
                if s[0] == "D":
                    _, q, r = s
                    fs = ch[di]
                    di += 1
                    for f in sem.readers[b][q]:
                        if f == fs:
                            terms.setdefault((f, r), []).append(True)
                        else:
                            l = self.lt((f, q), (fs, q))       # f before f*  -> seen in r + 1
                            terms.setdefault((f, r + 1), []).append(l)
                            terms.setdefault((f, r), []).append(-l)
                elif s[0] == "H":
                    _, k, U, r = s
                    for x_ in C.supp(k):
                        if x_ in U:
                            continue
                        for u in U:
                            cond.append(self.lt((k, x_), (k, u)))
                    for u in U:
                        for f in sem.readers[b][u]:
                            l = self.lt((f, u), (k, u))         # reader before hook CNOT -> r + 1
                            terms.setdefault((f, r + 1), []).append(l)
                            terms.setdefault((f, r), []).append(-l)
                else:
                    _, c, r = s
                    terms.setdefault((c, r), []).append(True)
                    terms.setdefault((c, r + 1), []).append(True)
            cl = [-l for l in cond]
            sat = False
            for key in sorted(terms, key=repr):
                const = sum(1 for l in terms[key] if l is True) % 2
                lits = [l for l in terms[key] if l is not True]
                y, c2 = self.xor(lits) if lits else (None, 0)
                const ^= c2
                if y is None:
                    if const:
                        sat = True
                        break
                    continue
                cl.append(-y if const else y)
            if not sat:
                out.append(cl)
        return out

    def decode(self, model):
        pos = set(l for l in model if l > 0)
        return {e: next(t for t, v in self.x[e].items() if v in pos) for e in self.ev}

    def assign(self, tau):
        """primary-variable literals for a schedule."""
        return [v if tau[e] == t else -v for e in self.ev for t, v in self.x[e].items()]
