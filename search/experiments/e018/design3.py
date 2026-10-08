"""E-018 stage c: CP-SAT existence question for ANY periodic single-ancilla schedule (pipelined / wrapping allowed,
period P, Fig. 12 per-check CNOT orders, ancilla gaps allowed): can every single-hook weight-11 logical
(10 data + one r2 hook) be blocked in the general frame model (`frame_model.feasible_general`)?

Schedule variables per check (or per (type, colour) class in --mode sym): prep s in [0, P-1], CNOT offsets
1 <= o_1 < ... < o_6 <= P-2 (meas at s + o_6 + 1 <= s + P - 1); absolute CNOT times t = s + o.
Constraints: data conflicts (t mod P distinct per data qubit); determinism: for each overlapping X/Z pair with shared
u, v: ceil((t_a(u) - t_c(u))/P) == ceil((t_a(v) - t_c(v))/P)  (same relative instance on both shared qubits);
blocking certificate per logical: a path in the difference graph from a hook check x (H_x = F + delta_x) to a hook
check y with accumulated bound dist[y] < delta_y, where free-qubit edges d -> c (shared w) have weight
floor((t_d(w) - t_c(w))/P) + 1.  (dist/rank variables; paths through |Q∩c| = 2 checks only.)
In the frame model, blocking a single-hook logical <=> such a path exists (negative cycle through F once).

    PYTHONPATH=.:tests uv run python -m search.experiments.e018.design3 --mode sym --P 8 --bases Z
"""
from __future__ import annotations

import argparse
import json
import time

from ortools.sat.python import cp_model

from search.experiments.e018.anal import comp
from search.experiments.e018.common import ext, orders
from search.experiments.e018.frame_model import column_events
from search.experiments.e018.gen import XCOL, ZCOL
from search.experiments.e018.lift import KIND_OF_BASIS
from search.experiments.e018.screen import logicals


def build(P, mode, bases, types, assume=False, fix=None):
    xo, zo = orders()
    m = cp_model.CpModel()
    if mode == "sym":
        keyof = {("X", i): ("X", int(XCOL[i])) for i in range(72)} | {("Z", j): ("Z", int(ZCOL[j])) for j in range(72)}
    else:
        keyof = {(k, i): (k, i) for k in "XZ" for i in range(72)}
    var = {}
    for key in set(keyof.values()):
        s = m.NewIntVar(0, P - 1, "")
        o = [m.NewIntVar(1, P - 2, "") for _ in range(6)]
        for k in range(5):
            m.Add(o[k + 1] > o[k])
        var[key] = (s, o)
        if fix and str(key) in fix:
            fs, fo = fix[str(key)]
            m.Add(s == fs)
            for k in range(6):
                m.Add(o[k] == fo[k])
    pos = {("X", i): {q: k for k, q in enumerate(xo[i])} for i in range(72)} | \
          {("Z", j): {q: k for k, q in enumerate(zo[j])} for j in range(72)}
    tcache = {}

    def T(k, i, q):
        kk = (keyof[(k, i)], pos[(k, i)][q])
        if kk not in tcache:
            s, o = var[kk[0]]
            t = m.NewIntVar(1, 2 * P - 3, "")
            m.Add(t == s + o[kk[1]])
            tcache[kk] = t
        return tcache[kk]
    modc = {}

    def Tmod(k, i, q):
        t = T(k, i, q)
        if t.Index() not in modc:
            r = m.NewIntVar(0, P - 1, "")
            m.AddModuloEquality(r, t, P)
            modc[t.Index()] = r
        return modc[t.Index()]
    touch = [[] for _ in range(144)]
    for k, ords in (("X", xo), ("Z", zo)):
        for i, o in enumerate(ords):
            for q in o:
                touch[q].append((k, i))
    done = set()
    for q in range(144):
        ex = [Tmod(k, i, q) for k, i in touch[q]]
        sig = tuple(sorted(e.Index() for e in ex))
        if sig not in done:
            done.add(sig)
            m.AddAllDifferent(ex)
    flc = {}

    def floordiv(k1, i1, k2, i2, q):
        """floor((T(k1,i1,q) - T(k2,i2,q)) / P) as an int var in [-2, 1]."""
        t1, t2 = T(k1, i1, q), T(k2, i2, q)
        key = (t1.Index(), t2.Index())
        if key not in flc:
            f = m.NewIntVar(-2, 1, "")
            # f*P <= t1 - t2 < (f+1)*P
            m.Add(f * P <= t1 - t2)
            m.Add(t1 - t2 < f * P + P)
            flc[key] = f
        return flc[key]
    for i in range(72):
        for j in range(72):
            sh = sorted(set(xo[i]) & set(zo[j]))
            if sh:
                u, v = sh
                # ceil(x/P) = floor((x-1)/P)+1; x never a multiple of P, so ceil equality <=> floor equality
                m.Add(floordiv("X", i, "Z", j, u) == floordiv("X", i, "Z", j, v))
    m.assume_lits = []
    nS = n4 = 0
    BIG = 8
    for basis in bases:
        kind = KIND_OF_BASIS[basis]
        rk = "Z" if kind == "X" else "X"
        rd_ords = zo if kind == "X" else xo
        E = ext(kind)
        for S in logicals(kind, mode == "sym"):
            if comp(E, S) not in types:
                continue
            nS += 1
            evs = [column_events(kind, j) for j in S]
            (_, a, res), = [e for e in evs if e[0] == "h"]
            free = [e[1] for e in evs if e[0] == "d"]
            Q = set(free) | set(res)
            rchk = {q: [c for c, o in enumerate(rd_ords) if q in o] for q in Q}
            qc = {}
            for q in Q:
                for c in rchk[q]:
                    qc.setdefault(c, []).append(q)
            good = {c for c, l in qc.items() if len(l) == 2}
            n4 += sum(len(l) > 2 for l in qc.values())
            nodes = sorted(good)
            R = {c: m.NewBoolVar("") for c in nodes}
            rank = {c: m.NewIntVar(0, len(nodes), "") for c in nodes}
            dist = {c: m.NewIntVar(-BIG, BIG, "") for c in nodes}
            fins = []
            for c in nodes:
                supp = []
                hq = [q for q in qc[c] if q in res]
                if hq:
                    q = hq[0]
                    delta = floordiv(kind, a, rk, c, q)          # H_c = F + delta + 1
                    b = m.NewBoolVar("")
                    m.Add(dist[c] == delta + 1).OnlyEnforceIf(b)
                    supp.append(b)
                    f = m.NewBoolVar("")
                    m.AddImplication(f, R[c])
                    m.Add(dist[c] < delta + 1).OnlyEnforceIf(f)
                    fins.append(f)
                for w in qc[c]:
                    if w in res:
                        continue
                    for d in rchk[w]:
                        if d == c or d not in good:
                            continue
                        e = m.NewBoolVar("")
                        m.AddImplication(e, R[d])
                        m.Add(rank[d] < rank[c]).OnlyEnforceIf(e)
                        # H_c <= H_d + floor((t_d - t_c)/P) + 1
                        m.Add(dist[c] == dist[d] + floordiv(rk, d, rk, c, w) + 1).OnlyEnforceIf(e)
                        supp.append(e)
                m.AddBoolOr(supp).OnlyEnforceIf(R[c])
            if assume:
                lit = m.NewBoolVar("")
                m.AddBoolOr(fins).OnlyEnforceIf(lit)
                m.assume_lits.append((lit, basis, S))
            else:
                m.AddBoolOr(fins)
    return m, var, nS, n4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--P", type=int, default=8)
    ap.add_argument("--mode", default="sym")
    ap.add_argument("--bases", default="Z")
    ap.add_argument("--types", default="d10 r21")
    ap.add_argument("--time", type=float, default=900)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    t0 = time.time()
    m, var, nS, n4 = build(a.P, a.mode, a.bases, a.types.split(","))
    print(f"model built: {nS} logicals, n4={n4}, {time.time() - t0:.0f}s", flush=True)
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = a.time
    s.parameters.num_workers = a.workers
    st = s.Solve(m)
    res = {"P": a.P, "mode": a.mode, "bases": a.bases, "types": a.types, "status": s.StatusName(st),
           "sec": round(time.time() - t0, 1), "nS": nS, "n4": n4}
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        res["sched"] = {str(k): [s.Value(v[0]), [s.Value(x) for x in v[1]]] for k, v in var.items()}
    print(json.dumps({k: v for k, v in res.items() if k != "sched"}), flush=True)
    json.dump(res, open(a.out, "w"))


if __name__ == "__main__":
    main()


def spec_from_sched(res):
    """ScheduleSpec from a design3 result (sym or free)."""
    import ast
    from evaluators.candidate import CheckTiming, ScheduleSpec
    P = res["P"]
    xo, zo = orders()
    sched = {ast.literal_eval(k): v for k, v in res["sched"].items()}

    def mk(k, i, o):
        key = (k, int(XCOL[i]) if k == "X" else int(ZCOL[i])) if res["mode"] == "sym" else (k, i)
        s, off = sched[key]
        return CheckTiming(s % P, (s + off[5] + 1) % P, tuple(sorted((int(q), (s + t) % P) for q, t in zip(o, off))))
    return ScheduleSpec(P, tuple(mk("X", i, xo[i]) for i in range(72)), tuple(mk("Z", j, zo[j]) for j in range(72)))
