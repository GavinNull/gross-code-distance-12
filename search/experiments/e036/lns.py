"""E-036 step 5b: per-check-free timing search by large-neighbourhood search over LEGAL schedules.

Legality model (CP-SAT, exact): every measured check gets CNOT times t(c, term) in 1..S, all different within the
check and all different on each data qubit; determinism: for every (X check, Z check) overlap the number of shared
qubits with t_X < t_Z is even (non-wrapping template: prep 0, meas S+1, period S+2).
Search: start from a random legal schedule; each step frees k random checks (others fixed), asks CP-SAT for a legal
completion minimising a random linear objective, evaluates the exact distance cost (anneal.count_low on the full
SD6 DEM, R = 1, 2, both bases) and accepts by Metropolis.  Cost 0 -> exact check at R = 1..Rchk.
"""
import argparse
import json
import math
import random
import time

import stim  # noqa: F401  (import stim BEFORE ortools: the reverse order makes stim ~10x slower here)
from search.experiments.e036 import common as _c  # noqa: F401
from ortools.sat.python import cp_model
from search.experiments.e036.anneal import count_low
from search.experiments.e036.common import OUT, checks, dem_mechs, min_weight, sd6, spec_from_terms, term_col


class Model:
    def __init__(self, variant, S):
        self.variant, self.S = variant, S
        xs, zs = checks(variant)
        self.cks = [("X", c) for c in xs] + [("Z", c) for c in zs]
        self.cols = {k: [term_col(k[0], k[1], t) for t in range(6)] for k in self.cks}
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

    def solve(self, fixed, rng, timeout=10.0):
        m = cp_model.CpModel()
        S = self.S
        T = {k: [m.NewIntVar(1, S, f"t{k[0]}{k[1]}_{a}") for a in range(6)] for k in self.cks}
        for k in self.cks:
            m.AddAllDifferent(T[k])
        byq = {}
        for k in self.cks:
            for a in range(6):
                byq.setdefault(self.cols[k][a], []).append(T[k][a])
        for q, vs in byq.items():
            m.AddAllDifferent(vs)
        for kx, kz, sh in self.pairs:
            bs = []
            for a, b in sh:
                v = m.NewBoolVar("")
                m.Add(T[kx][a] < T[kz][b]).OnlyEnforceIf(v)
                m.Add(T[kx][a] > T[kz][b]).OnlyEnforceIf(v.Not())
                bs.append(v)
            # even number true: XOR of bs == 0  <=> AddBoolXOr(bs + [True]) ... use parity via sum = 2*z
            z = m.NewIntVar(0, len(bs), "")
            m.Add(sum(bs) == 2 * z)
        for k, ts in fixed.items():
            for a in range(6):
                m.Add(T[k][a] == ts[a])
        m.Minimize(sum(rng.randint(-5, 5) * T[k][a] for k in self.cks for a in range(6)))
        s = cp_model.CpSolver()
        s.parameters.max_time_in_seconds = timeout
        s.parameters.num_workers = 1
        s.parameters.random_seed = rng.randrange(1 << 30)
        st = s.Solve(m)
        if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return None if st == cp_model.INFEASIBLE else "timeout"
        return {k: [s.Value(T[k][a]) for a in range(6)] for k in self.cks}

    def spec(self, sol):
        xt = {k[1]: sol[k] for k in self.cks if k[0] == "X"}
        zt = {k[1]: sol[k] for k in self.cks if k[0] == "Z"}
        return spec_from_terms(self.variant, xt, zt, self.S + 2, 0, self.S + 1, 0, self.S + 1)

    def cost(self, sol, d, Rs=(1, 2)):
        spec = self.spec(sol)
        tot = 0
        for R in Rs:
            for b in ("Z", "X"):
                mechs, _ = dem_mechs(sd6(spec, self.variant, b, R))
                c1, c2, c3 = count_low(mechs, d)
                tot += 10000 * c1 + (100 * c2 + c3 if d >= 4 else c2)
        return tot


def search(variant, S, d, seed, steps, kfree, T0, rchk):
    rng = random.Random(seed)
    M = Model(variant, S)
    sol = M.solve({}, rng, timeout=60)
    if sol is None or sol == "timeout":
        return {"variant": variant, "S": S, "seed": seed, "legal": sol is None and "infeasible" or "timeout"}
    cur = M.cost(sol, d)
    best = (cur, sol)
    t0 = time.time()
    hist = []
    for it in range(steps):
        if cur == 0:
            break
        temp = T0 * (0.05 / T0) ** (it / steps) if steps > 1 else T0
        free = set(rng.sample(range(len(M.cks)), kfree))
        fixed = {k: sol[k] for i, k in enumerate(M.cks) if i not in free}
        new = M.solve(fixed, rng, timeout=5)
        if new is None or new == "timeout":
            continue
        c = M.cost(new, d)
        if c <= cur or rng.random() < math.exp(-(c - cur) / max(temp, 1e-9)):
            sol, cur = new, c
            if c < best[0]:
                best = (c, new)
        if it % 50 == 0:
            hist.append([it, cur, best[0]])
    rec = {"variant": variant, "S": S, "period": S + 2, "seed": seed, "best_cost": best[0], "steps": it + 1,
           "sec": round(time.time() - t0, 1), "trace": hist[-10:]}
    spec = M.spec(best[1])
    path = OUT / f"lns_{variant}_S{S}_seed{seed}.json"
    path.write_text(json.dumps(spec.to_dict()))
    rec["spec"] = str(path)
    if best[0] == 0:
        ok = True
        for R in range(1, rchk + 1):
            for b in ("Z", "X"):
                mechs, _ = dem_mechs(sd6(spec, variant, b, R))
                w, _ = min_weight(mechs, d - 1)
                if w is not None:
                    ok = False
                    rec.setdefault("fail", []).append([R, b, w])
        rec["exact_R1_to_Rchk_ok"] = ok
    return rec


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("variant")
    ap.add_argument("S", type=int)
    ap.add_argument("--d", type=int, default=4)
    ap.add_argument("--seed", type=int, default=20261025)
    ap.add_argument("--steps", type=int, default=2000)
    ap.add_argument("--kfree", type=int, default=3)
    ap.add_argument("--T0", type=float, default=20.0)
    ap.add_argument("--rchk", type=int, default=8)
    ap.add_argument("--restarts", type=int, default=1)
    a = ap.parse_args()
    for r in range(a.restarts):
        rec = search(a.variant, a.S, a.d, a.seed + r, a.steps, a.kfree, a.T0, a.rchk)
        print(json.dumps(rec), flush=True)
        with open(OUT / "lns.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")
