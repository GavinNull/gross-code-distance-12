"""E-039: check the finite-R pattern clauses (finite.FinitePE) against the finite mechanism list (finite.mechs, which
equals the stim DEM: validate_finite) on random legal N(S) schedules.  For every sampled pattern and every reader
choice f*: "clause false under the schedule" must hold iff the corresponding mechanisms XOR to zero detectors with a
non-zero observable.  Patterns: all witnesses of the schedule (positives) + random patterns of all static types.
usage: uv run python -m search.experiments.e039.validate_finite_clauses --R 1 --n 10"""
import argparse
import itertools
import json
import random

from pysat.solvers import Solver

from search.experiments.e036_audit.core import min_weight_le
from search.experiments.e038.enc import Enc
from search.experiments.e039 import finite
from search.experiments.e039.finite_static import TYPES, patterns
from search.experiments.e039.static import multisets

ap = argparse.ArgumentParser()
ap.add_argument("--S", type=int, default=7)
ap.add_argument("--R", type=int, default=1)
ap.add_argument("--n", type=int, default=10)
ap.add_argument("--neg", type=int, default=400)
ap.add_argument("--seed", type=int, default=9)
a = ap.parse_args()
rng = random.Random(a.seed)
E = Enc("bb18", "N", a.S)
PE = finite.FinitePE(E, a.R)
allp = []
for b in "ZX":
    for m in multisets("bb18", b, set(TYPES)):
        allp += patterns(b, m, a.R)
s = Solver(name="cd15", bootstrap_with=E.cl)
ptr = len(E.cl)
tot = {"R": a.R, "schedules": 0, "pos": 0, "neg": 0, "neg_cancel": 0, "mismatch": 0}
for it in range(a.n):
    ass = []
    for e in rng.sample(E.ev, 6):
        l = E.tau[e].eq(rng.randint(1, a.S))
        if l not in (True, False):
            ass.append(l)
    for c in E.cl[ptr:]:
        s.add_clause(c)
    ptr = len(E.cl)
    s.set_phases([v if rng.random() < 0.5 else -v for v in range(1, E.nv + 1)])
    if not s.solve(assumptions=ass):
        continue
    sch = E.decode(s.get_model())
    tot["schedules"] += 1
    mech = {b: {m[2]: (m[0], m[1]) for m in finite.mechs(sch, b, a.R)} for b in "ZX"}
    pos = []
    for b in "ZX":
        ms = finite.mechs(sch, b, a.R)
        w, wits = min_weight_le(ms, 3, want_all=True, limit=300)
        pos += [finite.pattern_abs(b, [ms[i][2] for i in t]) for t in wits]
    cand = [(p, True) for p in pos] + [(p, False) for p in rng.sample(allp, a.neg)]
    cls = {p: PE.clauses(p) for p, _ in cand}
    for c in E.cl[ptr:]:
        s.add_clause(c)
    ptr = len(E.cl)
    fix = []
    for e, iv in E.tau.items():
        for tt, v in iv.u.items():
            fix.append(v if sch.tau[e] <= tt else -v)
    assert s.solve(assumptions=fix)
    mod = set(s.get_model())
    for p, ispos in cand:
        b, slots = p
        falsified = any(all(-l in mod for l in c) for c in cls[p])
        # ground truth from the mechanism list: some choice of f* per D slot gives a cancelling logical
        rev = {q: [(k, i) for k in sch.ks if k[0] == b for i, qq in enumerate(finite.support(k)) if qq == q]
               for q in range(18)}
        dsl = [x for x in slots if x[0] == "D"]
        truth = False
        for ch in itertools.product(*[rev[x[1]] for x in dsl]):
            d = o = 0
            di = 0
            ok = True
            for x in slots:
                if x[0] == "D":
                    tag = ("D", x[1], ch[di], x[2])
                    di += 1
                elif x[0] == "H":
                    tag = ("H", x[1], frozenset(x[2]), x[3])
                else:
                    tag = ("M", x[1], x[2])
                if tag not in mech[b]:
                    ok = False      # hook set U is not a suffix in this schedule
                    break
                dd, oo = mech[b][tag]
                d ^= dd
                o ^= oo
            if ok and d == 0 and o:
                truth = True
                break
        tot["pos" if ispos else "neg"] += 1
        tot["neg_cancel"] += (not ispos) and truth
        if falsified != truth or (ispos and not truth):
            tot["mismatch"] += 1
            print("MISMATCH", p, falsified, truth, flush=True)
print(json.dumps(tot))
with open("results/E-039-bb18-pipe/validate_finite_clauses.jsonl", "a") as f:
    f.write(json.dumps(tot) + "\n")
