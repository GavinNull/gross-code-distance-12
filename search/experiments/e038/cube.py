"""E-038 cube-and-conquer pattern-CEGAR for a class N(S) or W(P).

Cubes = all injective assignments of the layers of the 6 CNOTs of the first check (X0) to 1..S (S!/(S-6)! cubes);
legality forces exactly one cube to hold for every schedule, so the class is UNSAT iff every cube is.  Inside a cube:
the CEGAR loop of cegar.py (SAT under the cube assumptions -> bulk witness search -> pattern clauses, which are global).
Shards: cube index i is handled by shard i mod n.  Patterns found are saved per shard; the final certificate uses the
UNION of all pattern files (adding sound clauses keeps every cube UNSAT).
usage: uv run python -m search.experiments.e038.cube N 7 --shard 0/3 --resume a.json,b.json
"""
import argparse
import itertools
import json
import random
import time

from pysat.solvers import Solver

from search.experiments.e038.cegar import OUT, PatternEncoder, expand, load_patterns, pattern_of, save_patterns
from search.experiments.e038.enc import Enc
from search.experiments.e038.model import bulk_min, legal


def cubes(E, S):
    """N(S): layers 1..S.  W(P): the first check has pi = 0 fixed, so its events lie in 1..P-2."""
    k0 = E.ks[0]
    out = []
    hi = S if E.cls == "N" else E.P - 2
    for lay in itertools.permutations(range(1, hi + 1), 6):
        out.append([E.tau[(k0, a)].eq(t) for a, t in enumerate(lay)])
    return out


def main(variant, S, shard, nsh, resume, d, W, limit, do_expand, seed, cls="N"):
    E = Enc(variant, cls, S)
    PE = PatternEncoder(E)
    pats = {}
    for path in resume:
        for pat in load_patterns(path):
            if pat not in pats:
                cl = PE.clauses(pat)
                pats[pat] = len(cl)
                for c in cl:
                    E.add(c)
    allc = cubes(E, S)
    order = list(range(len(allc)))
    random.Random(seed).shuffle(order)
    mine = [i for j, i in enumerate(order) if j % nsh == shard]
    s = Solver(name="cd15", bootstrap_with=E.cl)
    ptr = len(E.cl)
    tag = f"{variant}_{cls}{S}_d{d}_cube{shard}of{nsh}"
    log = open(f"{OUT}/{tag}.log", "a")
    t0 = time.time()
    done = 0
    for ci in mine:
        ass = [l for l in allc[ci] if l is not True]
        assert all(l is not False for l in ass)
        it = 0
        tc = time.time()
        while True:
            for c in E.cl[ptr:]:
                s.add_clause(c)
            ptr = len(E.cl)
            if not s.solve(assumptions=ass):
                break
            sch = E.decode(s.get_model())
            assert legal(sch)[0]
            w, wits = bulk_min(sch, d - 1, W=W, want_all=True, limit=limit)
            if w is None:
                w, wits = bulk_min(sch, d - 1, W=12, want_all=True, limit=limit)
                if w is None:
                    res = {"result": "FOUND", "cube": ci, "sched": sch.to_json()}
                    print(json.dumps(res), flush=True)
                    log.write(json.dumps(res) + "\n")
                    json.dump(sch.to_json(), open(f"{OUT}/found_{tag}_{ci}.json", "w"))
                    save_patterns(f"{OUT}/{tag}_patterns.json", pats)
                    return
            new = 0
            for b, tags in wits:
                base = pattern_of(b, tags)
                for pat in (expand(base) if do_expand else [base]):
                    if pat in pats:
                        continue
                    cl = PE.clauses(pat)
                    pats[pat] = len(cl)
                    for c in cl:
                        E.add(c)
                    new += 1
            assert new, "abstraction failed"
            it += 1
        done += 1
        msg = json.dumps({"cube": ci, "iters": it, "sec": round(time.time() - tc, 1), "done": done, "of": len(mine),
                          "patterns": len(pats), "total_sec": round(time.time() - t0, 1)})
        log.write(msg + "\n")
        log.flush()
        if done % 20 == 0:
            print(msg, flush=True)
            save_patterns(f"{OUT}/{tag}_patterns.json", pats)
    save_patterns(f"{OUT}/{tag}_patterns.json", pats)
    res = {"result": "ALL_CUBES_UNSAT", "shard": shard, "nsh": nsh, "cubes": len(mine), "patterns": len(pats),
           "sec": round(time.time() - t0, 1)}
    print(json.dumps(res), flush=True)
    log.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cls")
    ap.add_argument("S", type=int)
    ap.add_argument("--variant", default="bb18")
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--resume", default="")
    ap.add_argument("--d", type=int, default=4)
    ap.add_argument("--W", type=int, default=6)
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--expand", action="store_true")
    ap.add_argument("--seed", type=int, default=20261026)
    a = ap.parse_args()
    sh, n = map(int, a.shard.split("/"))
    main(a.variant, a.S, sh, n, [p for p in a.resume.split(",") if p], a.d, a.W, a.limit, a.expand, a.seed, a.cls)
