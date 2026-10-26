"""E-039: checks of the static pattern clauses for a wrapping class (W P or Mg P), on random legal schedules.
  (1) completeness of the static enumeration: every bulk witness (model.bulk_min, all min-weight witnesses, W = 6) of a
      random legal schedule whose type is statically enumerated (HH, HHM, DDH) has its pattern in the static set;
  (2) my clauses = the auditor's independent semantics (e038_audit.gpat.GSem): for witness patterns (positives) and
      random static patterns (mostly negatives), "some clause of the pattern is false under the schedule" (Tseitin
      auxiliaries fixed by the definitional clauses) iff GSem.cancels(...) is non-empty;
  (3) physics: for cancelling patterns, gpat.physical (noiseless periodic stim circuit, faults injected) fires no
      detector and flips the observable.
usage: uv run python -m search.experiments.e039.validate_static W 8 --n 20"""
import argparse
import json
import random

from pysat.solvers import Solver

from search.experiments.e036_audit.core import support
from search.experiments.e038.cegar import PatternEncoder, pattern_of
from search.experiments.e038.model import bulk_min
from search.experiments.e038_audit import gpat, npat
from search.experiments.e039.legal2 import legal_any
from search.experiments.e039.scegar import make_enc
from search.experiments.e039.static import multisets, patterns_of

ap = argparse.ArgumentParser()
ap.add_argument("cls")
ap.add_argument("P", type=int)
ap.add_argument("--n", type=int, default=20)
ap.add_argument("--neg", type=int, default=300)
ap.add_argument("--phys", type=int, default=15)
ap.add_argument("--seed", type=int, default=3)
ap.add_argument("--exclude", default="", help="static types whose clauses are imposed while sampling, e.g. HH,HHM")
a = ap.parse_args()
rng = random.Random(a.seed)
E = make_enc(a.cls, a.P)
PE = PatternEncoder(E)
static = {}
for b in "ZX":
    for m in multisets("bb18", b, {"HH", "HHM", "DDH"}):
        for p in patterns_of(b, m):
            static[p] = None
allstatic = list(static)
ncl0 = len(E.cl)


def clauses_sep(p):
    n0 = len(E.cl)
    cl = PE.clauses(p)      # Tseitin definitions go to E.cl; the pattern clauses are returned
    return cl


sem = gpat.GSem(a.P)
for b in "ZX":
    for m in multisets("bb18", b, set(t for t in a.exclude.split(",") if t)):
        for p in patterns_of(b, m):
            for c in PE.clauses(p):
                E.add(c)
s = Solver(name="cd15", bootstrap_with=E.cl)
ptr = len(E.cl)
tot = {"cls": a.cls, "P": a.P, "schedules": 0, "witness_patterns": 0, "static_type_witnesses": 0,
       "missing_from_static": 0, "pos_checked": 0, "neg_checked": 0, "mismatch": 0, "phys_checked": 0,
       "phys_fail": 0, "illegal": 0}
for it in range(a.n):
    ass = []
    for e in rng.sample(E.ev, 3):
        l = E.tau[e].eq(rng.randint(E.tau[e].lo, E.tau[e].hi))
        if l not in (True, False):
            ass.append(l)
    for k in rng.sample(E.ks[1:], 4):
        l = E.pi[k].eq(rng.randint(E.pi[k].lo, E.pi[k].hi))
        if l not in (True, False):
            ass.append(l)
    for c in E.cl[ptr:]:
        s.add_clause(c)
    ptr = len(E.cl)
    s.set_phases([v if rng.random() < 0.5 else -v for v in range(1, E.nv + 1)])
    if not s.solve(assumptions=ass):
        continue
    sch = E.decode(s.get_model())
    if not legal_any(sch, merged=a.cls == "Mg")[0]:
        tot["illegal"] += 1
        continue
    tot["schedules"] += 1
    tau_a = {(k, support(k)[i]): sch.tau[(k, i)] for k in sch.ks for i in range(6)}
    w, wits = bulk_min(sch, 3, W=6, want_all=True, limit=2000)
    pos = []
    for b, tags in wits:
        p = pattern_of(b, tags)
        tot["witness_patterns"] += 1
        t = "".join(sorted(x[0] for x in p[1]))
        if t in ("HH", "HHM", "DDH"):
            tot["static_type_witnesses"] += 1
            if p not in static:
                tot["missing_from_static"] += 1
                print("MISSING", p, flush=True)
        pos.append(p)
    negs = rng.sample(allstatic, a.neg)
    cand = [(p, True) for p in pos[:200]] + [(p, False) for p in negs]
    # clauses for candidates (adds Tseitin defs), then fix tau and read aux values
    cls = {p: PE.clauses(p) for p, _ in cand}
    for c in E.cl[ptr:]:
        s.add_clause(c)
    ptr = len(E.cl)
    fix = []
    for e, iv in E.tau.items():
        for tt, v in iv.u.items():
            fix.append(v if sch.tau[e] <= tt else -v)
    for k in E.ks:
        for iv, val in ((E.pi[k], sch.pi[k]), (E.mu[k], sch.mu[k])):
            for tt, v in iv.u.items():
                fix.append(v if val <= tt else -v)
    assert s.solve(assumptions=fix)
    mod = set(l for l in s.get_model())
    nphys = 0
    for p, ispos in cand:
        falsified = any(all(-l in mod for l in c) for c in cls[p])
        ap_ = npat.norm_pattern(p)
        canc = sem.cancels(ap_, tau_a)
        if ispos:
            tot["pos_checked"] += 1
        else:
            tot["neg_checked"] += 1
        if falsified != bool(canc) or (ispos and not canc):
            tot["mismatch"] += 1
            print("MISMATCH", p, falsified, canc, flush=True)
        if canc and nphys < a.phys:
            nphys += 1
            tot["phys_checked"] += 1
            fired, obs = gpat.physical(ap_, canc[0], a.P, sch.pi, sch.mu, tau_a)
            if fired or not obs:
                tot["phys_fail"] += 1
                print("PHYS", p, fired, obs, flush=True)
print(json.dumps(tot))
with open("results/E-039-bb18-pipe/validate_static.jsonl", "a") as f:
    f.write(json.dumps(tot) + "\n")
