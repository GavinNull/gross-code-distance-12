"""E-041 exact oracle for one OFFSET VECTOR: every check k's 6 CNOTs inside the fixed 7-layer window
[s_k + 1, s_k + 7] (W9: P = 9, prep s_k, meas s_k + 8 = s_k + P - 1; Mg8: P = 8, prep s_k, meas s_k + 8 = s_k + P,
merged layer).  Every schedule of W9 / Mg8 has such a window vector (theory C lemma 2: span <= 6), so the cubes over
all vectors cover the class.

Encoding: e038.enc.Enc machinery (audited: LT literals, distinctness, mod-P data distinctness, determinism parity),
with tau domains restricted to the windows and pi / mu constants.  Witness clauses: e038.cegar.PatternEncoder on
the static (complete) pattern lists of e039.static for the chosen types; remaining types lazily (CEGAR on witnesses of
SAT models, exact bulk check with e038.model.bulk_min W = 6 and W = 12).
Result: FOUND (schedule with no bulk weight <= 3 witness, both bases) or UNSAT (no schedule with this window vector;
with --types HH,HHM,DDH,DHH,HHH complete, or exact CEGAR fixpoint) or TIMEOUT.
usage: uv run python -m search.experiments.e041.offcube --P 9 --starts 0,3,...(14 values) [--static HH,HHM,DDH,DHH]"""
from __future__ import annotations

import argparse
import itertools
import json
import time

from pysat.solvers import Solver

from search.experiments.e036_audit.core import checks, support
from search.experiments.e038.cegar import PatternEncoder, pattern_of
from search.experiments.e038.enc import Enc, IntVar
from search.experiments.e038.model import bulk_min
from search.experiments.e039.static import multisets, patterns_of

OUT = "results/E-041-bb18-p9"


class EncWin(Enc):
    def __init__(self, P, starts, variant="bb18"):
        self.variant, self.cls = variant, "Win"
        self.nv = 0
        self.cl = []
        self.ks = checks(variant)
        self.ev = [(k, a) for k in self.ks for a in range(6)]
        self.P = P
        self.pi = {k: IntVar(self, s, s) for k, s in zip(self.ks, starts)}
        self.mu = {k: IntVar(self, s + 8, s + 8) for k, s in zip(self.ks, starts)}
        self.tau = {(k, a): IntVar(self, s + 1, s + 7) for k, s in zip(self.ks, starts) for a in range(6)}
        self.ltc, self.andc, self.xorc = {}, {}, {}
        for k in self.ks:
            for e1, e2 in itertools.combinations([(k, a) for a in range(6)], 2):
                self.distinct(e1, e2, mod=False)
        self.onq = {}
        for k in self.ks:
            for a, q in enumerate(support(k)):
                self.onq.setdefault(q, []).append((k, a))
        for q, evs in self.onq.items():
            for e1, e2 in itertools.combinations(evs, 2):
                self.distinct(e1, e2, mod=True)
        for kx in self.ks:
            if kx[0] != "X":
                continue
            for kz in self.ks:
                if kz[0] != "Z":
                    continue
                sx, sz = support(kx), support(kz)
                sh = [q for q in sx if q in sz]
                if not sh:
                    continue
                for i in (-2, -1, 0, 1, 2):
                    lits = [self.LT((kx, sx.index(q)), (kz, sz.index(q)), i) for q in sh]
                    self.xor_const(lits, 0)


def solve_cube(P, starts, static, max_iter=10000, solver="cadical195", time_limit=None, log=None):
    t0 = time.time()
    E = EncWin(P, starts)
    PE = PatternEncoder(E)
    pats = set()
    empty = False
    for b in ("Z", "X"):
        for m in multisets("bb18", b, set(static)):
            for pat in patterns_of(b, m):
                pats.add(pat)
                for c in PE.clauses(pat):
                    if not c:
                        empty = True
                    E.add(c)
    tb = time.time() - t0
    if empty:
        return {"result": "UNSAT", "how": "empty clause at build", "build_sec": round(tb, 1), "iters": 0}
    s = Solver(name=solver, bootstrap_with=E.cl)
    ptr = len(E.cl)
    for it in range(max_iter):
        for c in E.cl[ptr:]:
            s.add_clause(c)
        ptr = len(E.cl)
        if not s.solve():
            return {"result": "UNSAT", "iters": it, "patterns": len(pats), "vars": E.nv, "clauses": len(E.cl),
                    "build_sec": round(tb, 1), "sec": round(time.time() - t0, 1)}
        sch = E.decode(s.get_model())
        w, wits = bulk_min(sch, 3, W=6, want_all=True, limit=500)
        if w is None:
            w, wits = bulk_min(sch, 3, W=12, want_all=True, limit=500)
            if w is None:
                return {"result": "FOUND", "iters": it, "sched": sch.to_json(), "sec": round(time.time() - t0, 1)}
        new = 0
        for b, tags in wits:
            pat = pattern_of(b, tags)
            if pat in pats:
                continue
            pats.add(pat)
            new += 1
            for c in PE.clauses(pat):
                if not c:
                    empty = True
                E.add(c)
        if empty:
            return {"result": "UNSAT", "how": "empty clause", "iters": it}
        if new == 0:
            raise RuntimeError("CEGAR made no progress: abstraction failed")
        if log:
            log.write(json.dumps({"it": it, "w": w, "nwit": len(wits), "new": new, "sec": round(time.time() - t0, 1)})
                      + "\n")
            log.flush()
        if time_limit and time.time() - t0 > time_limit:
            return {"result": "TIMEOUT", "iters": it, "sec": round(time.time() - t0, 1)}
    return {"result": "MAXITER"}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--P", type=int, default=9)
    ap.add_argument("--starts", required=True)
    ap.add_argument("--static", default="HH,HHM,DDH,DHH")
    ap.add_argument("--time", type=float, default=3600)
    a = ap.parse_args()
    starts = [int(x) for x in a.starts.split(",")]
    assert len(starts) == 14
    tag = f"offcube_P{a.P}_" + "".join(map(str, starts))
    log = open(f"{OUT}/{tag}.log", "a")
    r = solve_cube(a.P, starts, a.static.split(","), time_limit=a.time, log=log)
    r.update({"P": a.P, "starts": starts, "static": a.static})
    print(json.dumps(r), flush=True)
    log.write(json.dumps(r) + "\n")
    with open(f"{OUT}/offcube.jsonl", "a") as f:
        f.write(json.dumps(r) + "\n")
    if r["result"] == "FOUND":
        json.dump(r["sched"], open(f"{OUT}/found_{tag}.json", "w"))
