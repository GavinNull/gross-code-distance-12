"""E-038 audit: the N7 pattern witnesses also hold WITHOUT ancilla reset (Kunlun's mode).  Random legal N7 schedules
from my legality CNF; every cancelling instance of final_N7_patterns is injected into the no-reset circuit
(npat.physical_noreset): must give 0 detectors and a flipped observable.  Also: >= 1 cancelling instance per schedule.
usage: uv run python -m search.experiments.e038_audit.b2b_noreset --n 60 --seed 21"""
import argparse
import json
import random

from pysat.solvers import Solver

from search.experiments.e038_audit import npat

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=60)
ap.add_argument("--seed", type=int, default=21)
a = ap.parse_args()
rng = random.Random(a.seed)
sem = npat.NSem(7)
pats = [npat.norm_pattern(p) for p in json.load(open("results/E-038-bb18-d4/final_N7_patterns.json"))]
G = npat.NCNF(7)
s = Solver(name="cadical195", bootstrap_with=G.cl)
tot = {"schedules": 0, "distinct": 0, "no_cancel": 0, "ok": 0, "bad": 0, "nondet": 0}
seen = set()
for it in range(a.n):
    ass = [G.x[e][rng.randint(1, 7)] for e in rng.sample(G.ev, 6)]
    s.set_phases([v if rng.random() < 0.5 else -v for v in range(1, G.nv + 1)])
    if not s.solve(assumptions=ass):
        continue
    tau = G.decode(s.get_model())
    tot["schedules"] += 1
    key = tuple(sorted((str(k), v) for k, v in tau.items()))
    if key not in seen:
        seen.add(key)
        tot["distinct"] += 1
    canc = [(i, ch) for i, p in enumerate(pats) for ch in sem.cancels(p, tau)]
    if not canc:
        tot["no_cancel"] += 1
    for i, ch in canc:
        d, o = npat.physical_noreset(pats[i], ch, tau, 7)
        if d < 0:
            tot["nondet"] += 1
        elif d == 0 and o > 0:
            tot["ok"] += 1
        else:
            tot["bad"] += 1
print(json.dumps(tot))
json.dump(tot, open("results/E-038-audit/b2b_noreset.json", "w"))
