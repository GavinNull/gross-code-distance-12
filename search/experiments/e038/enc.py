"""E-038 CNF encoding of a schedule class (see model.py for the definition of a legal periodic schedule).

Classes:
  N(S)   non-wrapping, S CNOT layers: P = S + 2, pi = 0, mu = S + 1 (constants), tau in 1..S.
  W(P)   wrapping, per-check prep/meas: pi in 0..P-1 (pi of the first check fixed to 0: a global time shift followed
         by relabelling the instances of the checks pushed past P is a symmetry of the bulk model and of legality),
         mu in 7..2P-2, tau in 1..2P-3, pi < tau < mu, mu - pi <= P - 1.
Integers use the order encoding  u[v, t] <-> v <= t.  LT(g, f, k) := tau_g < tau_f + kP (reified, cached).
"""
from __future__ import annotations

import itertools

from search.experiments.e036_audit.core import checks, support


class IntVar:
    def __init__(self, enc, lo, hi):
        self.lo, self.hi = lo, hi
        self.u = {}
        for t in range(lo, hi):
            self.u[t] = enc.new()
        for t in range(lo, hi - 1):
            enc.add([-self.u[t], self.u[t + 1]])
        self.x = {}
        self.enc = enc

    def le(self, t):
        """literal for v <= t, or True / False."""
        if t >= self.hi:
            return True
        if t < self.lo:
            return False
        return self.u[t]

    def eq(self, t):
        if t < self.lo or t > self.hi:
            return False
        if t in self.x:
            return self.x[t]
        a, b = self.le(t), self.le(t - 1)   # v = t  <->  (v <= t) & ~(v <= t-1)
        if b is False:
            lit = a
        elif a is True:
            lit = -b if b is not True else False
        else:
            v = self.enc.new()
            e = self.enc
            e.add([-v, a])
            if b is not True:
                e.add([-v, -b])
                e.add([v, -a, b])
            lit = v
        self.x[t] = lit
        return lit


class Enc:
    def __init__(self, variant, cls, S_or_P):
        self.variant, self.cls = variant, cls
        self.nv = 0
        self.cl = []
        self.ks = checks(variant)
        self.ev = [(k, a) for k in self.ks for a in range(6)]
        if cls == "N":
            S = S_or_P
            self.P = P = S + 2
            self.pi = {k: IntVar(self, 0, 0) for k in self.ks}
            self.mu = {k: IntVar(self, S + 1, S + 1) for k in self.ks}
            self.tau = {e: IntVar(self, 1, S) for e in self.ev}
        else:
            self.P = P = S_or_P
            self.pi = {}
            for i, k in enumerate(self.ks):
                self.pi[k] = IntVar(self, 0, 0) if i == 0 else IntVar(self, 0, P - 1)
            self.mu = {k: IntVar(self, 7, 2 * P - 2) for k in self.ks}
            self.tau = {e: IntVar(self, 1, 2 * P - 3) for e in self.ev}
        self.ltc = {}
        self.andc = {}
        self.xorc = {}
        for k in self.ks:
            for a in range(6):
                e = (k, a)
                self.hard_le(self.pi[k], self.tau[e], 1)      # pi + 1 <= tau
                self.hard_le(self.tau[e], self.mu[k], 1)      # tau + 1 <= mu
            self.hard_le(self.mu[k], self.pi[k], -(P - 1))    # mu - (P-1) <= pi
            evs = [(k, a) for a in range(6)]
            for e1, e2 in itertools.combinations(evs, 2):
                self.distinct(e1, e2, mod=False)
        self.onq = {}
        for k in self.ks:
            for a, q in enumerate(support(k)):
                self.onq.setdefault(q, []).append((k, a))
        for q, evs in self.onq.items():
            for e1, e2 in itertools.combinations(evs, 2):
                self.distinct(e1, e2, mod=True)
        # determinism parity
        for kx in self.ks:
            if kx[0] != "X":
                continue
            for kz in self.ks:
                if kz[0] != "Z":
                    continue
                sx, sz = support(kx), support(kz)
                sh = [q for q in sx if q in sz]
                if not sh:
                    continue
                for i in (-2, -1, 0, 1, 2):
                    lits = [self.LT((kx, sx.index(q)), (kz, sz.index(q)), i) for q in sh]
                    self.xor_const(lits, 0)

    # ------------------------------------------------------------------ basics
    def new(self):
        self.nv += 1
        return self.nv

    def add(self, c):
        """add a clause given as a list of literals / booleans (True -> drop clause, False -> drop literal)."""
        out = []
        for l in c:
            if l is True:
                return
            if l is False:
                continue
            out.append(l)
        self.cl.append(out)

    def hard_le(self, a: IntVar, b: IntVar, d):
        """a + d <= b."""
        for t in range(a.lo, a.hi + 1):
            # a >= t  ->  b >= t + d     i.e.  (a <= t-1) or not (b <= t+d-1)
            self.add([a.le(t - 1), neg(b.le(t + d - 1))])

    def distinct(self, e1, e2, mod):
        a, b = self.tau[e1], self.tau[e2]
        P = self.P
        for t in range(a.lo, a.hi + 1):
            for t2 in range(b.lo, b.hi + 1):
                if (t == t2) or (mod and (t - t2) % P == 0):
                    self.add([neg(a.eq(t)), neg(b.eq(t2))])

    def LT(self, g, f, k):
        """literal  tau_g < tau_f + kP  (g, f events)."""
        key = (g, f, k)
        if key in self.ltc:
            return self.ltc[key]
        a, b = self.tau[g], self.tau[f]
        c = k * self.P - 1   # a - b <= c
        if a.hi - b.lo <= c:
            lit = True
        elif a.lo - b.hi > c:
            lit = False
        else:
            v = self.new()
            for t in range(b.lo, b.hi + 1):       # v & b <= t  ->  a <= t + c
                self.add([-v, neg(b.le(t)), a.le(t + c)])
            for t in range(a.lo, a.hi + 1):       # ~v & a <= t ->  b <= t - c - 1
                self.add([v, neg(a.le(t)), b.le(t - c - 1)])
            lit = v
        self.ltc[key] = lit
        return lit

    def AND(self, lits):
        lits = [l for l in lits if l is not True]
        if any(l is False for l in lits):
            return False
        if not lits:
            return True
        if len(lits) == 1:
            return lits[0]
        key = tuple(sorted(lits))
        if key in self.andc:
            return self.andc[key]
        v = self.new()
        for l in lits:
            self.add([-v, l])
        self.add([v] + [-l for l in lits])
        self.andc[key] = v
        return v

    def XOR(self, lits, const=0):
        """literal equal to XOR(lits) ^ const (Tseitin, cached)."""
        c = const
        ls = []
        for l in lits:
            if l is True:
                c ^= 1
            elif l is False:
                continue
            else:
                ls.append(l)
        # cancel duplicate / complementary literals
        cnt = {}
        for l in ls:
            v = abs(l)
            cnt[v] = cnt.get(v, 0) ^ 1
            if l < 0:
                c ^= 1
        vs = sorted(v for v, n in cnt.items() if n)
        if not vs:
            return bool(c)
        key = tuple(vs)
        if key not in self.xorc:
            acc = vs[0]
            for v in vs[1:]:
                y = self.new()
                self.cl += [[-y, acc, v], [-y, -acc, -v], [y, -acc, v], [y, acc, -v]]
                acc = y
            self.xorc[key] = acc
        acc = self.xorc[key]
        return -acc if c else acc

    def xor_const(self, lits, const):
        """hard constraint XOR(lits) = const (direct CNF, lits are few)."""
        c = const
        ls = []
        for l in lits:
            if l is True:
                c ^= 1
            elif l is False:
                continue
            else:
                ls.append(l)
        if not ls:
            if c:
                self.cl.append([])
            return
        n = len(ls)
        for signs in itertools.product([0, 1], repeat=n):
            if sum(signs) % 2 != c:   # forbid this assignment (signs = values of ls)
                self.cl.append([(-l if s else l) for l, s in zip(ls, signs)])

    # ------------------------------------------------------------------ decode
    def value(self, iv: IntVar, pos):
        for t in range(iv.lo, iv.hi):
            if iv.u[t] in pos:
                return t
        return iv.hi

    def decode(self, model):
        from search.experiments.e038.model import Sched
        pos = set(l for l in model if l > 0)
        pi = {k: self.value(self.pi[k], pos) for k in self.ks}
        mu = {k: self.value(self.mu[k], pos) for k in self.ks}
        tau = {e: self.value(self.tau[e], pos) for e in self.ev}
        return Sched(self.variant, self.P, pi, mu, tau)


def neg(l):
    if l is True:
        return False
    if l is False:
        return True
    return -l
