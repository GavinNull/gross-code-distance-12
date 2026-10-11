"""E-024a: incremental-SAT CEGAR for PIPELINED (wrapping) single-ancilla gross circuits of a fixed period P in the
Fig. 12 extended-code class, for families F(H) = circuits invariant under a translation subgroup H of the 24-element
colour-preserving group (|H| = 24 colour-symmetric ... |H| = 1 per-check free).

Variables (pysat, order encoding).  Unit u = (type, H-orbit class).  Item i = (u, label): absolute CNOT time
t_i in [0, 2P-4].  Per unit: times distinct, window max-min <= P-3 (prep at first-1, meas at last+1 mod P => evaluator
rule 0 < off(cnot) < off(meas) < P), first CNOT in [0, P-1] (unit-wise shift by P is the same circuit), unit X0's first
CNOT = 0 (global time shift).  Order of each unit in the 8-element Fig. 12 class (rev bool + prefix/suffix sets, same
as e021.cegarP / nwfull).
Legality (evaluator): per data qubit the 6 touching items' times are distinct mod P.
Determinism (E-018 audit criterion, 121/121 vs stim): X check a, Z check c sharing {u, v}:
   floor((Tx(u)-Tz(u))/P) == floor((Tx(v)-Tz(v))/P)  <=>  for m in {-P, 0, P}: [dx_u >= m] <-> [dx_v >= m].
   (Every candidate is re-checked by stim's DEM construction.)
Bulk frame model (E-018 feasible_general; wrap weights floor((t2-t1)/P)+1 as E-020 cegar / e021 cegarP, audited):
   lifting logical with potential pi -> nogood OR_i [difference literal], images under the 24 translations added
   (family and model are equivariant under the abelian 24-group).
Model candidate (no modelled logical lifts) -> exact lift (e021.liftscreen: E-018 DP on the complete 4224 lists,
   Table I asserted, R = 1..rmax both bases); if it lifts, that exact timing is excluded (weak, counted).
UNSAT => every legal deterministic F(H) circuit of period P in the class has a modelled weight-11 logical that lifts
   in the bulk (audit C1) => d_circ <= 11 for enough rounds.  (Bulk statement, not finite-R.)

    PYTHONPATH=.:tests uv run python -m search.experiments.e024a.cegar --P 14 --sub "1,2;0,3"
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

from pysat.formula import IDPool
from pysat.solvers import Cadical153

import search.experiments.e021.nwfull as NF
from search.experiments.e018 import common as C
from search.experiments.e021.liftscreen import screen
from search.experiments.e021.mono import fig12_labels
from search.experiments.e021.nwsat import Family, parse_sub, subgroup

OUT = Path("results/E-024a-gross12-period")
N2 = 72
G24 = subgroup([(1, 2), (0, 3)])


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


def tighten(cons, t, P, unit_of, rng):
    """Strengthen a lifting logical's potential (my addition, E-024a).  Edge e = (u, w, kd, (i1, i2)) is the constraint
    H_u - H_w <= wt_e (graph edge w -> u).  Greedily lower each edge's bound b_e (from wt_e towards the smallest weight
    the edge can take in the family, minwt_e) while the system stays feasible (no negative cycle; checked with an
    all-pairs shortest-path matrix updated incrementally), then return potentials pi feasible for b.  The nogood
    OR_e [wt'_e <= pi_u - pi_w - 1] is valid for ANY pi feasible for the current circuit's weights (pi_u - pi_w <=
    b_e <= wt_e), and every edge with pi_u - pi_w <= minwt_e contributes an impossible literal (dropped), so the clause
    gets shorter (stronger).  Returns (pi, minwt list)."""
    import numpy as np
    nodes = {}
    E = []
    for u, w, kd, (i1, i2) in cons:
        iu = nodes.setdefault(u, len(nodes)); iw = nodes.setdefault(w, len(nodes))
        f = (t[i2] - t[i1]) // P + 1
        wt = f if kd != "hook-" else -f
        same = unit_of[i1] == unit_of[i2]
        if kd != "hook-":
            mn = 0 if same else -1
        else:
            mn = -1 if same else -2
        E.append([iw, iu, wt, mn])
    n = len(nodes)
    INF = 10 ** 6
    Dm = np.full((n, n), INF, dtype=np.int64)
    np.fill_diagonal(Dm, 0)
    for a, b, wt, _ in E:
        if wt < Dm[a, b]:
            Dm[a, b] = wt
    for k in range(n):
        Dm = np.minimum(Dm, Dm[:, k:k + 1] + Dm[k:k + 1, :])
    assert (np.diag(Dm) >= 0).all()
    order = list(range(len(E)))
    rng.shuffle(order)
    for ei in order:
        a, b, wt, mn = E[ei]
        for nb in range(mn, wt):
            # adding edge a->b with weight nb keeps feasibility iff nb + dist(b, a) >= 0
            if nb + Dm[b, a] >= 0:
                if nb < Dm[a, b]:
                    Dm = np.minimum(Dm, Dm[:, a:a + 1] + nb + Dm[b:b + 1, :])
                E[ei][2] = nb
                break
    pot = np.minimum(0, Dm.min(axis=0))
    inv = {i: k for k, i in nodes.items()}
    pi = {inv[i]: int(pot[i]) for i in range(n)}
    for a, b, wt, _ in E:
        assert pot[b] - pot[a] <= wt
    return pi, [e[3] for e in E]


def adapt(F):
    """give a plain nwsat.Family the unit interface of mixed.MixedFamily."""
    if hasattr(F, "units"):
        return F
    F.units = [(ty, k) for ty in "XZ" for k in range(F.nc)]
    F.unit_rep = {(ty, k): F.reps[k] for ty in "XZ" for k in range(F.nc)}
    F.ucls = {ty: list(F.cls) for ty in "XZ"}
    return F


class TimeSAT:
    def __init__(self, F: Family, P: int, fix_first=True, maxwin=None, winunits=None):
        self.F, self.P = F, P
        self.TM = 2 * P - 4
        self.pool = IDPool()
        self.S = Cadical153()
        self.ncl = 0
        n = len(F.items)
        self.n = n
        # g[i][v] = [t_i >= v], v = 1..TM
        for i in range(n):
            for v in range(1, self.TM):
                self.add([-self.ge(i, v + 1), self.ge(i, v)])
        self.dcache = {}
        f12 = fig12_labels()
        adapt(F)
        self.units = list(F.units)
        for u in self.units:
            its = [F.idx[(u[0], u[1], lab)] for lab in range(6)]
            for a in its:
                for b in its:
                    if a < b:
                        self.add([self.le_diff(a, b, -1), self.le_diff(b, a, -1)])   # distinct
                    if a != b:
                        wl = P - 3 if (maxwin is None or (winunits is not None and u not in winunits)) else min(P - 3, maxwin)
                        self.add([self.le_diff(a, b, wl)])  # window
            self.add([-self.ge(i, P) for i in its])                                    # first CNOT <= P-1
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
            self.add([-self.ge(i, 1) for i in (F.idx[("X", 0, lab)] for lab in range(6))])  # some X0 item at 0
        # legality: residues distinct per data qubit
        for q in range(144):
            its = sorted({F.item(ty, c, lab) for ty, c, lab in F.touch[q]})
            assert len(its) == 6
            for x in range(6):
                for y in range(x + 1, 6):
                    for r in range(P):
                        self.add([-self.res(its[x], r), -self.res(its[y], r)])
        # determinism
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

    def add(self, cl):
        self.S.add_clause(cl); self.ncl += 1

    def ge(self, i, v):
        """literal [t_i >= v]; constants for v <= 0 / v > TM handled by caller via TRUE/FALSE ids."""
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
        """one-way literal L -> (t_a - t_b <= M)."""
        key = ("le", a, b, M)
        if key in self.dcache:
            return self.dcache[key]
        L = self.pool.id(key)
        # t_a <= t_b + M  <=>  for all v: [t_a >= v] -> [t_b >= v - M]
        for v in range(1, self.TM + 1):
            w = v - M
            if w <= 0:
                continue
            self.add([-L, -self.ge(a, v), self.ge(b, w)])
        if M < 0:
            self.add([-L, self.ge(b, -M)])   # v = 0 case: t_b >= -M
        self.dcache[key] = L
        return L

    def full_ge_diff(self, a, b, m):
        """fully reified literal  <-> (t_a - t_b >= m)."""
        key = ("fge", a, b, m)
        if key in self.dcache:
            return self.dcache[key]
        L = self.pool.id(key)
        l1 = self.le_diff(b, a, -m)        # t_b - t_a <= -m
        l2 = self.le_diff(a, b, m - 1)     # t_a - t_b <= m-1
        self.add([-L, l1]); self.add([L, l2])
        self.dcache[key] = L
        return L

    def solve(self, assumptions=(), deadline=None):
        if not self.S.solve(assumptions=list(assumptions)):
            return None
        mod = self.S.get_model()
        pos = set(l for l in mod if l > 0)
        t = []
        for i in range(self.n):
            v = 0
            while v + 1 <= self.TM and self.pool.id(("g", i, v + 1)) in pos:
                v += 1
            t.append(v)
        return t


def item_perms(F):
    """for each g in the 24-group: item index permutation."""
    T = F.T
    out = []
    for g in G24:
        pr, pc = C.tr(*g)
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


def spec_of(F, t, P):
    T = F.T
    d = {"format": "qec-schedule/v1", "period": P, "x_checks": [], "z_checks": []}
    for ty, key in (("X", "x_checks"), ("Z", "z_checks")):
        for i in range(N2):
            ts = [t[F.item(ty, i, lab)] for lab in range(6)]
            d[key].append({"prep": (min(ts) - 1) % P, "meas": (max(ts) + 1) % P,
                           "cnots": [[int(T[ty][i][lab]), ts[lab] % P] for lab in range(6)]})
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--sub", default="1,2;0,3", help="generators of H ('' = trivial = per-check free)")
    ap.add_argument("--max_sec", type=float, default=3600)
    ap.add_argument("--rmax", type=int, default=6)
    ap.add_argument("--images", type=int, default=1)
    ap.add_argument("--no_model", type=int, default=0, help="classical control: no nogoods, random sampling")
    ap.add_argument("--seed", type=int, default=20261011)
    ap.add_argument("--tag", default="")
    ap.add_argument("--stop_on_cert", type=int, default=1)
    ap.add_argument("--tighten", type=int, default=1)
    ap.add_argument("--maxwin", type=int, default=None, help="max (last CNOT - first CNOT) per check")
    ap.add_argument("--split_units", default="", help="mixed family: split only these colour units (e.g. 'X0,Z2') "
                    "into orbits of --sub; others colour-symmetric")
    ap.add_argument("--hook_filter", default="", help="keep only logicals with a hook on a check of these classes, "
                    "e.g. 'X:0' (sound for UNSAT; local core test)")
    ap.add_argument("--winunits", default="", help="apply maxwin only to these units, e.g. 'X0,Z2'")
    ap.add_argument("--witness", default="", help="soundness test: a spec in the family that must stay admitted")
    a = ap.parse_args()
    P = a.P
    t0 = time.time()
    gens = parse_sub(a.sub) if a.sub else [(0, 0)]
    if a.split_units:
        from search.experiments.e024a.mixed import MixedFamily
        su = {(x[0], int(x[1:])) for x in a.split_units.split(",")}
        F = MixedFamily(gens, su)
        print("mixed family units", F.units, flush=True)
    else:
        F = Family(gens)
    tag = a.tag or f"P{P}_H{len(F.Hs)}_{a.sub.replace(';', '_').replace(',', '') or 'triv'}{'_m' + a.split_units.replace(',', '') if a.split_units else ''}"
    recs, skipped = NF.prepare_full(F, "XZ")
    if a.hook_filter:
        ty_, ks = a.hook_filter.split(":")
        ks = {int(x) for x in ks.split(",")}
        recs = [r for r in recs if r["kind"] == ty_ and any(e[0] == "h" and F.cls[e[1]] in ks for e in r["evs"])]
        print("hook filter", a.hook_filter, "->", len(recs), "logicals kept", flush=True)
    wu = None
    if a.winunits:
        wu = {(x[0], int(x[1:])) for x in a.winunits.split(",")}
    M = TimeSAT(F, P, maxwin=a.maxwin, winunits=wu)
    perms = item_perms(F) if a.images else [list(range(len(F.items)))]
    print(f"P={P} |H|={len(F.Hs)} classes={F.nc} items={len(F.items)} reps={len(recs)} skipped={skipped} "
          f"det_pairs={M.ndet} clauses={M.ncl} vars={M.pool.top} {time.time() - t0:.0f}s", flush=True)
    rng = random.Random(a.seed)
    unit_of = [(it_[0], it_[1]) for it_ in F.items]
    wass = None
    if a.witness:
        from search.experiments.e024a.selftest import times_of_spec
        wt = times_of_spec(F, json.load(open(a.witness)), P)
        wass = [M.eq(i, wt[i]) for i in range(len(wt))]
        assert M.solve(wass) is not None
    log = {"P": P, "sub": a.sub, "H": len(F.Hs), "reps": len(recs), "skipped": skipped, "iters": [], "lift": []}
    status, it, ncand = "UNKNOWN", 0, 0
    best = None
    import os
    import threading

    def watchdog():   # a single SAT call can exceed max_sec (CaDiCaL in pysat cannot be interrupted)
        log.update(status="UNKNOWN", iterations=it, sec=round(time.time() - t0, 1), best_model_lifting=best,
                   candidates=ncand, note="watchdog: SAT call exceeded max_sec")
        print(f"STATUS P={P} |H|={len(F.Hs)} UNKNOWN it={it} cands={ncand} best={best} (watchdog) "
              f"{log['sec']}s", flush=True)
        (OUT / f"{tag}.json").write_text(json.dumps(log))
        os._exit(0)
    wd = threading.Timer(a.max_sec + 60, watchdog)
    wd.daemon = True
    wd.start()
    while time.time() - t0 < a.max_sec:
        it += 1
        if a.no_model:
            M.S.set_phases([rng.choice([1, -1]) * v for v in range(1, M.pool.top + 1)])
        t = M.solve()
        if t is None:
            status = "UNSAT"; break
        NF.bf_general = lambda cons, rank: bf_P(cons, t, P)  # noqa: E731
        lif = NF.evaluate_full(F, recs, None)
        if best is None or len(lif) < best:
            best = len(lif)
        if not lif or a.no_model:
            ncand += 1
            sp = OUT / f"{tag}_cand{ncand}.json"
            sp.write_text(json.dumps(spec_of(F, t, P)))
            ts = time.time()
            r = screen(str(sp), a.rmax)
            r.update(it=it, model_lifting=len(lif), sec=round(time.time() - ts, 1))
            log["lift"].append(r)
            print("exact:", r, flush=True)
            if r["status"] == "CERTIFIED" and a.stop_on_cert:
                status = "CERTIFIED"; log["spec"] = str(sp); break
            # exclude this exact timing (and its images)
            for pm in perms:
                M.add([-M.eq(pm[i], t[i]) for i in range(len(t))])
            if a.no_model:
                rec = {"it": it, "model_lifting": len(lif), "sec": round(time.time() - t0, 1)}
                log["iters"].append(rec)
                continue
            continue
        nn = clen = 0
        seen_cl = set()
        for r_, cons, pi in lif:
            mins = None
            if a.tighten:
                pi, mins = tighten(cons, t, P, unit_of, rng)
            for pm in perms:
                lits = set()
                for ei, (u_, w_, kd, (i1, i2)) in enumerate(cons):
                    K = pi[u_] - pi[w_]
                    if mins is not None and K - 1 < mins[ei]:
                        continue                 # literal impossible in the family
                    j1, j2 = pm[i1], pm[i2]
                    if kd in ("free", "hook+"):
                        lits.add(M.le_diff(j2, j1, (K - 1) * P - 1))
                    else:
                        lits.add(M.le_diff(j1, j2, K * P))
                cl = tuple(sorted(lits))
                if cl in seen_cl:
                    continue
                seen_cl.add(cl)
                M.add(list(cl)); nn += 1; clen += len(cl)
        if wass is not None:
            assert M.solve(wass) is not None, "nogood excluded the witness circuit"
        rec = {"it": it, "lifting": len(lif), "nogoods": nn, "sec": round(time.time() - t0, 1),
               "mean_len": round(clen / max(nn, 1), 1)}
        log["iters"].append(rec)
        if it % 10 == 0 or it < 4:
            print(rec, flush=True)
    wd.cancel()
    log.update(status=status, iterations=it, sec=round(time.time() - t0, 1), best_model_lifting=best,
               candidates=ncand)
    print(f"STATUS P={P} |H|={len(F.Hs)} {status} it={it} cands={ncand} best={best} {log['sec']}s", flush=True)
    (OUT / f"{tag}.json").write_text(json.dumps(log))


if __name__ == "__main__":
    main()
