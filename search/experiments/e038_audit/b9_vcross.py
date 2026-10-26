"""E-038 audit: E-038's own V(P, delta) certificates (cegar_bb18_V{P}_d4_delta{d}.cnf, DRAT-checked) clause by clause
against my semantics, as b2 does for N7: rebuild the CNF with E-038's encoder (bookkeeping only; must hash to the
dumped CNF), sample legal schedules from MY V legality (gcnf.vclass), fix E-038's tau literals, let its non-pattern
clauses fix the auxiliaries (and some mu), and require  {patterns with a falsified clause} == {patterns that cancel
under my semantics}.  usage: uv run python -m search.experiments.e038_audit.b9_vcross P delta --n 30"""
import argparse
import hashlib
import json
import random

from pysat.solvers import Solver

from search.experiments.e036_audit.core import support
from search.experiments.e038_audit import gcnf, gpat, npat

ap = argparse.ArgumentParser()
ap.add_argument("P", type=int)
ap.add_argument("delta", type=int)
ap.add_argument("--n", type=int, default=30)
ap.add_argument("--seed", type=int, default=7)
a = ap.parse_args()
P, d = a.P, a.delta
from search.experiments.e038.cegar import PatternEncoder, load_patterns
from search.experiments.e038.enc import Enc
pf = f"results/E-038-bb18-d4/cegar_bb18_V{P}_d4_delta{d}_patterns.json"
E = Enc("bb18", "V", P, d)
PE = PatternEncoder(E)
theirs = load_patterns(pf)
owner = {}
for i, p in enumerate(theirs):
    for c in PE.clauses(p):
        n0 = len(E.cl)
        E.add(c)
        if len(E.cl) > n0:
            owner[len(E.cl) - 1] = i
txt = f"p cnf {E.nv} {len(E.cl)}\n" + "".join(" ".join(map(str, c)) + " 0\n" for c in E.cl)
h = hashlib.sha256(txt.encode()).hexdigest()
h0 = hashlib.sha256(open(f"results/E-038-bb18-d4/cegar_bb18_V{P}_d4_delta{d}.cnf", "rb").read()).hexdigest()
defs = [c for i, c in enumerate(E.cl) if i not in owner]
sd = Solver(name="cadical195", bootstrap_with=defs)
mine = [npat.norm_pattern(p) for p in json.load(open(pf))]
G = gcnf.vclass(P, d)
sem = gpat.GSem(P)
s = Solver(name="cadical195", bootstrap_with=G.cl)
rng = random.Random(a.seed)
tot = {"P": P, "delta": d, "rebuilt_equals_dumped": h == h0, "samples": 0, "their_reject_legal": 0,
       "falsified_not_cancel": 0, "cancel_not_falsified": 0, "mean_cancel": 0}
for it in range(a.n):
    ass = [G.x[e][rng.choice(list(G.x[e]))] for e in rng.sample(G.ev, 5)]
    s.set_phases([v if rng.random() < 0.5 else -v for v in range(1, G.nv + 1)])
    if not s.solve(assumptions=ass):
        continue
    tau = G.decode(s.get_model())
    tot["samples"] += 1
    prim = []
    for (k, ai), iv in E.tau.items():
        t = tau[(k, support(k)[ai])]
        for tt, v in iv.u.items():
            prim.append(v if t <= tt else -v)
    if not sd.solve(assumptions=prim):
        tot["their_reject_legal"] += 1
        continue
    m = set(l for l in sd.get_model() if l > 0)
    fals = set()
    for ci, pi in owner.items():
        if not any((l > 0 and l in m) or (l < 0 and -l not in m) for l in E.cl[ci]):
            fals.add(pi)
    canc = {i for i, p in enumerate(mine) if sem.cancels(p, tau)}
    tot["falsified_not_cancel"] += len(fals - canc)
    tot["cancel_not_falsified"] += len(canc - fals)
    tot["mean_cancel"] += len(canc)
tot["mean_cancel"] = round(tot["mean_cancel"] / max(1, tot["samples"]), 1)
print(json.dumps(tot), flush=True)
with open("results/E-038-audit/b9_vcross.jsonl", "a") as f:
    f.write(json.dumps(tot) + "\n")
