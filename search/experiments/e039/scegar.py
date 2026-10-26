"""E-039 pattern-CEGAR with (a) complete static patterns of chosen slot types (static.py), (b) lazy patterns for the
rest, (c) large-neighbourhood harvesting: after every global SAT model, NLNS sub-solves that keep all but a few
random checks fixed (assumptions) produce nearby legal schedules satisfying all current clauses; every witness of
every such schedule becomes a pattern.  Any schedule with no bulk witness of weight <= d-1 (W = 6 and W = 12) is
reported FOUND.  Cubes: assumptions on prep times pi of chosen checks (every schedule has some legal pi vector, so the
cubes over all pi values of the chosen checks cover the class).

Sanity check built in: a SAT model can never have a witness whose pattern type is statically complete (else the
completeness argument of static.py is wrong) -> RuntimeError.

classes: W P  (e038 Enc 'W': mu - pi <= P - 1)        Mg P (merged measure + reset layer: mu - pi <= P; enc2.py)
usage: uv run python -m search.experiments.e039.scegar W 8 --static HH,HHM,DDH --lns 30
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import random
import time

from pysat.solvers import Solver

from search.experiments.e038.cegar import PatternEncoder, load_patterns, pattern_of, save_patterns
from search.experiments.e038.model import bulk_min
from search.experiments.e039.legal2 import legal_any
from search.experiments.e039.static import multisets, patterns_of

OUT = "results/E-039-bb18-pipe"
SOLVER = os.environ.get("E039_SOLVER", "cadical195")


def make_enc(cls, P, variant="bb18"):
    if cls == "W":
        from search.experiments.e038.enc import Enc
        return Enc(variant, "W", P)
    if cls == "Mg":
        from search.experiments.e039.enc2 import EncMerged
        return EncMerged(variant, P)
    if cls == "N":
        from search.experiments.e038.enc import Enc
        return Enc(variant, "N", P)
    raise ValueError(cls)


def ptype(pat):
    return "".join(sorted(s[0] for s in pat[1]))


class Driver:
    def __init__(self, cls, P, static, resume, d=4, variant="bb18", tag="", seed=0, shuffle=None):
        self.E = E = make_enc(cls, P, variant)
        self.PE = PatternEncoder(E)
        self.d = d
        self.static = set(static)
        self.pats = {}
        self.rng = random.Random(seed)
        t0 = time.time()
        for b in ("Z", "X"):
            for m in multisets(variant, b, self.static):
                for pat in patterns_of(b, m):
                    self.add(pat)
        self.nstatic = len(self.pats)
        for path in resume:
            for pat in load_patterns(path):
                self.add(pat)
        if shuffle is not None:
            random.Random(shuffle).shuffle(E.cl)
        self.s = Solver(name=SOLVER, bootstrap_with=E.cl)
        self.ptr = len(E.cl)
        self.tag = tag
        self.log = open(f"{OUT}/{tag}.log", "a")
        self.logw({"start": tag, "static": sorted(self.static), "nstatic": self.nstatic, "patterns": len(self.pats),
                   "vars": E.nv, "clauses": len(E.cl), "build_sec": round(time.time() - t0, 1)})

    def logw(self, d):
        self.log.write(json.dumps(d) + "\n")
        self.log.flush()
        print(json.dumps(d), flush=True)

    def add(self, pat):
        if pat in self.pats:
            return False
        cl = self.PE.clauses(pat)
        if any(len(c) == 0 for c in cl):
            raise RuntimeError(f"schedule-independent pattern {pat}")
        self.pats[pat] = len(cl)
        for c in cl:
            self.E.add(c)
        return True

    def sync(self):
        for c in self.E.cl[self.ptr:]:
            self.s.add_clause(c)
        self.ptr = len(self.E.cl)

    def witnesses(self, sch):
        w, wits = bulk_min(sch, self.d - 1, W=6, want_all=True, limit=400)
        if w is None:
            w, wits = bulk_min(sch, self.d - 1, W=12, want_all=True, limit=400)
        return w, wits

    def learn(self, sch):
        """returns (w, new) ; w None -> FOUND."""
        ok, why = legal_any(sch, merged=self.E.cls == "Mg")
        assert ok, why
        w, wits = self.witnesses(sch)
        if w is None:
            return None, 0
        new = 0
        for b, tags in wits:
            pat = pattern_of(b, tags)
            if ptype(pat) in self.static and pat not in self.pats:
                raise RuntimeError(f"static completeness violated: {pat}")
            new += self.add(pat)
        return w, new

    def fix_lits(self, sch, free):
        E = self.E
        ass = []
        for k in E.ks:
            if k in free:
                continue
            for a in range(6):
                l = E.tau[(k, a)].eq(sch.tau[(k, a)])
                if l is not True:
                    ass.append(l)
        return ass

    def found(self, sch, where):
        json.dump(sch.to_json(), open(f"{OUT}/found_{self.tag}_{where}.json", "w"))
        self.logw({"result": "FOUND", "where": where, "sched": sch.to_json()})

    def run(self, cube=(), nlns=0, nfree=3, max_iter=10 ** 9, tlimit=None):
        E = self.E
        t0 = time.time()
        it = 0
        while it < max_iter:
            self.sync()
            ts = time.time()
            sat = self.s.solve(assumptions=list(cube))
            tsolve = time.time() - ts
            if not sat:
                return "UNSAT", it
            sch = E.decode(self.s.get_model())
            w, new = self.learn(sch)
            if w is None:
                self.found(sch, f"it{it}")
                return "FOUND", sch
            lw = []
            for j in range(nlns):
                free = set(self.rng.sample(E.ks, nfree))
                self.sync()
                if not self.s.solve(assumptions=list(cube) + self.fix_lits(sch, free)):
                    continue
                sch2 = E.decode(self.s.get_model())
                w2, n2 = self.learn(sch2)
                if w2 is None:
                    self.found(sch2, f"it{it}_lns{j}")
                    return "FOUND", sch2
                new += n2
                lw.append(w2)
            it += 1
            self.logw({"it": it, "w": w, "new": new, "patterns": len(self.pats), "lns_w": sorted(set(lw)),
                       "solve": round(tsolve, 1), "sec": round(time.time() - t0, 1)})
            if it % 10 == 0:
                self.save()
            if tlimit and time.time() - t0 > tlimit:
                return "TIMEOUT", it
        return "MAXITER", it

    def save(self):
        save_patterns(f"{OUT}/{self.tag}_patterns.json", [p for p in self.pats if ptype(p) not in self.static])

    def dump(self, path, extra=()):
        with open(path, "w") as f:
            f.write(f"p cnf {self.E.nv} {len(self.E.cl) + len(extra)}\n")
            for c in self.E.cl:
                f.write(" ".join(map(str, c)) + " 0\n")
            for c in extra:
                f.write(" ".join(map(str, c)) + " 0\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cls")
    ap.add_argument("P", type=int)
    ap.add_argument("--static", default="HH,HHM,DDH")
    ap.add_argument("--resume", default="")
    ap.add_argument("--lns", type=int, default=20)
    ap.add_argument("--nfree", type=int, default=3)
    ap.add_argument("--tag", default="")
    ap.add_argument("--seed", type=int, default=20261027)
    ap.add_argument("--tlimit", type=float)
    ap.add_argument("--dump", action="store_true")
    a = ap.parse_args()
    tag = f"{a.cls}{a.P}{a.tag}"
    D = Driver(a.cls, a.P, [t for t in a.static.split(",") if t], [p for p in a.resume.split(",") if p], tag=tag,
               seed=a.seed)
    res = D.run(nlns=a.lns, nfree=a.nfree, tlimit=a.tlimit)
    D.save()
    D.logw({"result": res[0], "iters": res[1] if res[0] != "FOUND" else None, "patterns": len(D.pats)})
    if a.dump and res[0] == "UNSAT":
        D.dump(f"{OUT}/{tag}.cnf")
