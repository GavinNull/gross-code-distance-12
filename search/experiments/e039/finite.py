"""E-039 finite-R fault model for NON-WRAPPING schedules (class N(S): prep 0, CNOTs 1..S, meas S+1, P = S+2) and
the finite-R pattern clauses.

Memory experiment with exactly R rounds (evaluator template): data reset in basis b, rounds 0..R-1, final data readout
in basis b.  Detectors (readers c = measured checks of type b): D(c,0) = s(c,0), D(c,j) = s(c,j) ^ s(c,j-1) (j < R),
D(c,R) = final data parity on supp(c) ^ s(c,R-1).  Relevant single faults (X parts in Z memory, Z parts in X memory;
the projection argument of the E-036 audit):
  D(q, r, f*)  data error on q just before reader event f* of round r (r = 0..R-1), or r = R: after the last round
               (data readout flip / final idle): reader f of q sees it first in instance j0 = min{j : tau_f + jP >
               tau_f* + rP - 1/2}, capped at R (the final readout sees it) -> toggles D(c_f, min(j0, R)).
               A data reset flip is the cut before the earliest reader of round 0.
  H(k, U, r)   spreader hook after its p-th CNOT, p = 1..4, U = time suffix, instance r = 0..R-1; same capping.
  M(c, r)      reader measurement / reset flip: D(c, r), D(c, r+1).
Mechanism list: mechs(sch, basis, R).  Patterns keep ABSOLUTE rounds.  Clauses: e038.cegar.PatternEncoder with every
detector round r + j0 capped at R (FinitePE).
"""
from __future__ import annotations

from search.experiments.e036_audit.core import observables, support
from search.experiments.e038.cegar import PatternEncoder


def mechs(s, basis, R):
    P = s.P
    readers = [k for k in s.ks if k[0] == basis]
    spreaders = [k for k in s.ks if k[0] != basis]
    ridx = {k: i for i, k in enumerate(readers)}
    L = observables(s.variant, basis)
    obsq = [sum(1 << i for i in range(len(L)) if L[i][q]) for q in range(18)]
    rev = {q: [] for q in range(18)}
    for k in readers:
        for a, q in enumerate(support(k)):
            rev[q].append((k, a))

    def bit(c, j):
        return 1 << (ridx[c] * (R + 1) + min(j, R))

    def j0(f, t2):
        return (t2 - 2 * s.tau[f]) // (2 * P) + 1

    out = []
    for r in range(R + 1):
        for q in range(18):
            for fs in rev[q]:
                t2 = 2 * (s.tau[fs] + r * P) - 1
                d = 0
                for f in rev[q]:
                    jj = j0(f, t2)
                    assert jj >= 0
                    d ^= bit(f[0], jj)
                out.append((d, obsq[q], ("D", q, fs, r)))
        if r == R:
            break
        for k in spreaders:
            order = sorted(range(6), key=lambda a: s.tau[(k, a)])
            for p in range(1, 5):
                suf = order[p:]
                d = o = 0
                for a in suf:
                    u = support(k)[a]
                    t2 = 2 * (s.tau[(k, a)] + r * P)
                    for f in rev[u]:
                        d ^= bit(f[0], j0(f, t2))
                    o ^= obsq[u]
                out.append((d, o, ("H", k, frozenset(suf), r)))
        for c in readers:
            out.append((bit(c, r) ^ bit(c, r + 1), 0, ("M", c, r)))
    return out


def pattern_abs(basis, tags):
    slots = []
    for t in tags:
        if t[0] == "D":
            slots.append(("D", t[1], t[3]))
        elif t[0] == "H":
            slots.append(("H", t[1], tuple(sorted(t[2])), t[3]))
        else:
            slots.append(("M", t[1], t[2]))
    return (basis, tuple(sorted(slots, key=repr)))


class FinitePE(PatternEncoder):
    def __init__(self, E, R):
        super().__init__(E)
        self.R = R

    def contrib(self, dets, g, f, r):
        for j0 in range(-2, 4):
            ind = self.first(g, f, j0)
            if ind is False:
                continue
            assert r + j0 >= 0 or ind is False
            dets.setdefault((f[0], min(r + j0, self.R)), []).append(ind)

    def _cap(self, dets):
        return dets

    def clauses_for_choice(self, pat, ch):
        # D slot with f* = fs toggles (fs, r): for r = R that is (fs, R) as well, no change needed.
        return super().clauses_for_choice(pat, ch)
