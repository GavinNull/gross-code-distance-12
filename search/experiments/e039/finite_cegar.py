"""E-039: is there a non-wrapping N(S) schedule whose R-round memory experiment (exactly R rounds, both bases) has no
undetectable logical of weight <= d-1?  Pattern-CEGAR with the finite-R model (finite.py, validated vs stim and the
evaluator): SAT model -> exact min weight in finite.mechs (both bases) -> all min-weight witnesses as absolute-round
patterns -> FinitePE clauses (sound: if the clause is false in a schedule, the slots exist there and cancel with the
same non-trivial residual).  UNSAT -> DIMACS for DRAT.
usage: uv run python -m search.experiments.e039.finite_cegar --S 7 --R 1"""
import argparse
import json
import time

from pysat.solvers import Solver

from search.experiments.e036_audit.core import min_weight_le
from search.experiments.e038.cegar import save_patterns
from search.experiments.e038.enc import Enc
from search.experiments.e038.model import legal
from search.experiments.e039 import finite

OUT = "results/E-039-bb18-pipe"


def fmin(sch, R, d, limit=400):
    best, wits = None, []
    for b in ("Z", "X"):
        ms = finite.mechs(sch, b, R)
        w, ww = min_weight_le(ms, d - 1, want_all=True, limit=limit)
        if w is None:
            continue
        if best is None or w < best:
            best, wits = w, []
        if w == best:
            wits += [(b, [ms[i][2] for i in t]) for t in ww]
    return best, wits


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--S", type=int, default=7)
    ap.add_argument("--R", type=int, default=1)
    ap.add_argument("--d", type=int, default=4)
    ap.add_argument("--variant", default="bb18")
    a = ap.parse_args()
    tag = f"finite_{a.variant}_N{a.S}_R{a.R}_d{a.d}"
    E = Enc(a.variant, "N", a.S)
    PE = finite.FinitePE(E, a.R)
    s = Solver(name="cd15", bootstrap_with=E.cl)
    ptr = len(E.cl)
    pats = {}
    log = open(f"{OUT}/{tag}.log", "a")
    t0 = time.time()
    it = 0
    while True:
        for c in E.cl[ptr:]:
            s.add_clause(c)
        ptr = len(E.cl)
        ts = time.time()
        if not s.solve():
            res = {"result": "UNSAT", "iters": it, "patterns": len(pats)}
            break
        tsol = time.time() - ts
        sch = E.decode(s.get_model())
        assert legal(sch)[0]
        w, wits = fmin(sch, a.R, a.d)
        if w is None:
            res = {"result": "FOUND", "iters": it, "patterns": len(pats), "sched": sch.to_json()}
            json.dump(sch.to_json(), open(f"{OUT}/found_{tag}.json", "w"))
            break
        new = 0
        for b, tags in wits:
            pat = finite.pattern_abs(b, tags)
            if pat in pats:
                continue
            cl = PE.clauses(pat)
            assert all(len(c) for c in cl), pat
            pats[pat] = len(cl)
            for c in cl:
                E.add(c)
            new += 1
        assert new, "abstraction failed"
        it += 1
        if it % 10 == 0:
            msg = json.dumps({"it": it, "w": w, "patterns": len(pats), "solve": round(tsol, 2),
                              "sec": round(time.time() - t0, 1)})
            log.write(msg + "\n")
            log.flush()
            print(msg, flush=True)
    res.update({"S": a.S, "R": a.R, "d": a.d, "vars": E.nv, "clauses": len(E.cl), "sec": round(time.time() - t0, 1)})
    print(json.dumps(res), flush=True)
    log.write(json.dumps(res) + "\n")
    save_patterns(f"{OUT}/{tag}_patterns.json", list(pats))
    with open(f"{OUT}/{tag}.cnf", "w") as f:
        f.write(f"p cnf {E.nv} {len(E.cl)}\n")
        for c in E.cl:
            f.write(" ".join(map(str, c)) + " 0\n")
