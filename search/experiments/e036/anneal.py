"""E-036 step 5b: per-check-free timing search (simulated annealing) for d_circ = d, non-wrapping template.

State: for every measured check, the CNOT time of each of its 6 terms in 1..S (distinct within the check); prep 0,
measure S+1 (period S+2).  Cost = 1000*(data collisions + odd (X,Z) overlap parities)
       + [legal only] 100*#(weight-<=d-2 undetectable logical fault sets) + #(weight d-1 sets), summed over
       both bases at R = 1 and R = 2 (exact counts on the full SD6 DEM, distinct mechanisms).
Cost 0 => candidate; candidates are then checked exactly at R = 1..Rchk with dcirc.min_weight.
Moves: swap the times of two terms of one check, or move one term to a free slot of that check.
"""
import argparse
import json
import math
import random
import time

import numpy as np

from search.experiments.e036.common import (OUT, TERMS, checks, code, dem_mechs, min_weight, sd6, spec_from_terms,
                                            term_col)


def count_low(mechs, dmax):
    """(#weight-1, #weight-2, #weight-3) undetectable logical sets (distinct mechanisms), up to weight dmax-1."""
    D = [m[0] for m in mechs]
    O = [m[1] for m in mechs]
    n = len(mechs)
    c1 = sum(1 for i in range(n) if D[i] == 0 and O[i])
    by = {}
    for i in range(n):
        by.setdefault(D[i], []).append(i)
    c2 = 0
    for lst in by.values():
        for a in range(len(lst)):
            for b in range(a + 1, len(lst)):
                if O[lst[a]] != O[lst[b]]:
                    c2 += 1
    c3 = 0
    if dmax >= 4:
        for i in range(n):
            for j in range(i + 1, n):
                lst = by.get(D[i] ^ D[j])
                if lst:
                    oo = O[i] ^ O[j]
                    for k in lst:
                        if k > j and O[k] != oo:
                            c3 += 1
    return c1, c2, c3


class State:
    def __init__(self, variant, S, rng):
        self.variant, self.S, self.rng = variant, S, rng
        xs, zs = checks(variant)
        self.cks = [("X", c) for c in xs] + [("Z", c) for c in zs]
        self.cols = {k: [term_col(k[0], k[1], t) for t in range(6)] for k in self.cks}
        self.T = {}
        for k in self.cks:
            slots = rng.sample(range(1, S + 1), 6)
            self.T[k] = slots
        # overlap pairs
        self.pairs = []
        for kx in self.cks:
            if kx[0] != "X":
                continue
            for kz in self.cks:
                if kz[0] != "Z":
                    continue
                sh = [(a, self.cols[kz].index(q)) for a, q in enumerate(self.cols[kx]) if q in self.cols[kz]]
                if sh:
                    self.pairs.append((kx, kz, sh))

    def penalty(self):
        use = {}
        bad = 0
        for k in self.cks:
            for t in range(6):
                key = (self.cols[k][t], self.T[k][t])
                use[key] = use.get(key, 0) + 1
        bad += sum(v - 1 for v in use.values() if v > 1)
        for kx, kz, sh in self.pairs:
            par = sum(1 for a, b in sh if self.T[kx][a] < self.T[kz][b]) % 2
            bad += par
        return bad

    def spec(self):
        xt = {k[1]: self.T[k] for k in self.cks if k[0] == "X"}
        zt = {k[1]: self.T[k] for k in self.cks if k[0] == "Z"}
        S = self.S
        return spec_from_terms(self.variant, xt, zt, S + 2, 0, S + 1, 0, S + 1)

    def dist_cost(self, d, Rs=(1, 2)):
        spec = self.spec()
        tot = 0
        for R in Rs:
            for b in ("Z", "X"):
                mechs, _ = dem_mechs(sd6(spec, self.variant, b, R))
                c1, c2, c3 = count_low(mechs, d)
                tot += 10000 * c1 + (100 * c2 + c3 if d >= 4 else c2)
        return tot

    def cost(self, d):
        pen = self.penalty()
        if pen:
            return 1_000_000 + 1000 * pen
        return self.dist_cost(d)

    def move(self):
        k = self.rng.choice(self.cks)
        old = list(self.T[k])
        free = [s for s in range(1, self.S + 1) if s not in old]
        if free and self.rng.random() < 0.4:
            a = self.rng.randrange(6)
            self.T[k][a] = self.rng.choice(free)
        else:
            a, b = self.rng.sample(range(6), 2)
            self.T[k][a], self.T[k][b] = self.T[k][b], self.T[k][a]
        return k, old


def anneal(variant, S, d, seed, iters, T0=30.0, T1=0.3):
    """SA restricted to LEGAL states: start from a CP-SAT legal schedule, reject any move that breaks legality."""
    from search.experiments.e036.lns import Model
    rng = random.Random(seed)
    st = State(variant, S, rng)
    sol = Model(variant, S).solve({}, rng, timeout=60)
    if sol is None or sol == "timeout":
        return None, st, 0, 0.0
    st.T = {k: list(v) for k, v in sol.items()}
    assert st.penalty() == 0
    cur = st.dist_cost(d)
    best = (cur, {k: list(v) for k, v in st.T.items()})
    t0 = time.time()
    tried = 0
    it = 0
    for it in range(iters):
        if cur == 0:
            break
        temp = T0 * (T1 / T0) ** (it / iters)
        k, old = st.move()
        if st.penalty():
            st.T[k] = old
            continue
        tried += 1
        new = st.dist_cost(d)
        if new <= cur or rng.random() < math.exp(-(new - cur) / temp):
            cur = new
            if cur < best[0]:
                best = (cur, {kk: list(v) for kk, v in st.T.items()})
        else:
            st.T[k] = old
    st.T = best[1]
    return best[0], st, (it + 1, tried), time.time() - t0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("variant")
    ap.add_argument("S", type=int)
    ap.add_argument("--d", type=int, default=4)
    ap.add_argument("--seed", type=int, default=20261025)
    ap.add_argument("--iters", type=int, default=20000)
    ap.add_argument("--restarts", type=int, default=5)
    ap.add_argument("--rchk", type=int, default=8)
    a = ap.parse_args()
    for r in range(a.restarts):
        c, st, its, sec = anneal(a.variant, a.S, a.d, a.seed + r, a.iters)
        rec = {"variant": a.variant, "S": a.S, "seed": a.seed + r, "best_cost": c, "iters": its, "sec": round(sec, 1)}
        if c == 0:
            spec = st.spec()
            ok = True
            for R in range(1, a.rchk + 1):
                for b in ("Z", "X"):
                    mechs, _ = dem_mechs(sd6(spec, a.variant, b, R))
                    w, _ = min_weight(mechs, a.d - 1)
                    if w is not None:
                        ok = False
                        rec.setdefault("fail", []).append([R, b, w])
            rec["exact_R1_to_Rchk_ok"] = ok
            path = OUT / f"anneal_{a.variant}_S{a.S}_seed{a.seed + r}.json"
            path.write_text(json.dumps(spec.to_dict()))
            rec["spec"] = str(path)
        print(json.dumps(rec), flush=True)
        with open(OUT / "anneal.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")
