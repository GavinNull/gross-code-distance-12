"""E-024b step 3: timing CEGAR and exact lift for an ARBITRARY colour-dependent extended-code class.

Generalises e021/cegarP.py + nwfull.py + liftscreen.py (Fig. 12 class only) to: colouring col = (m, alpha, beta),
per-colour canonical orders xo[c], zo[c] (each unit may use any of the 8 orders with the same extended code: within-pair
swaps of positions 1-2 / 5-6 and reversal), complete weight-11 lists from w11.py (stored by (H,L) keys).

Lift (exact, as audited for E-021, `research/audits/2026-10-10-E-021.md` item 3): requires d_ext >= 11 for the side
(w11.py asserts the W=10 DFS found nothing) and the complete weight-11 list; asserts the circuit's extended column key
set equals the list's code (same class) and Table I (lift21.build_groups).

    PYTHONPATH=.:tests uv run python -m search.experiments.e024b.gen --col 3,1,1 --x <orders> --z <orders> --P 12
"""
from __future__ import annotations

import argparse
import itertools
import json
import pickle
import time
from pathlib import Path

from ortools.sat.python import cp_model

from evaluators.candidate import parse_schedule
from search.experiments.e018.lift import solve
from search.experiments.e021.lift21 import KIND_OF_BASIS, build_groups, label_orders
from search.experiments.e021.mono import table
from search.experiments.e021.nwfull import column_real, evaluate_full
from search.experiments.e021.nwsat import Family
from search.experiments.e024b.common import OUT, colour, ext_general, labord, type_key
from search.experiments.e024b.w11 import parse_orders, tag_of

N2 = 72


def kernel(col):
    m, al, be = col
    return [(a, b) for a in range(12) for b in range(6) if (al * a + be * b) % m == 0]


def load_list(kind, col, orders_s):
    d = pickle.load(open(OUT / f"w11_{tag_of(kind, col, orders_s)}.pkl", "rb"))
    return d["keys"]


def reindex(E, keylist):
    k2j = {E["He"][:, j].tobytes() + E["Le"][:, j].tobytes(): j for j in range(E["N"])}
    allk = {k for S in keylist for k in S}
    assert allk <= set(k2j), "list column not in this circuit's extended code"
    return [tuple(sorted(k2j[k] for k in S)) for S in keylist], set(k2j)


class Cls:
    """a full class: colouring + per-colour orders for X and Z sides + their lists."""

    def __init__(self, col, xs, zs):
        self.col, self.xs, self.zs = col, xs, zs
        self.orders = {"X": parse_orders(xs), "Z": parse_orders(zs)}
        self.E = {k: ext_general(k, labord(col, self.orders[k])) for k in "XZ"}
        self.keys = {k: load_list(k, col, xs if k == "X" else zs) for k in "XZ"}
        self.sols = {}
        self.colset = {}
        for k in "XZ":
            self.sols[k], self.colset[k] = reindex(self.E[k], self.keys[k])


def prepare(F, C: Cls, kinds="XZ"):
    recs, skipped = [], 0
    Hs = set(F.Hs)
    for kind in kinds:
        rd = "Z" if kind == "X" else "X"
        E = C.E[kind]
        perms = [P for g, P in zip(E["group"], E["perms"]) if tuple(g) in Hs]
        seen, reps = set(), []
        for S in C.sols[kind]:
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


def lift_screen(spec_d, C: Cls, rmax=6, rlist=None, stop_first=True, bases="ZX"):
    """exact lift; returns dict with status CERTIFIED / lifts / error and per-(R,basis) counts."""
    spec = parse_schedule(spec_d).canonical()
    lo = label_orders(spec)
    Es, sols = {}, {}
    for b in bases:
        k = KIND_OF_BASIS[b]
        Es[b] = ext_general(k, lo[k])
        sols[b], cs = reindex(Es[b], C.keys[k])
        assert cs == C.colset[k], "circuit's extended code differs from the class"
    per = []
    for R in (rlist or range(1, rmax + 1)):
        for b in bases:
            try:
                groups, st = build_groups(spec, R, b, Es[b])
            except Exception as e:  # noqa: BLE001
                return {"status": "error", "err": str(e)[:300]}
            n = 0
            for S in sols[b]:
                if solve(S, groups)[0] is not None:
                    n += 1
                    if stop_first:
                        break
            per.append({"R": R, "basis": b, "lifting": n, "num": len(sols[b])})
            if n and stop_first:
                return {"status": "lifts", "R": R, "basis": b, "per": per}
    st = "CERTIFIED" if all(p["lifting"] == 0 for p in per) else "lifts"
    return {"status": st, "per": per}


def first_constraints(m, o_var, u, ordr, rev):
    def first(U, cond):
        for x in U:
            for y in range(6):
                if y not in U:
                    m.Add(o_var[(u, x)] < o_var[(u, y)]).OnlyEnforceIf(cond)
    first(ordr[:2], rev.Not()); first(ordr[:3], rev.Not()); first(ordr[:4], rev.Not())
    first(ordr[4:], rev); first(ordr[3:], rev); first(ordr[2:], rev)


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


def build_family(col):
    F = Family(kernel(col))
    assert F.nc == col[0]
    ccol = [colour(col, F.reps[k]) for k in range(F.nc)]
    for i in range(N2):
        assert colour(col, i) == ccol[F.cls[i]]
    return F, ccol


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--col", required=True)
    ap.add_argument("--x", required=True)
    ap.add_argument("--z", required=True)
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--nowrap", type=int, default=0)
    ap.add_argument("--max_sec", type=float, default=3600)
    ap.add_argument("--rmax", type=int, default=6)
    ap.add_argument("--tag", default="")
    ap.add_argument("--nologic", type=int, default=0, help="classical control: no logical nogoods (random legal)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--maxcand", type=int, default=1000000)
    a = ap.parse_args()
    P = a.P
    t0 = time.time()
    col = tuple(int(v) for v in a.col.split(","))
    C = Cls(col, a.x, a.z)
    F, ccol = build_family(col)
    recs, skipped = prepare(F, C)
    T = table()
    units = [(ty, k) for ty in "XZ" for k in range(F.nc)]
    m = cp_model.CpModel()
    s = {u: m.NewIntVar(0, 0 if a.nowrap else P - 1, f"s{u}") for u in units}
    o = {(u, l): m.NewIntVar(1, P - 2, f"o{u}{l}") for u in units for l in range(6)}
    t = {}
    revs = {}
    for u in units:
        m.AddAllDifferent([o[(u, l)] for l in range(6)])
        for l in range(6):
            t[F.idx[(u[0], u[1], l)]] = s[u] + o[(u, l)]
        ordr = C.orders[u[0]][ccol[u[1]]]
        rev = m.NewBoolVar(f"rev{u}")
        revs[u] = rev
        first_constraints(m, o, u, ordr, rev)
    m.Add(s[("X", 0)] == 0)
    tv = {}
    for i, it in enumerate(F.items):
        v = m.NewIntVar(0, 2 * P, f"t{i}")
        m.Add(v == t[i]); tv[i] = v
    modv = {}
    for i in tv:
        mv = m.NewIntVar(0, P - 1, f"m{i}")
        m.AddModuloEquality(mv, tv[i], P); modv[i] = mv
    for q in range(144):
        its = sorted({F.item(ty, c, lab) for ty, c, lab in F.touch[q]})
        assert len(its) == 6
        m.AddAllDifferent([modv[i] for i in its])
    seen = set()
    for ia in range(N2):
        qa = set(int(x) for x in T["X"][ia])
        for ic in range(N2):
            ov = sorted(qa & set(int(x) for x in T["Z"][ic]))
            if not ov:
                continue
            pr = [(F.item("X", ia, F.label_of("X", ia, q)), F.item("Z", ic, F.label_of("Z", ic, q))) for q in ov]
            key = tuple(pr)
            if key in seen:
                continue
            seen.add(key)
            fl = []
            for ix, iz in pr:
                f = m.NewIntVar(0, 6, "")
                num = m.NewIntVar(-2 * P, 5 * P, "")
                m.Add(num == tv[ix] - tv[iz] + 3 * P)
                m.AddDivisionEquality(f, num, P)
                fl.append(f)
            m.Add(fl[0] == fl[1])
    print(f"P={P} nowrap={a.nowrap} col={col} reps {len(recs)} skipped {skipped} det-pairs {len(seen)} "
          f"{time.time() - t0:.0f}s", flush=True)
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
    tag = a.tag or f"cg_{col[0]}{col[1]}{col[2]}_P{P}{'_nw' if a.nowrap else ''}"
    log = {"P": P, "col": col, "x": a.x, "z": a.z, "nowrap": a.nowrap, "reps": len(recs), "skipped": skipped,
           "iters": [], "lift_rejects": []}
    status, it, ncand = "UNKNOWN", 0, 0
    while time.time() - t0 < a.max_sec:
        it += 1
        solver = cp_model.CpSolver()
        solver.parameters.num_workers = 1
        solver.parameters.random_seed = a.seed + it
        solver.parameters.max_time_in_seconds = max(10.0, a.max_sec - (time.time() - t0))
        st = solver.Solve(m)
        if st == cp_model.INFEASIBLE:
            status = "UNSAT"; break
        if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            status = "UNKNOWN"; break
        tval = {i: solver.Value(tv[i]) for i in tv}
        if a.nologic:
            lif = []
        else:
            import search.experiments.e021.nwfull as NF
            NF.bf_general = lambda cons, rank: bf_P(cons, tval, P)  # noqa: E731
            lif = evaluate_full(F, recs, None)
        if not lif:
            ncand += 1
            d = {"format": "qec-schedule/v1", "period": P, "x_checks": [], "z_checks": []}
            for ty, key in (("X", "x_checks"), ("Z", "z_checks")):
                for i in range(N2):
                    u = (ty, F.cls[i])
                    sv = solver.Value(s[u])
                    cn = [[int(T[ty][i][l]), (sv + solver.Value(o[(u, l)])) % P] for l in range(6)]
                    d[key].append({"prep": sv % P, "meas": (sv + P - 1) % P, "cnots": cn})
            sp = OUT / f"{tag}_cand{ncand}.json"
            sp.write_text(json.dumps(d))
            r = lift_screen(d, C, a.rmax)
            r["spec"] = str(sp)
            print(f"it {it} model candidate -> exact {r['status']} {r.get('R')} {r.get('basis')} "
                  f"{time.time() - t0:.0f}s", flush=True)
            if r["status"] == "CERTIFIED":
                status = "CERTIFIED"; log["spec"] = str(sp); break
            log["lift_rejects"].append({k: v for k, v in r.items() if k != "per"})
            if ncand >= a.maxcand:
                status = "MAXCAND"; break
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
    log.update(status=status, iterations=it, sec=round(time.time() - t0, 1), candidates=ncand)
    print(f"STATUS P={P} {status} it={it} cands={ncand} {log['sec']}s", flush=True)
    (OUT / f"{tag}.json").write_text(json.dumps(log))


if __name__ == "__main__":
    main()
