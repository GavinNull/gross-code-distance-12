"""E-039 audit: own random sampler of legal N(S) schedules (own one-hot CNF; nothing from e038/e039).
x[e, t] one-hot (t = 1..S); at most one event per (check, layer) and per (data qubit, layer); determinism parity via
order literals lt(e1, e2) defined pointwise from the one-hot variables and a direct XOR on each X/Z pair."""
from __future__ import annotations

import itertools
import random

from pysat.card import CardEnc, EncType
from pysat.formula import IDPool
from pysat.solvers import Solver

from search.experiments.e039_audit import fcore as F


class Sampler:
    def __init__(self, S, seed=0):
        self.S = S
        self.rng = random.Random(seed)
        self.pool = IDPool()
        cl = []
        ev = [(k, a) for k in F.KS for a in range(6)]
        self.ev = ev
        x = lambda e, t: self.pool.id(("x", e, t))
        self.x = x
        for e in ev:
            lits = [x(e, t) for t in range(1, S + 1)]
            cl += CardEnc.equals(lits, 1, vpool=self.pool, encoding=EncType.pairwise).clauses
        for k in F.KS:
            for t in range(1, S + 1):
                cl += CardEnc.atmost([x((k, a), t) for a in range(6)], 1, vpool=self.pool,
                                     encoding=EncType.pairwise).clauses
        for q in range(F.ND):
            eq = [(k, a) for k in F.KS for a in range(6) if F.SUPP[k][a] == q]
            for t in range(1, S + 1):
                cl += CardEnc.atmost([x(e, t) for e in eq], 1, vpool=self.pool, encoding=EncType.pairwise).clauses

        def lt(e1, e2):
            v = self.pool.id(("lt", e1, e2))
            for t1 in range(1, S + 1):
                for t2 in range(1, S + 1):
                    cl.append([-x(e1, t1), -x(e2, t2), v if t1 < t2 else -v])
            return v
        for kx in F.KS:
            if kx[0] != "X":
                continue
            for kz in F.KS:
                if kz[0] != "Z":
                    continue
                sh = sorted(set(F.SUPP[kx]) & set(F.SUPP[kz]))
                if not sh:
                    continue
                ls = [lt((kx, F.SUPP[kx].index(q)), (kz, F.SUPP[kz].index(q))) for q in sh]
                for signs in itertools.product([0, 1], repeat=len(ls)):
                    if sum(signs) % 2:
                        cl.append([(-l if s else l) for l, s in zip(ls, signs)])
        self.s = Solver(name="cd15", bootstrap_with=cl)
        self.nv = self.pool.top

    def sample(self, nfix=8):
        S = self.S
        while True:
            ass = [self.x(e, self.rng.randint(1, S)) for e in self.rng.sample(self.ev, nfix)]
            self.s.set_phases([v if self.rng.random() < 0.5 else -v for v in range(1, self.nv + 1)])
            if self.s.solve(assumptions=ass):
                m = set(l for l in self.s.get_model() if l > 0)
                tau = {e: next(t for t in range(1, S + 1) if self.x(e, t) in m) for e in self.ev}
                assert F.legal(tau, S)
                return tau
