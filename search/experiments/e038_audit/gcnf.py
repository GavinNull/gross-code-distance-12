"""E-038 audit: my own CNF for a periodic class with fixed per-check event windows (covers N(S) and V(P, delta)).

Class W(P, lo, hi): every event of check k at an absolute time tau in [lo[k], hi[k]] (hi - lo <= P - 3 so that prep
at lo - 1 and meas at hi + 1 fit in one period), distinct per check, distinct mod P per data qubit, determinism
parity for every X/Z pair and every instance shift.  N(S): lo = 1, hi = S, P = S + 2.  V(P, d): X checks [1, P - 2],
Z checks [d + 1, d + P - 2].  (Prep / meas times only need pi < tau < mu, mu - pi <= P - 1; with fixed type-wise prep
pi = 0 / d the windows above are exactly the allowed event times.)
Variables: one-hot x[e, t]; for ordered pairs (g, f) on one data qubit: J[g, f, j] <-> "first instance of f strictly
after g is j" = min{j : tau_f + jP > tau_g}; for pairs in one check: o[a, b] <-> tau_a < tau_b.
Pattern clauses from my semantics (gpat.GSem): D(q, r) with reader f*: f* toggles (f*, r), other readers f toggle
(f, r + J[f*, f]); H(k, U, r): suffix literals, each u in U, reader f toggles (f, r + J[(k,u), f]); M toggles (c,r),
(c,r+1)."""
from __future__ import annotations

import itertools

from search.experiments.e038_audit import acore as C


class GCNF:
    def __init__(self, P, lo, hi, meas=C.MEASURED):
        self.P = P
        self.nv = 0
        self.cl = []
        self.ks = C.check_list(meas)
        self.lo, self.hi = lo, hi
        self.ev = [(k, q) for k in self.ks for q in C.supp(k)]
        self.x = {e: {t: self.new() for t in range(lo[e[0]], hi[e[0]] + 1)} for e in self.ev}
        for e in self.ev:
            v = list(self.x[e].values())
            self.cl.append(v)
            for a, b in itertools.combinations(v, 2):
                self.cl.append([-a, -b])
        # distinct within a check (plain), within a qubit (mod P)
        for k in self.ks:
            for q1, q2 in itertools.combinations(C.supp(k), 2):
                self._forbid((k, q1), (k, q2), lambda t1, t2: t1 == t2)
        self.onq = {q: [e for e in self.ev if e[1] == q] for q in range(18)}
        for q, evs in self.onq.items():
            for e1, e2 in itertools.combinations(evs, 2):
                self._forbid(e1, e2, lambda t1, t2: (t1 - t2) % P == 0)
        self.o = {}
        for k in self.ks:
            for q1, q2 in itertools.permutations(C.supp(k), 2):
                self.o[((k, q1), (k, q2))] = self._rel((k, q1), (k, q2), lambda t1, t2: t1 < t2)
        self.J = {}
        for q, evs in self.onq.items():
            for g, f in itertools.permutations(evs, 2):
                vals = {}
                for t1 in self.x[g]:
                    for t2 in self.x[f]:
                        if (t1 - t2) % P == 0:
                            continue
                        vals.setdefault(self.jfun(t1, t2), []).append((t1, t2))
                for j in vals:
                    self.J[(g, f, j)] = self._rel(g, f, lambda t1, t2, j=j: (t1 - t2) % P != 0 and self.jfun(t1, t2) == j)
        # determinism parity: for every shift i, #{q in shared : tau_x < tau_z + iP} even
        for kx in self.ks:
            if kx[0] != "X":
                continue
            for kz in self.ks:
                if kz[0] != "Z":
                    continue
                sh = sorted(set(C.supp(kx)) & set(C.supp(kz)))
                if not sh:
                    continue
                for i in range(-4, 5):
                    lits = []
                    const = 0
                    for q in sh:
                        ex, ez = (kx, q), (kz, q)
                        always = all(t1 < t2 + i * P for t1 in self.x[ex] for t2 in self.x[ez])
                        never = all(not (t1 < t2 + i * P) for t1 in self.x[ex] for t2 in self.x[ez])
                        if always:
                            const ^= 1
                        elif not never:
                            lits.append(self._rel(ex, ez, lambda t1, t2, i=i: t1 < t2 + i * P))
                    if not lits:
                        assert const == 0, ("parity impossible", kx, kz, i)
                        continue
                    for signs in itertools.product([0, 1], repeat=len(lits)):
                        if (sum(signs) + const) % 2:
                            self.cl.append([(-l if s else l) for l, s in zip(lits, signs)])
        self.nleg = len(self.cl)
        self.xc = {}

    def jfun(self, tg, tf):
        """min j with tf + jP > tg."""
        return (tg - tf) // self.P + 1

    def new(self):
        self.nv += 1
        return self.nv

    def _forbid(self, e1, e2, bad):
        for t1, v1 in self.x[e1].items():
            for t2, v2 in self.x[e2].items():
                if bad(t1, t2):
                    self.cl.append([-v1, -v2])

    def _rel(self, e1, e2, pred):
        v = self.new()
        for t1, v1 in self.x[e1].items():
            for t2, v2 in self.x[e2].items():
                self.cl.append([-v1, -v2, v if pred(t1, t2) else -v])
        return v

    def xor(self, lits):
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

    def pattern_clauses(self, readers, pat):
        b, slots = pat
        out = []
        dslots = [s for s in slots if s[0] == "D"]
        for ch in itertools.product(*[readers[b][s[1]] for s in dslots]):
            cond = []
            terms = {}
            di = 0
            for s in slots:
                if s[0] == "D":
                    _, q, r = s
                    fs = ch[di]
                    di += 1
                    for f in readers[b][q]:
                        if f == fs:
                            terms.setdefault((f, r), []).append(True)
                        else:
                            for (g_, f_, j), lit in self._Jof((fs, q), (f, q)):
                                terms.setdefault((f, r + j), []).append(lit)
                elif s[0] == "H":
                    _, k, U, r = s
                    for x_ in C.supp(k):
                        if x_ not in U:
                            for u in U:
                                cond.append(self.o[((k, x_), (k, u))])
                    for u in U:
                        for f in readers[b][u]:
                            for (g_, f_, j), lit in self._Jof((k, u), (f, u)):
                                terms.setdefault((f, r + j), []).append(lit)
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

    def _Jof(self, g, f):
        return [((g, f, j), v) for (gg, ff, j), v in self.J.items() if gg == g and ff == f]

    def index_J(self):
        idx = {}
        for (g, f, j), v in self.J.items():
            idx.setdefault((g, f), []).append(((g, f, j), v))
        self._Jof = lambda g, f: idx.get((g, f), [])

    def decode(self, model):
        pos = set(l for l in model if l > 0)
        return {e: next(t for t, v in self.x[e].items() if v in pos) for e in self.ev}


def nclass(S, meas=C.MEASURED):
    ks = C.check_list(meas)
    G = GCNF(S + 2, {k: 1 for k in ks}, {k: S for k in ks}, meas)
    G.index_J()
    return G


def vclass(P, d, meas=C.MEASURED):
    ks = C.check_list(meas)
    lo = {k: 1 if k[0] == "X" else d + 1 for k in ks}
    hi = {k: P - 2 if k[0] == "X" else d + P - 2 for k in ks}
    G = GCNF(P, lo, hi, meas)
    G.index_J()
    return G
