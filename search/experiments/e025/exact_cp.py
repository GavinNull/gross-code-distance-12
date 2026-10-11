"""E-025 method (B)/(d): EXACT lazy-logical solver (CP-SAT) for pipelined single-ancilla gross circuits of period P in
the Fig. 12 extended-code class, family F(H) (H <= 24-element colour-preserving group; '' = per-check free), same
family and evaluator rules as e024a.cegar.TimeSAT:
  items t_i in [0, 2P-4]; per unit: distinct, window <= P-3, first CNOT <= P-1, order in the 8-element Fig. 12 class
  (rev bool); X unit 0 first CNOT = 0; legality = residues mod P distinct per data qubit (AllDifferent);
  determinism = floor((Tx(u)-Tz(u))/P) == floor((Tx(v)-Tz(v))/P) (E-018 audit criterion).
Instead of nogoods, every added logical is encoded EXACTLY ("blocked in the bulk frame model"):
  frame-model system H_u - H_w <= wt_e (e021.nwfull skeleton; wt = 1 + f_e for free/hook+, -(1 + f_e) for hook-,
  f_e = floor((t_i2 - t_i1)/P), an integer var with P f <= dt <= P f + P - 1) is infeasible  <=>  (Farkas for
  difference constraints) there is a 0/1 circulation y on the constraint graph with sum_e y_e wt_e <= -1.
  (Any 0/1 circulation decomposes into cycles, so a negative total implies a negative cycle; a negative simple cycle is
  a 0/1 circulation.)  Products y_e * f_e via z_e with enforcement.  A logical with several pairings is blocked iff
  every pairing is blocked -> one circulation per pairing.
Lazy loop: solve -> evaluate all modelled logicals with the frame model (cycle form, e025.cyc, cross-checked against
  Bellman-Ford) -> add the exact encoding of every lifting logical -> repeat.  An already-added logical can never lift
  again (asserted: self-check of the encoding).  The number of rounds is bounded by the number of logicals.
  Candidate (no modelled logical lifts) -> exact lift screen (e021.liftscreen, R = 1..rmax both bases).
INFEASIBLE => every legal deterministic circuit of F(H) at period P has a modelled weight-11 logical that lifts in the
  bulk => d_circ <= 11 for enough rounds (same meaning as the e024a/e024b UNSAT results).

    PYTHONPATH=.:tests uv run python -m search.experiments.e025.exact_cp --P 17 --sub "1,2;0,3"
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from ortools.sat.python import cp_model

import search.experiments.e021.nwfull as NF
from search.experiments.e021.mono import fig12_labels
from search.experiments.e021.nwsat import Family, parse_sub
from search.experiments.e024a.cegar import adapt, spec_of
from search.experiments.e025.cyc import pairing_classes, rec_cycles, blocked

OUT = Path("results/E-025-gross12-perchk-period")
N2 = 72


class ExactCP:
    def __init__(self, F, P, maxwin=None, winunits=None, fix_first=True):
        self.F, self.P = F, P
        adapt(F)
        m = self.m = cp_model.CpModel()
        n = len(F.items)
        TM = 2 * P - 4
        self.t = [m.NewIntVar(0, TM, f"t{i}") for i in range(n)]
        t = self.t
        self.unit_of = [(it[0], it[1]) for it in F.items]
        self.fv = {}
        f12 = fig12_labels()
        self.rev = {}
        for u in F.units:
            its = [F.idx[(u[0], u[1], lab)] for lab in range(6)]
            m.AddAllDifferent([t[i] for i in its])
            wl = P - 3 if (maxwin is None or (winunits is not None and u not in winunits)) else min(P - 3, maxwin)
            for a in its:
                for b in its:
                    if a != b:
                        m.Add(t[a] - t[b] <= wl)
            mn = m.NewIntVar(0, TM, f"mn{u}")
            m.AddMinEquality(mn, [t[i] for i in its])
            m.Add(mn <= P - 1)
            if fix_first and u == ("X", 0):
                m.Add(mn == 0)
            o = f12[u[0]][F.unit_rep[u]]
            T = lambda lab: t[F.idx[(u[0], u[1], lab)]]  # noqa: E731
            rv = m.NewBoolVar(f"rev{u}")
            self.rev[u] = rv
            fw = [(o[0], o[2]), (o[1], o[2]), (o[2], o[3]), (o[3], o[4]), (o[3], o[5])]
            for x, y in fw:
                m.Add(T(x) < T(y)).OnlyEnforceIf(rv.Not())
                m.Add(T(y) < T(x)).OnlyEnforceIf(rv)
        # legality
        self.r = [m.NewIntVar(0, P - 1, f"r{i}") for i in range(n)]
        for i in range(n):
            m.AddModuloEquality(self.r[i], t[i], P)
        for q in range(144):
            its = sorted({F.item(ty, c, lab) for ty, c, lab in F.touch[q]})
            assert len(its) == 6
            m.AddAllDifferent([self.r[i] for i in its])
        # determinism
        T_ = F.T
        seen = set()
        for a in range(N2):
            qa = set(int(x) for x in T_["X"][a])
            for c in range(N2):
                ov = sorted(qa & set(int(x) for x in T_["Z"][c]))
                if not ov:
                    continue
                pr = tuple((F.item("Z", c, F.label_of("Z", c, q)), F.item("X", a, F.label_of("X", a, q))) for q in ov)
                if pr in seen:
                    continue
                seen.add(pr)
                m.Add(self.f(*pr[0]) == self.f(*pr[1]))
        self.ndet = len(seen)
        self.sel = {}
        self.nlog = 0

    def f(self, i1, i2):
        """floor((t_i2 - t_i1)/P) as an int var."""
        key = (i1, i2)
        if key not in self.fv:
            P = self.P
            same = self.unit_of[i1] == self.unit_of[i2]
            lo, hi = (-1, 0) if same else (-2, 1)
            v = self.m.NewIntVar(lo, hi, f"f{i1}_{i2}")
            d = self.t[i2] - self.t[i1]
            self.m.Add(P * v <= d)
            self.m.Add(d <= P * v + P - 1)
            self.fv[key] = v
        return self.fv[key]

    def add_logical(self, k, r, selector=False):
        """exact 'blocked' encoding of record r (all pairings)."""
        m = self.m
        lit = None
        if selector:
            lit = m.NewBoolVar(f"sel{k}")
            self.sel[k] = lit
        for cls in pairing_classes(r):
            cons = NF.skeleton(self.F, r, cls)
            nodes = {}
            ins, outs = {}, {}
            terms = []
            for e, (u, w, kd, (i1, i2)) in enumerate(cons):
                y = m.NewBoolVar("")
                z = m.NewIntVar(-2, 1, "")
                fv = self.f(i1, i2)
                m.Add(z == fv).OnlyEnforceIf(y)
                m.Add(z == 0).OnlyEnforceIf(y.Not())
                s = -1 if kd == "hook-" else 1
                terms.append(s * (y + z))
                outs.setdefault(w, []).append(y)      # graph edge w -> u
                ins.setdefault(u, []).append(y)
                nodes[u] = nodes[w] = 1
            for v in nodes:
                c = m.Add(sum(ins.get(v, [])) == sum(outs.get(v, [])))
                if lit is not None:
                    c.OnlyEnforceIf(lit)
            c = m.Add(sum(terms) <= -1)
            if lit is not None:
                c.OnlyEnforceIf(lit)
        self.nlog += 1
        return lit

    def solve(self, max_sec, workers, hint=None, assumptions=None, seed=0):
        s = cp_model.CpSolver()
        s.parameters.max_time_in_seconds = max_sec
        s.parameters.num_workers = workers
        s.parameters.random_seed = seed
        self.m.ClearHints()
        if hint is not None:
            for v, x in zip(self.t, hint):
                self.m.AddHint(v, x)
        self.m.ClearAssumptions()
        if assumptions:
            self.m.AddAssumptions(assumptions)
        st = s.Solve(self.m)
        self.last = s
        if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return "SAT", [s.Value(v) for v in self.t]
        if st == cp_model.INFEASIBLE:
            return "INFEASIBLE", None
        return "UNKNOWN", None


def make_family(sub, split_units=""):
    gens = parse_sub(sub) if sub else [(0, 0)]
    if split_units:
        from search.experiments.e024a.mixed import MixedFamily
        su = {(x[0], int(x[1:])) for x in split_units.split(",")}
        return MixedFamily(gens, su)
    return Family(gens)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--sub", default="1,2;0,3")
    ap.add_argument("--split_units", default="")
    ap.add_argument("--max_sec", type=float, default=3600)
    ap.add_argument("--round_sec", type=float, default=1800)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--rmax", type=int, default=6)
    ap.add_argument("--maxwin", type=int, default=None)
    ap.add_argument("--winunits", default="")
    ap.add_argument("--all", type=int, default=0, help="add all modelled logicals up front (no laziness)")
    ap.add_argument("--max_add", type=int, default=100000, help="max logicals added per round")
    ap.add_argument("--no_exact", type=int, default=0)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    t0 = time.time()
    F = make_family(a.sub, a.split_units)
    wu = {(x[0], int(x[1:])) for x in a.winunits.split(",")} if a.winunits else None
    tag = a.tag or f"cp_P{a.P}_H{len(F.Hs)}_{a.sub.replace(';', '_').replace(',', '') or 'triv'}" + \
        (f"_m{a.split_units.replace(',', '')}" if a.split_units else "") + (f"_w{a.maxwin}" if a.maxwin else "")
    recs, skipped = NF.prepare_full(F, "XZ")
    RC = [rec_cycles(F, r) for r in recs]
    M = ExactCP(F, a.P, maxwin=a.maxwin, winunits=wu)
    print(f"P={a.P} |H|={len(F.Hs)} items={len(F.items)} reps={len(recs)} skipped={skipped} det={M.ndet} "
          f"{time.time() - t0:.0f}s", flush=True)
    active = set()
    if a.all:
        for k, r in enumerate(recs):
            M.add_logical(k, r); active.add(k)
    log = {"P": a.P, "sub": a.sub, "split": a.split_units, "H": len(F.Hs), "reps": len(recs), "iters": [], "lift": []}
    status, it, hint, ncand = "UNKNOWN", 0, None, 0
    while time.time() - t0 < a.max_sec:
        it += 1
        ts = time.time()
        st, t = M.solve(min(a.round_sec, a.max_sec - (time.time() - t0)), a.workers, hint=hint, seed=it)
        if st == "INFEASIBLE":
            status = "INFEASIBLE"; break
        if st == "UNKNOWN":
            status = "UNKNOWN"; break
        lif = [k for k in range(len(recs)) if not blocked(RC[k], t, a.P)]
        bad = [k for k in lif if k in active]
        assert not bad, f"encoding error: active logicals lift {bad[:5]}"
        rec = {"it": it, "lifting": len(lif), "active": len(active), "solve_sec": round(time.time() - ts, 1),
               "sec": round(time.time() - t0, 1)}
        log["iters"].append(rec)
        print(rec, flush=True)
        hint = t
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
            # exclude this exact timing
            bs = []
            for i, v in enumerate(M.t):
                b = M.m.NewBoolVar("")
                M.m.Add(v != t[i]).OnlyEnforceIf(b)
                bs.append(b)
            M.m.AddBoolOr(bs)
            continue
        for k in lif[:a.max_add]:
            M.add_logical(k, recs[k]); active.add(k)
    log.update(status=status, iterations=it, sec=round(time.time() - t0, 1), active=len(active), candidates=ncand)
    print(f"STATUS P={a.P} |H|={len(F.Hs)} {status} it={it} active={len(active)} {log['sec']}s", flush=True)
    (OUT / f"{tag}.json").write_text(json.dumps(log))


if __name__ == "__main__":
    main()
