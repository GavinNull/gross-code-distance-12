"""Primary encoding (SM S16, "Search"): schedules symmetric under a translation subgroup, CNOT orders in the
8-element class <rev, s12, s56> of given per-colour orders, period P; lazy frame-model nogoods (CEGAR).

Family: unit u = (type, class).  Start s_u in [0, P) (0 for the common frame), the six CNOTs at absolute times
t = s_u + o with o in [1, P-2] distinct, measurement at s_u + P - 1.  The unit's order is one of the 8 orders of its
class (Boolean rev + "first-set" constraints).  Legality: on every data qubit the six CNOT times are distinct mod P.
Determinism: for every X check and Z check sharing two qubits, floor((t_x - t_z)/P) is equal on both.
Encoding: one-hot x(i, v) <=> t_i = v, order literals ge(i, k) <=> t_i >= k, difference literals
D(i, j, M) <=> t_j - t_i >= M (defined both ways).  s(X, class 0) = 0 (global time shift).
--pin-fig12: every unit is additionally fixed to its Fig. 12 order (t of each label < t of the next label).
CEGAR: solve; compute the frame model at the model's times; for every lifting logical add its nogood; repeat.
UNSAT  =>  every legal deterministic circuit of the family has a weight-11 undetected error for sufficiently many
rounds.  A model with no lifting logical is reported as CANDIDATE (it must then be checked exactly).
"""
from __future__ import annotations

import itertools
import time

from pysat.formula import IDPool

from . import frame
from .common import N2, Family, bf_P, build_kind_data, colour, fig12_labels, kernel, parse_orders, parse_sub, table
from .recorder import RecordingSolver


class Enc:
    def __init__(self, F, orders, ccol, P, nowrap):
        self.F, self.P = F, P
        self.pool = IDPool()
        self.S = RecordingSolver()
        self.units = [(ty, k) for ty in "XZ" for k in range(F.nc)]
        hi = P - 2 if nowrap else 2 * P - 2
        self.dom = list(range(1, hi + 1))
        self.lo, self.hi = 1, hi
        n = len(F.items)
        self.x = {(i, v): self.pool.id(("x", i, v)) for i in range(n) for v in self.dom}
        S = self.S
        for i in range(n):
            S.add_clause([self.x[(i, v)] for v in self.dom])
            for v, w in itertools.combinations(self.dom, 2):
                S.add_clause([-self.x[(i, v)], -self.x[(i, w)]])
            for k in range(self.lo + 1, self.hi + 1):
                g = self.ge(i, k)
                for v in self.dom:
                    if v >= k:
                        S.add_clause([-self.x[(i, v)], g])
                    else:
                        S.add_clause([-self.x[(i, v)], -g])
        sdom = [0] if nowrap else list(range(P))
        self.s = {(u, w): self.pool.id(("s", u, w)) for u in self.units for w in sdom}
        for u in self.units:
            S.add_clause([self.s[(u, w)] for w in sdom])
            for w1, w2 in itertools.combinations(sdom, 2):
                S.add_clause([-self.s[(u, w1)], -self.s[(u, w2)]])
            its = [F.idx[(u[0], u[1], l)] for l in range(6)]
            for i in its:
                for v in self.dom:
                    S.add_clause([-self.x[(i, v)]] + [self.s[(u, w)] for w in sdom if 1 <= v - w <= P - 2])
            for i, j in itertools.combinations(its, 2):
                for v in self.dom:
                    S.add_clause([-self.x[(i, v)], -self.x[(j, v)]])
            ordr = orders[u[0]][ccol[u[1]]]
            rev = self.pool.id(("rev", u))
            it_ = lambda lab: F.idx[(u[0], u[1], lab)]  # noqa: E731

            def first(U, guard):
                for a in U:
                    for b in range(6):
                        if b not in U:
                            S.add_clause(guard + [self.D(it_(a), it_(b), 1)])
            first(ordr[:2], [rev]); first(ordr[:3], [rev]); first(ordr[:4], [rev])
            first(ordr[4:], [-rev]); first(ordr[3:], [-rev]); first(ordr[2:], [-rev])
        S.add_clause([self.s[(("X", 0), 0)]])
        pairs = set()
        for q in range(144):
            its = sorted({F.item(ty, c, lab) for ty, c, lab in F.touch[q]})
            assert len(its) == 6
            pairs.update(itertools.combinations(its, 2))
        for i, j in pairs:
            for v in self.dom:
                for w in self.dom:
                    if (v - w) % P == 0:
                        S.add_clause([-self.x[(i, v)], -self.x[(j, w)]])
        T = table()
        seen = set()
        for ia in range(N2):
            qa = set(int(q) for q in T["X"][ia])
            for ic in range(N2):
                ov = sorted(qa & set(int(q) for q in T["Z"][ic]))
                if not ov:
                    continue
                pr = tuple((F.item("X", ia, F.label_of("X", ia, q)), F.item("Z", ic, F.label_of("Z", ic, q)))
                           for q in ov)
                if pr in seen:
                    continue
                seen.add(pr)
                (x1, z1), (x2, z2) = pr
                for k in (-1, 0, 1):
                    a, b = self.D(z1, x1, k * P), self.D(z2, x2, k * P)
                    S.add_clause([-a, b]); S.add_clause([a, -b])
        self.ndet = len(seen)

    def pin_fig12(self):
        f12 = fig12_labels()
        for ty, k in self.units:
            o = f12[ty][self.F.reps[k]]
            assert all(f12[ty][i] == o for i in range(N2) if self.F.cls[i] == k), "Fig. 12 orders not invariant"
            for a in range(5):
                self.S.add_clause([self.D(self.F.idx[(ty, k, o[a])], self.F.idx[(ty, k, o[a + 1])], 1)])

    def ge(self, i, k):
        return self.pool.id(("ge", i, k))

    def gelit(self, i, k):
        if k <= self.lo:
            return True
        if k > self.hi:
            return False
        return self.ge(i, k)

    def D(self, i, j, M):
        """literal <=> t_j - t_i >= M"""
        key = ("D", i, j, M)
        if key in self.pool.obj2id:
            return self.pool.obj2id[key]
        d = self.pool.id(key)
        for v in self.dom:
            g = self.gelit(j, v + M)
            xv = self.x[(i, v)]
            if g is True:
                self.S.add_clause([-xv, d])
            elif g is False:
                self.S.add_clause([-xv, -d])
            else:
                self.S.add_clause([-xv, -g, d]); self.S.add_clause([-xv, g, -d])
        return d

    def times(self, model):
        ms = set(l for l in model if l > 0)
        return {i: v for (i, v), var in self.x.items() if var in ms}


def run(P, nowrap=0, col=(3, 1, 1), xs="A1A2A3B3B1B2,A1A2A3B1B2B3,A1A3A2B3B1B2",
        zs="A1A3A2B3B1B2,A1A2A3B1B2B3,A1A2A3B3B1B2", sub=None, pin=False, max_sec=3600, log=print):
    """returns (status, encoder, info).  Defaults: colouring (a + b) mod 3 with the canonical per-colour orders of
    the Fig. 12 class; sub = generators of a finer subgroup (e.g. "0,0" = no symmetry)."""
    t0 = time.time()
    orders = {"X": parse_orders(xs), "Z": parse_orders(zs)}
    if sub is not None:
        F = Family(parse_sub(sub))
        ccol = [colour(col, F.reps[k]) for k in range(F.nc)]
    else:
        F = Family(kernel(col))
        assert F.nc == col[0]
        ccol = [colour(col, F.reps[k]) for k in range(F.nc)]
    for i in range(N2):
        assert colour(col, i) == ccol[F.cls[i]]
    recs, skipped = frame.prepare(F, build_kind_data(col, orders))
    M = Enc(F, orders, ccol, P, nowrap)
    if pin:
        M.pin_fig12()
    log(f"P={P} common_frame={nowrap} classes={F.nc} logical reps={len(recs)} skipped={skipped} "
        f"det pairs={M.ndet} vars={M.pool.top}")
    status, it, nog = "UNKNOWN", 0, 0
    while time.time() - t0 < max_sec:
        it += 1
        if not M.S.solve():
            status = "UNSAT"
            break
        t = M.times(M.S.get_model())
        lif = frame.evaluate(F, recs, lambda cons: bf_P(cons, t, P))
        if not lif:
            status = "CANDIDATE"
            break
        for r_, cons, pi in lif:
            lits = set()
            for u_, w_, kd, (i1, i2) in cons:
                K = pi[u_] - pi[w_]
                if kd in ("free", "hook+"):
                    lits.add(-M.D(i1, i2, (K - 1) * P))
                else:
                    lits.add(M.D(i1, i2, -K * P))
            M.S.add_clause(sorted(lits))
            nog += 1
        if it % 50 == 0 or it < 3:
            log({"it": it, "lifting": len(lif), "nogoods": nog, "sec": round(time.time() - t0, 1)})
    info = {"status": status, "iterations": it, "nogoods": nog, "sec": round(time.time() - t0, 1)}
    log(f"STATUS {status} it={it}")
    return status, M, info
