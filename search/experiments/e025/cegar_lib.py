"""E-025: in-process nogood CEGAR (the audited e024a TimeSAT + e021 nwfull frame-model nogoods + G24 images), as a
library: run on a subset of modelled logicals, optional window limits, optional phase guidance, optional
assumption literals.  Used for core extraction (structure) and guided search.  Semantics identical to
e024a.cegar (UNSAT = every family circuit has a modelled logical of the subset that lifts in the bulk)."""
from __future__ import annotations

import random
import time

import search.experiments.e021.nwfull as NF
from search.experiments.e024a.cegar import TimeSAT, bf_P, item_perms, tighten


class Cegar:
    def __init__(self, F, P, recs, maxwin=None, winunits=None, images=True, use_tighten=True, seed=1):
        self.F, self.P, self.recs = F, P, recs
        self.M = TimeSAT(F, P, maxwin=maxwin, winunits=winunits)
        self.perms = item_perms(F) if images else [list(range(len(F.items)))]
        self.unit_of = [(it[0], it[1]) for it in F.items]
        self.rng = random.Random(seed)
        self.use_tighten = use_tighten
        self.it = 0

    def lifting(self, t, recs=None):
        P = self.P
        NF.bf_general = lambda cons, rank: bf_P(cons, t, P)  # noqa: E731
        return NF.evaluate_full(self.F, self.recs if recs is None else recs, None)

    def add_nogoods(self, t, lif, guard=None):
        M, P = self.M, self.P
        seen = set()
        n = 0
        for r_, cons, pi in lif:
            mins = None
            if self.use_tighten:
                pi, mins = tighten(cons, t, P, self.unit_of, self.rng)
            for pm in self.perms:
                lits = set()
                for ei, (u_, w_, kd, (i1, i2)) in enumerate(cons):
                    K = pi[u_] - pi[w_]
                    if mins is not None and K - 1 < mins[ei]:
                        continue
                    j1, j2 = pm[i1], pm[i2]
                    if kd in ("free", "hook+"):
                        lits.add(M.le_diff(j2, j1, (K - 1) * P - 1))
                    else:
                        lits.add(M.le_diff(j1, j2, K * P))
                cl = tuple(sorted(lits))
                if cl in seen:
                    continue
                seen.add(cl)
                M.add(list(cl) + ([-guard] if guard else []))
                n += 1
        return n

    def run(self, max_sec, assumptions=(), on_model=None, verbose=False, phases=None):
        """returns (status, t, info).  status: UNSAT | MODEL_SAT | UNKNOWN."""
        t0 = time.time()
        best = None
        while time.time() - t0 < max_sec:
            self.it += 1
            if phases is not None:
                self.M.S.set_phases(phases)
            t = self.M.solve(list(assumptions))
            if t is None:
                return "UNSAT", None, {"it": self.it, "sec": time.time() - t0, "best": best}
            lif = self.lifting(t)
            if best is None or len(lif) < best:
                best = len(lif)
            if not lif:
                if on_model is None:
                    return "MODEL_SAT", t, {"it": self.it, "sec": time.time() - t0}
                if on_model(t):
                    return "ACCEPTED", t, {"it": self.it, "sec": time.time() - t0}
                continue
            self.add_nogoods(t, lif)
            if verbose and (self.it % 20 == 0 or self.it < 4):
                print({"it": self.it, "lifting": len(lif), "best": best, "sec": round(time.time() - t0, 1)}, flush=True)
        return "UNKNOWN", None, {"it": self.it, "sec": time.time() - t0, "best": best}
