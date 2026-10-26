"""E-039 large-neighbourhood search for a d_circ = 4 schedule (heuristic; never used for impossibility claims).
State: a legal schedule satisfying the static clauses (scegar.Driver: legality + HH, HHM, DDH patterns, both bases).
Step: free 2-4 checks (biased to checks occurring in the current witnesses), fix every other check's CNOT times by
assumptions, SAT-solve with random phases (all learned clauses are sound global nogoods), evaluate the bulk witnesses
(W = 6, both bases); every witness pattern is added as a clause (so the neighbourhoods progressively exclude it);
accept the neighbour if its witness count is <= current (or with SA probability).  0 witnesses (W = 6 and 12) -> FOUND.
usage: uv run python -m search.experiments.e039.lns W 9 --start s.json --hours 2 --seed 1 [--spec X=0]"""
import argparse
import json
import math
import random
import time

from search.experiments.e038.cegar import pattern_of
from search.experiments.e038.model import Sched, bulk_min
from search.experiments.e039.scegar import OUT, Driver


def witnesses(s):
    w, wits = bulk_min(s, 3, W=6, want_all=True, limit=3000)
    return w, wits


def checks_of(tags):
    out = set()
    for t in tags:
        if t[0] == "H":
            out.add(t[1])
        elif t[0] == "D":
            out.add(t[2][0])
        else:
            out.add(t[1])
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cls")
    ap.add_argument("P", type=int)
    ap.add_argument("--start")
    ap.add_argument("--hours", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--T", type=float, default=1.0)
    ap.add_argument("--static", default="HH,HHM,DDH")
    a = ap.parse_args()
    rng = random.Random(a.seed)
    tag = f"lns_{a.cls}{a.P}_s{a.seed}"
    D = Driver(a.cls, a.P, a.static.split(","), [], tag=tag, seed=a.seed)
    E = D.E
    s = Sched.from_json(json.load(open(a.start)))
    w, wits = witnesses(s)
    for b, tags in wits:
        D.add(pattern_of(b, tags))
    cur = len(wits) * (1000 if w and w <= 2 else 1) if w else 0
    best = cur
    t0 = time.time()
    it = 0
    while time.time() - t0 < a.hours * 3600:
        it += 1
        hot = [k for b, tags in wits for k in checks_of(tags)] if wits else list(E.ks)
        nf = rng.choice((2, 3, 3, 4))
        free = set()
        while len(free) < nf:
            free.add(rng.choice(hot) if rng.random() < 0.7 else rng.choice(E.ks))
        ass = D.fix_lits(s, free)
        D.sync()
        D.s.set_phases([v if rng.random() < 0.5 else -v for v in range(1, E.nv + 1)])
        if not D.s.solve(assumptions=ass):
            continue
        t = E.decode(D.s.get_model())
        w2, wits2 = witnesses(t)
        for b, tags in wits2:
            D.add(pattern_of(b, tags))
        sc = 0 if w2 is None else len(wits2) * (1000 if w2 <= 2 else 1)
        if sc == 0:
            if bulk_min(t, 3, W=12)[0] is None:
                D.found(t, f"lns{it}")
                break
        if sc <= cur or rng.random() < math.exp(-(sc - cur) / a.T):
            s, cur, w, wits = t, sc, w2, wits2
            if cur < best:
                best = cur
                json.dump(s.to_json(), open(f"{OUT}/{tag}_best.json", "w"))
        if it % 20 == 0:
            D.logw({"it": it, "cur": cur, "best": best, "patterns": len(D.pats), "sec": round(time.time() - t0)})
    D.logw({"result": "END", "best": best, "it": it})
