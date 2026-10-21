"""E-032 (copy of e028/frame.py, gross via e032.common; generic d_ext extension at the end): bulk frame model + incremental-SAT timing CEGAR for [[90,8,10]] (port of e021/nwsat.Family, e021/nwfull
(column_real, skeleton, evaluate_full), e024b/gen (prepare, bf_P) and e024b/gsat (Enc, spec_of); audited methods:
frame-model soundness E-020/E-018 audit C1, nogood validity E-021 audit, gsat encoding E-024b audit).  Only the code
(tables, translations, sizes) changes.

Family F(Hs): Hs <= translation group; units = (type, Hs-orbit of checks); per unit a start s_u in [0,P) (0 if nowrap),
6 CNOT times t = s_u + o, o in [1, P-2] distinct, measurement at s_u + P - 1; per unit any of the 8 orders of the
unit's extended-code type.  Legal: the 6 times on each data qubit distinct mod P.  Deterministic: floor((t_x-t_z)/P)
equal on the two shared qubits of every overlapping X/Z pair.
Logicals: complete weight-9 extended-logical lists (by (H,L) keys); a record per Hs-orbit representative; columns
realised as free data errors or as hooks pinned at the hook check's CNOT times (smaller side of U / a\\U);
weight of a "free/hook+" edge = floor((t_i2 - t_i1)/P) + 1.  A logical "lifts" in the model <=> no negative cycle
=> genuine bulk weight-9 undetected logical.  Nogood = OR of violating difference literals.
"""
from __future__ import annotations

import itertools
import json

from pysat.formula import IDPool
from pysat.solvers import Cadical153

from search.experiments.e032 import common as C

N2, NQ = C.N2, C.NQ


def subgroup(gens):
    H = {(0, 0)}
    while True:
        N = H | {((h[0] + g[0]) % C.L_, (h[1] + g[1]) % C.M_) for h in H for g in gens}
        if N == H:
            return sorted(H)
        H = N


class Family:
    def __init__(self, gens):
        self.Hs = subgroup(gens)
        self.T = C.table()
        cls = [-1] * N2
        reps = []
        for i in range(N2):
            if cls[i] >= 0:
                continue
            for h in self.Hs:
                pr, _ = C.tr(*h)
                cls[int(pr[i])] = len(reps)
            reps.append(i)
        self.cls, self.reps = cls, reps
        self.nc = len(reps)
        self.items = [(ty, k, lab) for ty in "XZ" for k in range(self.nc) for lab in range(6)]
        self.idx = {it: n for n, it in enumerate(self.items)}
        self.touch = [[] for _ in range(NQ)]
        for ty in "XZ":
            for i in range(N2):
                for lab in range(6):
                    self.touch[int(self.T[ty][i][lab])].append((ty, i, lab))

    def item(self, ty, check, lab):
        return self.idx[(ty, self.cls[check], lab)]

    def label_of(self, ty, check, q):
        return int(list(self.T[ty][check]).index(q))


def pairings(lst):
    if not lst:
        yield []
        return
    for k in range(1, len(lst)):
        for p in pairings(lst[1:k] + lst[k + 1:]):
            yield [(lst[0], lst[k])] + p


def column_real(F, kind, E, j):
    sups = E["col_sups"][j]
    for s in sups:
        if len(s) == 1:
            return ("d", s[0])
    s = set(sups[0])
    for a in range(N2):
        qa = set(int(q) for q in F.T[kind][a])
        if s <= qa:
            V = s if len(s) <= 3 else qa - s
            return ("h", a, tuple(sorted(V)))
    raise AssertionError


def prepare(F, E_by_kind, sols_by_kind, kinds="XZ"):
    """records for Hs-orbit representatives of each side's complete weight-9 list (column indices of E)."""
    recs, skipped = [], 0
    Hs = set(F.Hs)
    for kind in kinds:
        rd = "Z" if kind == "X" else "X"
        E = E_by_kind[kind]
        perms = [P for g, P in zip(E["group"], E["perms"]) if tuple(g) in Hs]
        assert len(perms) == len(Hs), "Hs must preserve the circuit class (sub-group of the class group)"
        seen, reps = set(), []
        for S in sols_by_kind[kind]:
            if S in seen:
                continue
            for P in perms:
                seen.add(tuple(sorted(int(P[j]) for j in S)))
            reps.append(S)
        for S in reps:
            evs = [column_real(F, kind, E, j) for j in S]
            qs = []
            for e in evs:
                qs += [e[1]] if e[0] == "d" else list(e[2])
            if len(set(qs)) != len(qs):
                skipped += 1
                continue
            rc = {}
            for q in qs:
                for ty, c, lab in F.touch[q]:
                    if ty == rd:
                        rc.setdefault(c, []).append(q)
            assert all(len(v) % 2 == 0 for v in rc.values())
            recs.append({"kind": kind, "S": tuple(int(j) for j in S), "evs": evs, "rc": rc, "rd": rd})
    return recs, skipped


def skeleton(F, r, cls):
    kind, rd = r["kind"], r["rd"]
    cons = []
    for e in r["evs"]:
        if e[0] == "d":
            q = e[1]
            rds = [(cls[(c, q)], F.item(rd, c, lab)) for ty, c, lab in F.touch[q] if ty == rd]
            for (nc, ic), (nd, idd) in itertools.permutations(rds, 2):
                cons.append((nc, nd, "free", (ic, idd)))
        else:
            a = e[1]
            Fn = ("F", a)
            for q in e[2]:
                ia = F.item(kind, a, F.label_of(kind, a, q))
                for ty, c, lab in F.touch[q]:
                    if ty != rd:
                        continue
                    ic = F.item(rd, c, lab)
                    cons.append((cls[(c, q)], Fn, "hook+", (ic, ia)))
                    cons.append((Fn, cls[(c, q)], "hook-", (ic, ia)))
    return cons


def bf_P(cons, t, P):
    nodes, edges = {}, []
    for u, w, kd, (i1, i2) in cons:
        iu = nodes.setdefault(u, len(nodes)); iw = nodes.setdefault(w, len(nodes))
        f = (t[i2] - t[i1]) // P + 1
        edges.append((iu, iw, f if kd != "hook-" else -f))
    d = [0] * len(nodes)
    for _ in range(len(nodes) + 1):
        ch = False
        for iu, iw, wt in edges:
            if d[iw] + wt < d[iu]:
                d[iu] = d[iw] + wt; ch = True
        if not ch:
            return {k: d[i] for k, i in nodes.items()}
    return None


def evaluate(F, recs, t, P, first_only=False):
    out = []
    for r in recs:
        rc = r["rc"]
        multi = [c for c, l in rc.items() if len(l) > 2]
        for choice in itertools.product(*[list(pairings(sorted(rc[c]))) for c in multi]):
            cls = {}
            for c, l in rc.items():
                if len(l) == 2:
                    cls[(c, l[0])] = cls[(c, l[1])] = ("c", c, 0)
            for c, prs in zip(multi, choice):
                for k, (x, y) in enumerate(prs):
                    cls[(c, x)] = cls[(c, y)] = ("c", c, k)
            cons = skeleton(F, r, cls)
            pi = bf_P(cons, t, P)
            if pi is not None:
                out.append((r, cons, pi))
                break
        if first_only and out:
            break
    return out


class Enc:
    """gsat encoding (E-024b, audited) for family F, unit orders `uord[(ty, k)]` (canonical order of the unit's type)."""

    def __init__(self, F, uord, P, nowrap, win=None):
        self.F, self.P = F, P
        self.pool = IDPool()
        self.S = Cadical153()
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
                    S.add_clause([-self.x[(i, v)], g] if v >= k else [-self.x[(i, v)], -g])
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
            ordr = uord[u]
            rev = self.pool.id(("rev", u))
            it_ = lambda lab: F.idx[(u[0], u[1], lab)]  # noqa: E731

            def first(U, guard):
                for a in U:
                    for b in range(6):
                        if b not in U:
                            S.add_clause(guard + [self.D(it_(a), it_(b), 1)])
            first(ordr[:2], [rev]); first(ordr[:3], [rev]); first(ordr[:4], [rev])
            first(ordr[4:], [-rev]); first(ordr[3:], [-rev]); first(ordr[2:], [-rev])
            if win is not None and u in win:   # optional window limit: last CNOT - first CNOT <= win[u]
                for a_, b_ in itertools.permutations(its, 2):
                    S.add_clause([-self.D(a_, b_, win[u] + 1)])
        S.add_clause([self.s[(("X", 0), 0)]])
        pairs = set()
        for q in range(NQ):
            its = sorted({F.item(ty, c, lab) for ty, c, lab in F.touch[q]})
            assert len(its) == 6
            pairs.update(itertools.combinations(its, 2))
        for i, j in pairs:
            for v in self.dom:
                for w in self.dom:
                    if (v - w) % P == 0:
                        S.add_clause([-self.x[(i, v)], -self.x[(j, w)]])
        T = C.table()
        seen = set()
        for ia in range(N2):
            qa = set(int(q) for q in T["X"][ia])
            for ic in range(N2):
                ov = sorted(qa & set(int(q) for q in T["Z"][ic]))
                if not ov:
                    continue
                assert len(ov) == 2
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
        t = {i: v for (i, v), var in self.x.items() if var in ms}
        st = {u: w for (u, w), var in self.s.items() if var in ms}
        return t, st

    def nogood(self, cons, pi):
        P = self.P
        lits = set()
        for u_, w_, kd, (i1, i2) in cons:
            K = pi[u_] - pi[w_]
            if kd in ("free", "hook+"):
                lits.add(-self.D(i1, i2, (K - 1) * P))       # t_i2 - t_i1 <= (K-1)P - 1
            else:
                lits.add(self.D(i1, i2, -K * P))              # t_i2 - t_i1 >= -KP
        self.S.add_clause(sorted(lits))


def spec_of(F, t, st, P):
    T = C.table()
    d = {"format": "qec-schedule/v1", "period": P, "x_checks": [], "z_checks": []}
    for ty, key in (("X", "x_checks"), ("Z", "z_checks")):
        for i in range(N2):
            u = (ty, F.cls[i])
            sv = st[u]
            cn = [[int(T[ty][i][l]), t[F.idx[(ty, F.cls[i], l)]] % P] for l in range(6)]
            d[key].append({"prep": sv % P, "meas": (sv + P - 1) % P, "cnots": cn})
    return d


# ------------------------------------------------------------------ weight d_ext + 1 = 9 with d_ext = 8 (E-028 ext.)
# A weight-9 undetected logical is either 9 distinct columns (weight-9 list, standard record) or a weight-8 extended
# logical + one zero-image fault.  In the memory basis the zero-image faults are measurement flips of the reader
# checks (they flip one syndrome readout).  A reader whose two error qubits are seen in consecutive rounds (potentials
# differing by exactly 1) produces two flips of consecutive comparison detectors = one readout flip, cancelled by one
# measurement error.  Model ("split"): for ONE reader pairing node, its two qubits get separate nodes with
# |H_a - H_b| <= 1 (constant edges, carry no literal).  Feasible => the weight-8 logical lifts with <= 9 faults.

def skeleton_split(F, r, cls, split_node):
    """as skeleton, but the two qubits of pairing node `split_node` get nodes split_node+('a',) / +('b',)."""
    cls2 = dict(cls)
    qs = sorted(q for (c, q), nd in cls.items() if nd == split_node)
    assert len(qs) == 2
    c0 = next(c for (c, q), nd in cls.items() if nd == split_node)
    cls2[(c0, qs[0])] = split_node + ("a",)
    cls2[(c0, qs[1])] = split_node + ("b",)
    cons = skeleton(F, r, cls2)
    cons.append((split_node + ("a",), split_node + ("b",), "const1", None))
    cons.append((split_node + ("b",), split_node + ("a",), "const1", None))
    return cons


def bf_P2(cons, t, P):
    nodes, edges = {}, []
    for u, w, kd, it in cons:
        iu = nodes.setdefault(u, len(nodes)); iw = nodes.setdefault(w, len(nodes))
        if kd == "const1":
            edges.append((iu, iw, 1)); continue
        i1, i2 = it
        f = (t[i2] - t[i1]) // P + 1
        edges.append((iu, iw, f if kd != "hook-" else -f))
    d = [0] * len(nodes)
    for _ in range(len(nodes) + 1):
        ch = False
        for iu, iw, wt in edges:
            if d[iw] + wt < d[iu]:
                d[iu] = d[iw] + wt; ch = True
        if not ch:
            return {k: d[i] for k, i in nodes.items()}
    return None


def evaluate9(F, recs8, recs9, t, P):
    """lifting records: weight-8 (exact), weight-8 + one readout flip (split), weight-9 (exact)."""
    out = []
    for r in recs8:
        rc = r["rc"]
        multi = [c for c, l in rc.items() if len(l) > 2]
        done = False
        for choice in itertools.product(*[list(pairings(sorted(rc[c]))) for c in multi]):
            cls = {}
            for c, l in rc.items():
                if len(l) == 2:
                    cls[(c, l[0])] = cls[(c, l[1])] = ("c", c, 0)
            for c, prs in zip(multi, choice):
                for k, (x, y) in enumerate(prs):
                    cls[(c, x)] = cls[(c, y)] = ("c", c, k)
            cons = skeleton(F, r, cls)
            pi = bf_P2(cons, t, P)
            if pi is not None:
                out.append((r, cons, pi, "w8")); done = True; break
            for nd in sorted(set(cls.values())):
                cons = skeleton_split(F, r, cls, nd)
                pi = bf_P2(cons, t, P)
                if pi is not None:
                    out.append((r, cons, pi, "w8z")); done = True; break
            if done:
                break
    for r, cons, pi in evaluate(F, recs9, t, P):
        out.append((r, cons, pi, "w9"))
    return out


def nogood2(M, cons, pi):
    P = M.P
    lits = set()
    for u_, w_, kd, it in cons:
        if kd == "const1":
            continue
        i1, i2 = it
        K = pi[u_] - pi[w_]
        if kd in ("free", "hook+"):
            lits.add(-M.D(i1, i2, (K - 1) * P))
        else:
            lits.add(M.D(i1, i2, -K * P))
    M.S.add_clause(sorted(lits))


# ------------------------------------------------------------------ E-032: generic d_ext + 1 with d_ext = 10 (gross)
def evaluate_ext(F, recsA, recsB, t, P):
    """weight-d_ext list (exact one fault per column), weight-d_ext + one readout flip (split), weight-(d_ext+1)
    list.  Tags w10 / w10z / w11 for d_ext = 10 (evaluate9 is code-agnostic; only its tag names say 8/9)."""
    ren = {"w8": "w10", "w8z": "w10z", "w9": "w11"}
    return [(r, cons, pi, ren[k]) for r, cons, pi, k in evaluate9(F, recsA, recsB, t, P)]
