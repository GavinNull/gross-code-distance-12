"""E-039 merged measure+reset class Mg(P): as e038.enc W(P), but the measurement of instance j and the reset of
instance j+1 of an ancilla share one layer: mu - pi <= P (instead of P - 1).  So pi in 0..P-1 (first check 0),
tau in 1..2P-2, mu in 7..2P-1, pi < tau < mu, mu - pi <= P.  Everything else (distinctness, determinism parity, LT
literals, decode) is inherited unchanged from e038.enc.Enc."""
from __future__ import annotations

import itertools

from search.experiments.e036_audit.core import checks, support
from search.experiments.e038.enc import Enc, IntVar


class EncMerged(Enc):
    def __init__(self, variant, P):
        self.variant, self.cls = variant, "Mg"
        self.nv = 0
        self.cl = []
        self.ks = checks(variant)
        self.ev = [(k, a) for k in self.ks for a in range(6)]
        self.P = P
        self.pi = {k: (IntVar(self, 0, 0) if i == 0 else IntVar(self, 0, P - 1)) for i, k in enumerate(self.ks)}
        self.mu = {k: IntVar(self, 7, 2 * P - 1) for k in self.ks}
        self.tau = {e: IntVar(self, 1, 2 * P - 2) for e in self.ev}
        self.ltc, self.andc, self.xorc = {}, {}, {}
        for k in self.ks:
            for a in range(6):
                e = (k, a)
                self.hard_le(self.pi[k], self.tau[e], 1)
                self.hard_le(self.tau[e], self.mu[k], 1)
            self.hard_le(self.mu[k], self.pi[k], -P)          # mu - P <= pi   (merged layer)
            for e1, e2 in itertools.combinations([(k, a) for a in range(6)], 2):
                self.distinct(e1, e2, mod=False)
        self.onq = {}
        for k in self.ks:
            for a, q in enumerate(support(k)):
                self.onq.setdefault(q, []).append((k, a))
        for q, evs in self.onq.items():
            for e1, e2 in itertools.combinations(evs, 2):
                self.distinct(e1, e2, mod=True)
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
