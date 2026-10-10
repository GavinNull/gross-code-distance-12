"""E-021 follow-up (2c): pipelined (wrapping allowed) colour-symmetric circuits of a GIVEN period P in the Fig. 12
extended-code class, CEGAR in the bulk frame model with all weight-11 logicals (realisations as nwfull.py), then the
exact lift on every model candidate (liftscreen), excluding the exact schedule if the lift fails.

Variables (CP-SAT, re-solved each iteration): per unit u = (type, class): start s_u in [0,P), offsets o_{u,l} in
[1, P-2] per label l (distinct), order constrained to the Fig. 12 class (within-pair swaps / reversal via a Boolean
rev_u), absolute CNOT time t_{u,l} = s_u + o_{u,l}; measurement at s_u + P - 1 (any later point would also do).
Legality: per data qubit, the 6 times mod P distinct (evaluator rule).  Determinism: floor((T_x(u)-T_z(u))/P) equal on
the two shared qubits (criterion matched stim 121/121, audit 2026-10-08).
Model constraints (E-018 feasible_general): weight(i1, i2) = floor((t_i2 - t_i1)/P) + 1 (free, hook+), minus that
(hook-).  Nogood for a lifting logical with potential pi: OR of reified [t_i2 - t_i1 <= (K-1)P - 1] (free/hook+)
or [t_i2 - t_i1 >= -K P] (hook-), K = pi_u - pi_w over tight constraints (E-020 cegar.py, audited).
UNSAT => no colour-symmetric period-P circuit in the class blocks all modelled logicals in the bulk (=> none
certifies, since a bulk lift is a genuine weight-11 logical for large R ... and for the R <= 6 certificate the
lift is exact anyway).

    PYTHONPATH=.:tests uv run python -m search.experiments.e021.cegarP --P 12
"""
from __future__ import annotations

import argparse
import itertools
import json
import time
from pathlib import Path

from ortools.sat.python import cp_model

from search.experiments.e021.liftscreen import screen
from search.experiments.e021.mono import fig12_labels, table
from search.experiments.e021.nwfull import evaluate_full, prepare_full
from search.experiments.e021.nwsat import Family, parse_sub

OUT = Path("results/E-021-gross-new-orders")
N2 = 72


class Rank:
    """adapter so nwsat.bf (via nwfull.evaluate_full) can evaluate wrap-around weights: bf uses
    'rank[i2] > rank[i1]' for weights; we instead patch bf with a general weight function."""


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--sub", default="1,2;0,3")
    ap.add_argument("--max_sec", type=float, default=3600)
    ap.add_argument("--nowrap", type=int, default=0)
    ap.add_argument("--rmax", type=int, default=6)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    P = a.P
    t0 = time.time()
    F = Family(parse_sub(a.sub))
    recs, skipped = prepare_full(F, "XZ")
    import search.experiments.e021.nwfull as NF
    T = table()
    f12 = fig12_labels()
    units = [(ty, k) for ty in "XZ" for k in range(F.nc)]
    m = cp_model.CpModel()
    s = {u: m.NewIntVar(0, 0 if a.nowrap else P - 1, f"s{u}") for u in units}
    o = {(u, l): m.NewIntVar(1, P - 2, f"o{u}{l}") for u in units for l in range(6)}
    t = {}
    for u in units:
        m.AddAllDifferent([o[(u, l)] for l in range(6)])
        for l in range(6):
            t[F.idx[(u[0], u[1], l)]] = s[u] + o[(u, l)]
        ordr = f12[u[0]][F.reps[u[1]]]
        rev = m.NewBoolVar(f"rev{u}")

        def first(U, cond):
            for x in U:
                for y in range(6):
                    if y not in U:
                        m.Add(o[(u, x)] < o[(u, y)]).OnlyEnforceIf(cond)
        first(ordr[:2], rev.Not()); first(ordr[:3], rev.Not()); first(ordr[:4], rev.Not())
        first(ordr[4:], rev); first(ordr[3:], rev); first(ordr[2:], rev)
    m.Add(s[("X", 0)] == 0)
    tv = {}
    for i, it in enumerate(F.items):
        v = m.NewIntVar(0, 2 * P, f"t{i}")
        m.Add(v == t[i]); tv[i] = v
    # legality: per data qubit times mod P distinct
    modv = {}
    for i in tv:
        mv = m.NewIntVar(0, P - 1, f"m{i}")
        m.AddModuloEquality(mv, tv[i], P); modv[i] = mv
    for q in range(144):
        its = sorted({F.item(ty, c, lab) for ty, c, lab in F.touch[q]})
        assert len(its) == 6
        m.AddAllDifferent([modv[i] for i in its])
    # determinism
    seen = set()
    for ia in range(N2):
        qa = set(int(x) for x in T["X"][ia])
        for ic in range(N2):
            ov = sorted(qa & set(int(x) for x in T["Z"][ic]))
            if not ov:
                continue
            pr = []
            for q in ov:
                pr.append((F.item("X", ia, F.label_of("X", ia, q)), F.item("Z", ic, F.label_of("Z", ic, q))))
            key = tuple(pr)
            if key in seen:
                continue
            seen.add(key)
            fl = []
            for ix, iz in pr:
                f = m.NewIntVar(0, 6, "")
                num = m.NewIntVar(-2 * P, 2 * P + 3 * P, "")
                m.Add(num == tv[ix] - tv[iz] + 3 * P)
                m.AddDivisionEquality(f, num, P)
                fl.append(f)
            m.Add(fl[0] == fl[1])
    print(f"P={P} units {len(units)} reps {len(recs)} skipped {skipped} det-pairs {len(seen)} {time.time() - t0:.0f}s", flush=True)
    diffb = {}

    def dlit(i1, i2, op, M):
        key = (i1, i2, op, M)
        if key not in diffb:
            b = m.NewBoolVar("")
            if op == "le":
                m.Add(tv[i2] - tv[i1] <= M).OnlyEnforceIf(b)
            else:
                m.Add(tv[i2] - tv[i1] >= M).OnlyEnforceIf(b)
            diffb[key] = b
        return diffb[key]
    log = {"P": P, "sub": a.sub, "iters": [], "lift_rejects": []}
    status, it = "UNKNOWN", 0
    tag = a.tag or f"cegarP{P}{'_nw' if a.nowrap else ''}"
    while time.time() - t0 < a.max_sec:
        it += 1
        solver = cp_model.CpSolver()
        solver.parameters.num_workers = 1
        solver.parameters.max_time_in_seconds = max(10.0, a.max_sec - (time.time() - t0))
        st = solver.Solve(m)
        if st == cp_model.INFEASIBLE:
            status = "UNSAT"; break
        if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            status = "UNKNOWN"; break
        tval = {i: solver.Value(tv[i]) for i in tv}
        # evaluate all modelled logicals with wrap-around weights
        NF.bf_general = lambda cons, rank: bf_P(cons, tval, P)  # noqa: E731
        lif = evaluate_full(F, recs, None)
        if not lif:
            # exact lift of the concrete circuit
            d = {"format": "qec-schedule/v1", "period": P, "x_checks": [], "z_checks": []}
            for ty, key in (("X", "x_checks"), ("Z", "z_checks")):
                for i in range(N2):
                    u = (ty, F.cls[i])
                    sv = solver.Value(s[u])
                    cn = [[int(T[ty][i][l]), (sv + solver.Value(o[(u, l)])) % P] for l in range(6)]
                    d[key].append({"prep": sv % P, "meas": (sv + P - 1) % P, "cnots": cn})
            sp = OUT / f"{tag}_cand{it}.json"
            sp.write_text(json.dumps(d))
            r = screen(str(sp), a.rmax)
            print("model candidate -> exact", r, flush=True)
            if r["status"] == "CERTIFIED":
                status = "CERTIFIED"; log["spec"] = str(sp); break
            log["lift_rejects"].append(r)
            # exclude this exact timing assignment
            bs = []
            for i in tv:
                b = m.NewBoolVar("")
                m.Add(tv[i] != tval[i]).OnlyEnforceIf(b)
                bs.append(b)
            m.AddBoolOr(bs)
            continue
        for r_, cons, pi in lif:
            lits = []
            for u_, w_, kd, (i1, i2) in cons:
                K = pi[u_] - pi[w_]
                if kd in ("free", "hook+"):
                    lits.append(dlit(i1, i2, "le", (K - 1) * P - 1))
                else:
                    lits.append(dlit(i1, i2, "ge", -K * P))
            m.AddBoolOr(sorted(set(lits), key=lambda v: v.Index()))
        rec = {"it": it, "lifting": len(lif), "sec": round(time.time() - t0, 1)}
        log["iters"].append(rec)
        if it % 10 == 0 or it < 3:
            print(rec, flush=True)
    log.update(status=status, iterations=it, sec=round(time.time() - t0, 1))
    print(f"STATUS P={P} {status} it={it} {log['sec']}s", flush=True)
    (OUT / f"{tag}.json").write_text(json.dumps(log))


if __name__ == "__main__":
    main()
