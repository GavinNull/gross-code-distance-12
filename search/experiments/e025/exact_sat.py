"""E-025 method (B): EXACT lazy-logical solver, pure incremental SAT (CaDiCaL via pysat), on top of the e024a TimeSAT
base encoding (absolute times, order encoding; legality, determinism, window <= P-3, Fig. 12 8-element order class,
unit first CNOT <= P-1, X unit 0 first CNOT = 0).  Same family / meaning as e025.exact_cp.

Exact 'blocked' encoding of one pairing of a modelled logical (frame-model system H_u - H_w <= wt_e infeasible):
  y_e (edge w -> u selected), every node: in-degree = out-degree <= 1 (vertex-disjoint cycles), and
     sum_e y_e wt_e <= -1,  wt_e = s_e (-1 + I1 + I2 + I3),  Ik = [t_i2 - t_i1 >= m_k], m = (-P, 0, P)
     (1 + floor(dt/P) = -1 + I1 + I2 + I3 because |dt| <= 2P-4; constant indicators removed).
  A union of vertex-disjoint cycles with negative total contains a negative cycle (sound); a negative simple cycle is
  such a union (complete).  With p_ek = y_e AND Ik (one-sided: >= for s=+1 terms, <= for s=-1 terms):
     1 + A+ + Y-  <=  Y+ + A-      (A+ = sum p over s=+1 edges, Y- = sum y over s=-1 edges, ...)
  encoded by two one-directional totalizers (LHS 'at least j' upward, RHS 'at least j' downward) and L_j -> R_j.
Each logical has a selector literal (assumption) -> MUS / core extraction over logicals.
Lazy loop as exact_cp; every round asserts that no already-added logical lifts (self-check of the encoding).

    PYTHONPATH=.:tests uv run python -m search.experiments.e025.exact_sat --P 17 --sub "1,2;0,3"
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import search.experiments.e021.nwfull as NF
from search.experiments.e024a.cegar import TimeSAT, spec_of
from search.experiments.e025.cyc import pairing_classes, rec_cycles, blocked
from search.experiments.e025.exact_cp import make_family

OUT = Path("results/E-025-gross12-perchk-period")


class ExactSAT(TimeSAT):
    def __init__(self, F, P, **kw):
        super().__init__(F, P, **kw)
        self.unit_of = [(it[0], it[1]) for it in F.items]
        self.sel = {}

    def new(self):
        return self.pool._next()     # anonymous aux variable (no dict entry)

    def indicators(self, i1, i2):
        """(const, [literals]) with 1 + floor((t_i2 - t_i1)/P) = const + sum(literals)."""
        P = self.P
        if i1 == i2:
            return 1, []
        if self.unit_of[i1] == self.unit_of[i2]:
            lo, hi = -(P - 3), P - 3
        else:
            lo, hi = -(2 * P - 4), 2 * P - 4
        const, lits = -1, []
        for m in (-P, 0, P):
            if lo >= m:
                const += 1
            elif hi < m:
                pass
            else:
                lits.append(self.full_ge_diff(i2, i1, m))
        return const, lits

    def tot_up(self, xs, cap):
        """outputs o[1..cap]: (#true xs >= j) -> o[j]  (only this direction)."""
        if not xs:
            return []
        if len(xs) == 1:
            return [xs[0]]
        h = len(xs) // 2
        a, b = self.tot_up(xs[:h], cap), self.tot_up(xs[h:], cap)
        n = min(cap, len(a) + len(b))
        o = [self.new() for _ in range(n)]
        for i in range(len(a) + 1):
            for j in range(len(b) + 1):
                if i + j == 0:
                    continue
                k = min(i + j, n)
                cl = [o[k - 1]]
                if i:
                    cl.append(-a[i - 1])
                if j:
                    cl.append(-b[j - 1])
                self.add(cl)
        return o

    def tot_down(self, xs, cap):
        """outputs o[1..cap]: o[j] -> (#true xs >= j)."""
        if not xs:
            return []
        if len(xs) == 1:
            return [xs[0]]
        h = len(xs) // 2
        a, b = self.tot_down(xs[:h], cap), self.tot_down(xs[h:], cap)
        n = min(cap, len(a) + len(b))
        o = [self.new() for _ in range(n)]
        # o[k] (k = i + j + 1) -> a[i+1] or b[j+1]   for all i <= len(a), j <= len(b), i + j + 1 <= n
        for i in range(len(a) + 1):
            for j in range(len(b) + 1):
                k = i + j + 1
                if k > n:
                    continue
                cl = [-o[k - 1]]
                if i < len(a):
                    cl.append(a[i])
                if j < len(b):
                    cl.append(b[j])
                self.add(cl)
        return o

    def add_pairing(self, cons, guard):
        """guard -> this pairing's constraint system is infeasible."""
        ins, outs, nodes = {}, {}, set()
        lhs, rhs = [], []
        const_l = 1          # LHS constant (the '+1')
        nF = 0
        for (u, w, kd, (i1, i2)) in cons:
            y = self.new()
            ins.setdefault(u, []).append(y)
            outs.setdefault(w, []).append(y)
            nodes.add(u); nodes.add(w)
            c, ls = self.indicators(i1, i2)
            s = -1 if kd == "hook-" else 1
            # contribution s*y*(c + sum ls); move to "lhs <= rhs" form of  sum contrib <= -1
            if s == 1:
                # y*c + sum(y&l) : positive part -> lhs ; c may be -1,0,1,2
                if c < 0:
                    rhs.extend([y] * (-c))
                else:
                    lhs.extend([y] * c)
                for l in ls:
                    p = self.new()
                    self.add([-y, -l, p])          # p >= y & l
                    lhs.append(p)
            else:
                nF += 1
                if c < 0:
                    lhs.extend([y] * (-c))
                else:
                    rhs.extend([y] * c)
                for l in ls:
                    p = self.new()
                    self.add([-p, y]); self.add([-p, l])   # p <= y & l
                    rhs.append(p)
        for v in nodes:
            a_, b_ = ins.get(v, []), outs.get(v, [])
            for L in (a_, b_):
                for i in range(len(L)):
                    for j in range(i + 1, len(L)):
                        self.add([-guard, -L[i], -L[j]])
            # any in <-> any out
            for x in a_:
                self.add([-guard, -x] + b_)
            for x in b_:
                self.add([-guard, -x] + a_)
        # rhs <= nodes + 3 * (#selected hook- edges) <= len(nodes) + 3 * nF
        rmax = min(len(rhs), len(nodes) + 3 * nF)
        cap = rmax + 1
        L = self.tot_up(lhs, cap)
        R = self.tot_down(rhs, cap)
        # need const_l + #lhs <= #rhs :  for j: (#lhs >= j) -> (#rhs >= j + const_l)
        for j in range(0, cap + 1):
            need = j + const_l
            pre = [-guard] + ([-L[j - 1]] if j >= 1 else [])
            if j >= 1 and j > len(L):
                break
            if need > len(R):
                self.add(pre)              # impossible
            else:
                self.add(pre + [R[need - 1]])

    def add_logical(self, k, r):
        g = self.pool.id(("sel", k))
        self.sel[k] = g
        for cls in pairing_classes(r):
            self.add_pairing(NF.skeleton(self.F, r, cls), g)
        return g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--sub", default="1,2;0,3")
    ap.add_argument("--split_units", default="")
    ap.add_argument("--max_sec", type=float, default=3600)
    ap.add_argument("--rmax", type=int, default=6)
    ap.add_argument("--maxwin", type=int, default=None)
    ap.add_argument("--winunits", default="")
    ap.add_argument("--all", type=int, default=0)
    ap.add_argument("--max_add", type=int, default=100000)
    ap.add_argument("--no_exact", type=int, default=0)
    ap.add_argument("--core", type=int, default=0, help="on UNSAT: deletion-minimise the core of logicals")
    ap.add_argument("--witness", default="", help="spec that must stay admitted (soundness test)")
    ap.add_argument("--seed", type=int, default=20261011)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    t0 = time.time()
    F = make_family(a.sub, a.split_units)
    wu = {(x[0], int(x[1:])) for x in a.winunits.split(",")} if a.winunits else None
    tag = a.tag or f"sat_P{a.P}_H{len(F.Hs)}_{a.sub.replace(';', '_').replace(',', '') or 'triv'}" + \
        (f"_m{a.split_units.replace(',', '')}" if a.split_units else "") + \
        (f"_w{a.maxwin}{a.winunits.replace(',', '')}" if a.maxwin else "")
    recs, skipped = NF.prepare_full(F, "XZ")
    RC = [rec_cycles(F, r) for r in recs]
    M = ExactSAT(F, a.P, maxwin=a.maxwin, winunits=wu)
    print(f"P={a.P} |H|={len(F.Hs)} items={len(F.items)} reps={len(recs)} skipped={skipped} det={M.ndet} "
          f"clauses={M.ncl} {time.time() - t0:.0f}s", flush=True)
    wass = None
    if a.witness:
        from search.experiments.e024a.selftest import times_of_spec
        wt = times_of_spec(F, json.load(open(a.witness)), a.P)
        wass = [M.eq(i, wt[i]) for i in range(len(wt))]
        assert M.solve(wass) is not None
    active = []
    if a.all:
        for k, r in enumerate(recs):
            M.add_logical(k, r); active.append(k)
    log = {"P": a.P, "sub": a.sub, "split": a.split_units, "H": len(F.Hs), "reps": len(recs), "iters": [], "lift": []}
    status, it, ncand = "UNKNOWN", 0, 0
    rng = random.Random(a.seed)
    while time.time() - t0 < a.max_sec:
        it += 1
        ts = time.time()
        t = M.solve([M.sel[k] for k in active])
        if t is None:
            status = "UNSAT"; break
        aset = set(active)
        lif = [k for k in range(len(recs)) if not blocked(RC[k], t, a.P)]
        bad = [k for k in lif if k in aset]
        assert not bad, f"encoding error: active logicals lift {bad[:5]}"
        rec = {"it": it, "lifting": len(lif), "active": len(active), "solve_sec": round(time.time() - ts, 1),
               "sec": round(time.time() - t0, 1), "clauses": M.ncl}
        log["iters"].append(rec)
        print(rec, flush=True)
        if not lif:
            if a.no_exact:
                status = "MODEL_SAT"; log["t"] = t; break
            ncand += 1
            from search.experiments.e021.liftscreen import screen
            sp = OUT / f"{tag}_cand{ncand}.json"
            sp.write_text(json.dumps(spec_of(F, t, a.P)))
            r = screen(str(sp), a.rmax)
            print("exact:", r, flush=True)
            log["lift"].append(r)
            if r["status"] == "CERTIFIED":
                status = "CERTIFIED"; log["spec"] = str(sp); break
            M.add([-M.eq(i, t[i]) for i in range(len(t))])
            continue
        rng.shuffle(lif)
        for k in lif[:a.max_add]:
            M.add_logical(k, recs[k]); active.append(k)
        if wass is not None:
            assert M.solve(wass + [M.sel[k] for k in active]) is not None, "exact encoding excluded the witness"
    log.update(status=status, iterations=it, sec=round(time.time() - t0, 1), active=len(active), candidates=ncand)
    if status == "UNSAT":
        core = M.S.get_core() or []
        inv = {v: k for k, v in M.sel.items()}
        ck = sorted(inv[l] for l in core if l in inv)
        log["core_raw"] = ck
        print("raw core size", len(ck), flush=True)
        if a.core:
            keep = list(ck)
            i = 0
            while i < len(keep):
                trial = keep[:i] + keep[i + 1:]
                if M.solve([M.sel[k] for k in trial]) is None:
                    c2 = M.S.get_core() or []
                    keep = sorted(inv[l] for l in c2 if l in inv)
                    keep = [k for k in keep if k in set(trial)] or trial
                else:
                    i += 1
            log["core_min"] = keep
            log["core_min_recs"] = [{"kind": recs[k]["kind"], "S": recs[k]["S"], "evs": [list(map(str, e)) for e in recs[k]["evs"]]}
                                    for k in keep]
            print("minimal core", len(keep), keep, flush=True)
    print(f"STATUS P={a.P} |H|={len(F.Hs)} {status} it={it} active={len(active)} {log['sec']}s", flush=True)
    (OUT / f"{tag}.json").write_text(json.dumps(log))


if __name__ == "__main__":
    main()
