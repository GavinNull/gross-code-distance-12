"""Second, independent encoding (SM S16, "absolute times, one-sided difference literals"): pipelined schedules of
period P invariant under a translation subgroup H of the 24 colour-preserving translations, orders in the class of
Fig. 12; lazy frame-model nogoods (CEGAR).

Variables (order encoding).  Unit u = (type, H-orbit class); item i = (u, label) with absolute CNOT time
t_i in [0, 2P-4]; g(i, v) <=> t_i >= v.  Per unit: times distinct, window (last - first) <= P-3 (or <= maxwin for
the units in winunits), first CNOT in [0, P-1]; some CNOT of unit X0 at time 0 (global shift).  Order of each unit
in the 8-element class of its Fig. 12 order (rev Boolean + prefix/suffix sets).  Legality: on every data qubit the
six times are distinct mod P (residue literals m(i, r)).  Determinism: for X check a and Z check c sharing qubits
u, v and m in {-P, 0, P}: [t_a(u) - t_c(u) >= m] <-> [t_a(v) - t_c(v) >= m].  One-way literals le(a, b, M) imply
t_a - t_b <= M; fge(a, b, m) <-> t_a - t_b >= m.
--pin-fig12: every unit is fixed to its Fig. 12 order.
Nogoods: for every lifting logical (frame.py) the clause and its images under the 24 translations (the family and
the model are invariant under this abelian group).
"""
from __future__ import annotations

import time

from pysat.formula import IDPool

from . import frame
from .common import G24, N2, Family, bf_P, fig12_kind_data, fig12_labels, parse_sub, tr
from .recorder import RecordingSolver


class TimeSAT:
    def __init__(self, F, P, fix_first=True, maxwin=None, winunits=None):
        self.F, self.P = F, P
        self.TM = 2 * P - 4
        self.pool = IDPool()
        self.S = RecordingSolver()
        self.ncl = 0
        n = len(F.items)
        self.n = n
        for i in range(n):
            for v in range(1, self.TM):
                self.add([-self.ge(i, v + 1), self.ge(i, v)])
        self.dcache = {}
        f12 = fig12_labels()
        self.units = list(F.units)
        for u in self.units:
            its = [F.idx[(u[0], u[1], lab)] for lab in range(6)]
            for a in its:
                for b in its:
                    if a < b:
                        self.add([self.le_diff(a, b, -1), self.le_diff(b, a, -1)])
                    if a != b:
                        wl = P - 3 if (maxwin is None or (winunits is not None and u not in winunits)) else min(P - 3, maxwin)
                        self.add([self.le_diff(a, b, wl)])
            self.add([-self.ge(i, P) for i in its])
            o = f12[u[0]][F.unit_rep[u]]
            for i in range(N2):
                assert F.ucls[u[0]][i] != u[1] or f12[u[0]][i] == o, "Fig. 12 orders not H-invariant"
            rev = self.pool.id(("rev", u))
            it_ = lambda lab: F.idx[(u[0], u[1], lab)]  # noqa: E731

            def first(U, guard):
                for x in U:
                    for y in range(6):
                        if y not in U:
                            self.add(guard + [self.le_diff(it_(x), it_(y), -1)])
            first(o[:2], [rev]); first(o[:3], [rev]); first(o[:4], [rev])
            first(o[4:], [-rev]); first(o[3:], [-rev]); first(o[2:], [-rev])
        if fix_first:
            self.add([-self.ge(i, 1) for i in (F.idx[("X", 0, lab)] for lab in range(6))])
        for q in range(144):
            its = sorted({F.item(ty, c, lab) for ty, c, lab in F.touch[q]})
            assert len(its) == 6
            for x in range(6):
                for y in range(x + 1, 6):
                    for r in range(P):
                        self.add([-self.res(its[x], r), -self.res(its[y], r)])
        T = F.T
        seen = set()
        for a in range(N2):
            qa = set(int(x) for x in T["X"][a])
            for c in range(N2):
                ov = sorted(qa & set(int(x) for x in T["Z"][c]))
                if not ov:
                    continue
                assert len(ov) == 2
                pr = tuple((F.item("X", a, F.label_of("X", a, q)), F.item("Z", c, F.label_of("Z", c, q))) for q in ov)
                if pr in seen:
                    continue
                seen.add(pr)
                (x1, z1), (x2, z2) = pr
                for m in (-P, 0, P):
                    A, B = self.full_ge_diff(x1, z1, m), self.full_ge_diff(x2, z2, m)
                    if A != B:
                        self.add([-A, B]); self.add([A, -B])
        self.ndet = len(seen)

    def pin_fig12(self):
        f12 = fig12_labels()
        for u in self.units:
            o = f12[u[0]][self.F.unit_rep[u]]
            for a in range(5):
                self.add([self.le_diff(self.F.idx[(u[0], u[1], o[a])], self.F.idx[(u[0], u[1], o[a + 1])], -1)])

    def add(self, cl):
        self.S.add_clause(cl); self.ncl += 1

    def ge(self, i, v):
        if v <= 0:
            return self.true()
        if v > self.TM:
            return -self.true()
        return self.pool.id(("g", i, v))

    def true(self):
        k = ("TRUE",)
        if k not in self.pool.obj2id:
            t = self.pool.id(k)
            self.S.add_clause([t])
        return self.pool.id(k)

    def eq(self, i, v):
        k = ("e", i, v)
        if k not in self.pool.obj2id:
            e = self.pool.id(k)
            a, b = self.ge(i, v), self.ge(i, v + 1)
            self.add([-e, a]); self.add([-e, -b]); self.add([e, -a, b])
        return self.pool.id(k)

    def res(self, i, r):
        k = ("m", i, r)
        if k not in self.pool.obj2id:
            m = self.pool.id(k)
            e1 = self.eq(i, r)
            lits = [e1]
            if r + self.P <= self.TM:
                lits.append(self.eq(i, r + self.P))
            for e in lits:
                self.add([-e, m])
            self.add([-m] + lits)
        return self.pool.id(k)

    def le_diff(self, a, b, M):
        key = ("le", a, b, M)
        if key in self.dcache:
            return self.dcache[key]
        L = self.pool.id(key)
        for v in range(1, self.TM + 1):
            w = v - M
            if w <= 0:
                continue
            self.add([-L, -self.ge(a, v), self.ge(b, w)])
        if M < 0:
            self.add([-L, self.ge(b, -M)])
        self.dcache[key] = L
        return L

    def full_ge_diff(self, a, b, m):
        key = ("fge", a, b, m)
        if key in self.dcache:
            return self.dcache[key]
        L = self.pool.id(key)
        l1 = self.le_diff(b, a, -m)
        l2 = self.le_diff(a, b, m - 1)
        self.add([-L, l1]); self.add([L, l2])
        self.dcache[key] = L
        return L

    def solve(self):
        if not self.S.solve():
            return None
        pos = set(l for l in self.S.get_model() if l > 0)
        t = []
        for i in range(self.n):
            v = 0
            while v + 1 <= self.TM and self.pool.id(("g", i, v + 1)) in pos:
                v += 1
            t.append(v)
        return t


def item_perms(F):
    T = F.T
    out = []
    for g in G24:
        pr, pc = tr(*g)
        pm = {}
        for ty in "XZ":
            for i in range(N2):
                j = int(pr[i])
                for lab in range(6):
                    assert int(T[ty][j][lab]) == int(pc[int(T[ty][i][lab])])
                for lab in range(6):
                    pm[F.item(ty, i, lab)] = F.item(ty, j, lab)
        out.append([pm[i] for i in range(len(F.items))])
    return out


def run(P, sub="1,2;0,3", maxwin=None, winunits=None, pin=False, max_sec=5400, log=print):
    t0 = time.time()
    F = Family(parse_sub(sub))
    recs, skipped = frame.prepare(F, fig12_kind_data())
    M = TimeSAT(F, P, maxwin=maxwin, winunits=winunits)
    if pin:
        M.pin_fig12()
    perms = item_perms(F)
    log(f"P={P} |H|={len(F.Hs)} classes={F.nc} items={len(F.items)} reps={len(recs)} skipped={skipped} "
        f"det_pairs={M.ndet} clauses={M.ncl} vars={M.pool.top}")
    status, it = "UNKNOWN", 0
    while time.time() - t0 < max_sec:
        it += 1
        t = M.solve()
        if t is None:
            status = "UNSAT"
            break
        lif = frame.evaluate(F, recs, lambda cons: bf_P(cons, t, P))
        if not lif:
            status = "CANDIDATE"
            break
        seen_cl = set()
        for r_, cons, pi in lif:
            for pm in perms:
                lits = set()
                for (u_, w_, kd, (i1, i2)) in cons:
                    K = pi[u_] - pi[w_]
                    j1, j2 = pm[i1], pm[i2]
                    if kd in ("free", "hook+"):
                        lits.add(M.le_diff(j2, j1, (K - 1) * P - 1))
                    else:
                        lits.add(M.le_diff(j1, j2, K * P))
                cl = tuple(sorted(lits))
                if cl in seen_cl:
                    continue
                seen_cl.add(cl)
                M.add(list(cl))
        if it % 10 == 0 or it < 4:
            log({"it": it, "lifting": len(lif), "sec": round(time.time() - t0, 1)})
    info = {"status": status, "iterations": it, "sec": round(time.time() - t0, 1), "subgroup_order": len(F.Hs)}
    log(f"STATUS {status} it={it}")
    return status, M, info
