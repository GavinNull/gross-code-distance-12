"""E-020: lazy-constraint (CEGAR) decision of the per-check-free pipelined family at period P in the bulk frame model.

Schedules: per-check options (absolute CNOT times, see plegal.py), legal + deterministic (plegal.build).
Bulk frame model (E-018 frame_model.feasible_general; audit 2026-10-08 C1: model-feasible => a genuine weight-11
undetected logical in the bulk of a long enough memory experiment): variables H_c (instance of reading check c in
which it sees Q∩c) and F_a per hook check; constraints
  free qubit w read by c, d:      H_c - H_d <= floor((t_d(w) - t_c(w))/P) + 1
  hook a, residual qubit q, c reads q:  H_c - F_a = floor((t_a(q) - t_c(q))/P) + 1     (two inequalities)
Modelled logicals: all weight-11 extended logicals (both kinds) whose 11 column supports are disjoint and with
|Q∩c| <= 2 for every reading check (then the model is exact in the bulk); others are ignored (sound for INFEASIBLE).

Loop: SAT -> schedule -> evaluate every modelled logical with Bellman-Ford; for each feasible (lifting) S with
potential pi (shortest-path distances), add the nogood
     OR over model constraints (u - w <= wt(schedule)) of  [ wt < pi_u - pi_w ]
which is valid: any schedule falsifying every literal keeps pi feasible, so S still lifts.  Each literal is a
difference condition on two absolute CNOT times (t1 - t2 <= M or t1 - t2 >= M), encoded as literal -> condition.
UNSAT => every legal deterministic schedule of the family has a bulk weight-11 undetected logical (d_circ <= 11 for
large R).  SAT with no lifting modelled logical => candidate (then exact lift).

    PYTHONPATH=.:tests uv run python -m search.experiments.e020.cegar --P 9 --kinds XZ --types single
"""
from __future__ import annotations

import argparse
import json
import random
import time

from pysat.solvers import Cadical153

from search.experiments.e018.anal import comp
from search.experiments.e018.common import ext, orders
from search.experiments.e018.frame_model import column_events
from search.experiments.e018.screen import logicals
from search.experiments.e020.plegal import build

OUT = "results/E-020-gross-perchk-pipeline"


def prep_logicals(kinds, types):
    """list of (kind, S, model skeleton).  skeleton: list of constraints (u, w, kindof, data) with
    kindof 'free': data = (pd, pc) -> wt = floor((t[pd]-t[pc])/P)+1  (constraint H_c - H_d <= wt; u = c, w = d)
    kindof 'hook': data = (pa, pc, sign).  Node ids: ('c', check index in plegal order) / ('F', check index)."""
    xo, zo = orders()
    out, skipped = [], 0
    for kind in kinds:
        E = ext(kind)
        rd_off, rd_ord = (72, zo) if kind == "X" else (0, xo)   # reading checks (plegal index offset)
        hk_off, hk_ord = (0, xo) if kind == "X" else (72, zo)
        readers = {}
        for c, o in enumerate(rd_ord):
            for p, q in enumerate(o):
                readers.setdefault(q, []).append((rd_off + c, p))
        for S in logicals(kind, False):
            cp = comp(E, S)
            if types == "single" and cp not in ("d10 r21", "d10 r41"):
                continue
            evs = [column_events(kind, j) for j in S]
            qs = []
            for e in evs:
                qs += [e[1]] if e[0] == "d" else list(e[2])
            if len(set(qs)) != len(qs):
                skipped += 1; continue
            cnt = {}
            for q in qs:
                for c, _ in readers[q]:
                    cnt[c] = cnt.get(c, 0) + 1
            if max(cnt.values()) > 2:
                skipped += 1; continue
            cons = []
            for e in evs:
                if e[0] == "d":
                    q = e[1]
                    for c, pc in readers[q]:
                        for d, pd in readers[q]:
                            if c != d:
                                cons.append((("c", c), ("c", d), "free", ((d, pd), (c, pc))))
                else:
                    a = hk_off + e[1]
                    ho = hk_ord[e[1]]
                    for q in e[2]:
                        pa = list(ho).index(q)
                        for c, pc in readers[q]:
                            cons.append((("c", c), ("F", a), "hook+", ((a, pa), (c, pc))))
                            cons.append((("F", a), ("c", c), "hook-", ((a, pa), (c, pc))))
            out.append((kind, tuple(int(j) for j in S), cp, cons))
    return out, skipped


def weight(kd, data, T, P):
    (p1, p2) = data
    f = (T[p1] - T[p2]) // P + 1
    return f if kd != "hook-" else -f


def bellman_ford(cons, T, P):
    """returns potential dict if feasible, else None.  constraint (u, w, ...): h[u] - h[w] <= wt."""
    nodes = {}
    edges = []
    for u, w, kd, data in cons:
        iu = nodes.setdefault(u, len(nodes)); iw = nodes.setdefault(w, len(nodes))
        edges.append((iu, iw, weight(kd, data, T, P)))
    d = [0] * len(nodes)
    for _ in range(len(nodes) + 1):
        ch = False
        for iu, iw, wt in edges:
            if d[iw] + wt < d[iu]:
                d[iu] = d[iw] + wt; ch = True
        if not ch:
            return {k: d[i] for k, i in nodes.items()}
    return None


class Lits:
    """Absolute-time literals and difference-condition literals on top of plegal's CNF."""

    def __init__(self, P, C, O, x, pool, solver):
        self.P, self.C, self.O, self.x, self.pool, self.S = P, C, O, x, pool, solver
        self.T = {}
        self.cache = {}
        self.nclauses = 0

    def tlit(self, ci, p, t):
        key = (ci, p, t)
        if key not in self.T:
            v = self.pool.id(("T",) + key)
            opts = [self.x[ci][k] for k, o in enumerate(self.O) if o[p] == t]
            self.S.add_clause([-v] + opts)
            for l in opts:
                self.S.add_clause([-l, v])
            self.T[key] = v
        return self.T[key]

    def tvals(self, ci, p):
        return sorted({o[p] for o in self.O})

    def diff(self, p1, p2, op, M):
        """literal l with l -> (t[p1] - t[p2] <= M) (op 'le') or (>= M) (op 'ge')."""
        key = (p1, p2, op, M)
        if key in self.cache:
            return self.cache[key]
        l = self.pool.id(("D",) + key)
        for t2 in self.tvals(*p2):
            ok = [t1 for t1 in self.tvals(*p1) if (t1 - t2 <= M if op == "le" else t1 - t2 >= M)]
            self.S.add_clause([-l, -self.tlit(*p2, t2)] + [self.tlit(*p1, t1) for t1 in ok])
        self.cache[key] = l
        return l

    def nogood(self, cons, pi, gmaps=(None,)):
        """adds the nogood and its images under the check permutations in gmaps (translation symmetry: valid
        because the family, the model and the logical set are invariant under the 24 order-preserving translations)."""
        n = 0
        for gm in gmaps:
            n = self._nogood(cons, pi, gm)
        return n

    def _nogood(self, cons, pi, gm):
        P = self.P
        mp = (lambda pp: pp) if gm is None else (lambda pp: (gm[pp[0]], pp[1]))
        cl = []
        for u, w, kd, (p1, p2) in cons:
            p1, p2 = mp(p1), mp(p2)
            K = pi[u] - pi[w]                 # need wt < K to violate
            if kd in ("free", "hook+"):       # floor((t1-t2)/P) + 1 < K  <=> t1 - t2 <= (K-1)P - 1
                cl.append(self.diff(p1, p2, "le", (K - 1) * P - 1))
            else:                             # -(floor((t1-t2)/P)+1) < K <=> floor(..) > -K-1 <=> t1-t2 >= -K*P
                cl.append(self.diff(p1, p2, "ge", -K * P))
        cl = sorted(set(cl))
        self.S.add_clause(cl)
        self.nclauses += 1
        return len(cl)


def schedule_times(sv, O):
    T = {}
    for ci, k in enumerate(sv):
        for p, t in enumerate(O[k]):
            T[(ci, p)] = t
    return T


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--P", type=int, default=9)
    ap.add_argument("--kinds", default="XZ")
    ap.add_argument("--types", default="single")
    ap.add_argument("--max_iter", type=int, default=100000)
    ap.add_argument("--max_sec", type=float, default=36000)
    ap.add_argument("--per_iter", type=int, default=10 ** 9, help="max nogoods added per iteration")
    ap.add_argument("--seed", type=int, default=20261008)
    ap.add_argument("--tag", default="")
    ap.add_argument("--sym", type=int, default=1, help="add the 24 translated images of every nogood / det clause")
    a = ap.parse_args()
    rng = random.Random(a.seed)
    from search.experiments.e018.common import tr
    gmaps = [None]
    if a.sym:
        gmaps = []
        for g in ext("X")["group"]:
            pm, _ = tr(*g)
            gmaps.append([int(pm[i]) for i in range(72)] + [72 + int(pm[j]) for j in range(72)])
    t0 = time.time()
    L, skipped = prep_logicals(a.kinds, a.types)
    print(f"modelled logicals {len(L)} (skipped {skipped}) {time.time() - t0:.0f}s", flush=True)
    C, O, x, cnf, pool = build(a.P, lazy_det=True)
    dett = pool.det_table
    S = Cadical153(bootstrap_with=cnf)
    lits = Lits(a.P, C, O, x, pool, S)
    log = {"P": a.P, "kinds": a.kinds, "types": a.types, "modelled": len(L), "skipped": skipped, "iters": []}
    tag = a.tag or f"P{a.P}_{a.kinds}_{a.types}"
    status = "UNKNOWN"
    it = 0
    while it < a.max_iter and time.time() - t0 < a.max_sec:
        it += 1
        ts = time.time()
        if not S.solve():
            status = "UNSAT"
            break
        pos = set(l for l in S.get_model() if l > 0)
        sv = [next(k for k in range(len(O)) if x[ci][k] in pos) for ci in range(len(C))]
        T = schedule_times(sv, O)
        ndv = 0
        for (ca, cc), (ga, gc, (pau, pav, pcu, pcv)) in dett.items():
            g1 = (T[(ca, pau)], T[(ca, pav)]); g2 = (T[(cc, pcu)], T[(cc, pcv)])
            if (g1[0] - g2[0]) // a.P != (g1[1] - g2[1]) // a.P:
                for gm in gmaps:
                    k = (ca, cc) if gm is None else (gm[ca], gm[cc])
                    S.add_clause([-dett[k][0][g1], -dett[k][1][g2]])
                ndv += 1
        lifting = []
        for kind, Sx, cp, cons in L:
            pi = bellman_ford(cons, T, a.P)
            if pi is not None:
                lifting.append((cons, pi))
        if not lifting and ndv == 0:
            status = "CANDIDATE"
            log["candidate"] = [list(O[k]) for k in sv]
            break
        rng.shuffle(lifting)
        sizes = [lits.nogood(cons, pi, gmaps) for cons, pi in lifting[: a.per_iter]] or [0]
        rec = {"it": it, "det_viol": ndv, "lifting": len(lifting), "added": len(sizes),
               "mean_clause": round(sum(sizes) / len(sizes), 1),
               "sec": round(time.time() - ts, 2)}
        log["iters"].append(rec)
        if it % 10 == 0 or it < 5:
            print(rec, f"total {time.time() - t0:.0f}s", flush=True)
            json.dump(log, open(f"{OUT}/cegar_{tag}.json", "w"))
    log["status"] = status
    log["iterations"] = it
    log["nogoods"] = lits.nclauses
    log["sec"] = round(time.time() - t0, 1)
    print(f"STATUS {status} after {it} iterations, {lits.nclauses} nogoods, {log['sec']}s", flush=True)
    json.dump(log, open(f"{OUT}/cegar_{tag}.json", "w"))


if __name__ == "__main__":
    main()
