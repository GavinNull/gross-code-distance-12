"""E-041: offset-vector scan on a static class CNF (e039 dump_static: legality + complete static patterns of the
listed types, both bases) with assumptions pi_k = s_k for all 14 checks (X0 = 0 by the global time shift).
For W(P) (e038 enc 'W'), pi_k = s fixes the 7-layer window [s+1, s+7] for P = 9.  Each vector: SAT / UNSAT / TIMEOUT,
seconds, and the failed-assumption core size (UNSAT).  SAT under HH/HHM/DDH is only a necessary condition.
usage: uv run python -m search.experiments.e041.piscan <cnf> --mode random --n 50 --seed 1 --tl 120"""
import argparse
import json
import time

import numpy as np

from search.experiments.e041.fast import KS

OUT = "results/E-041-bb18-p9"


def names():
    return [f"{k[0]}{k[1]}" for k in KS]


class Oracle:
    """CaDiCaL 3.0.1 binary (tools/cadical) on base CNF + unit clauses, wall-clock limit -t."""

    def __init__(self, cnf_path, scratch, seed=0):
        self.mp = json.load(open(cnf_path.replace(".cnf", "_map.json")))["pi_eq"]
        lines = open(cnf_path).read().split("\n", 1)
        h = lines[0].split()
        self.nv, self.ncl = int(h[2]), int(h[3])
        self.body = lines[1]
        if not self.body.endswith("\n"):
            self.body += "\n"
        self.scratch, self.seed = scratch, seed
        self.load_sec = 0.0
        self.nm = names()

    def lits(self, starts):
        out = []
        for n, s in zip(self.nm, starts):
            l = self.mp[n][str(s)]
            if l is True:
                continue
            if l is False:
                return None
            out.append(l)
        return out

    def solve(self, starts, tl, extra_units=()):
        import subprocess
        A = self.lits(starts)
        if A is None:
            return "UNSAT", 0.0, 0
        A = list(A) + list(extra_units)
        with open(self.scratch, "w") as f:
            f.write(f"p cnf {self.nv} {self.ncl + len(A)}\n")
            f.write(self.body)
            for l in A:
                f.write(f"{l} 0\n")
        t0 = time.time()
        r = subprocess.run(["tools/cadical/build/cadical", "-q", "-t", str(int(tl)), f"--seed={self.seed}",
                            self.scratch], capture_output=True, text=True)
        dt = time.time() - t0
        st, model = None, []
        for line in r.stdout.splitlines():
            if line.startswith("s "):
                st = line[2:].strip()
            elif line.startswith("v "):
                model += [int(x) for x in line[2:].split() if x != "0"]
        if st == "SATISFIABLE":
            return "SAT", dt, model
        if st == "UNSATISFIABLE":
            return "UNSAT", dt, None
        return "TIMEOUT", dt, None


def gen(mode, rng, P):
    if mode == "random":
        v = [0] + list(rng.integers(0, P, 13))
    elif mode == "near":   # mostly 0, a few +-1 / +-2
        v = [0] * 14
        for i in rng.choice(np.arange(1, 14), int(rng.integers(1, 6)), replace=False):
            v[i] = int(rng.choice([1, 2, P - 1, P - 2]))
    elif mode == "twotype":   # X at 0 +- 1, Z at delta +- 1
        d = int(rng.integers(0, P))
        v = [0] + [int(rng.choice([0, 0, 1, P - 1])) for _ in range(6)] + \
            [(d + int(rng.choice([0, 0, 1, P - 1]))) % P for _ in range(7)]
    return [int(x) % P for x in v]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cnf")
    ap.add_argument("--mode", default="random")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--tl", type=float, default=120)
    ap.add_argument("--P", type=int, default=9)
    ap.add_argument("--vectors", help="json list of 14-vectors")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    import os
    O = Oracle(a.cnf, os.path.join(os.environ.get("E041_SCRATCH", OUT), f"piscan_{a.mode}_{a.seed}{a.tag}.cnf"))
    rng = np.random.default_rng(a.seed)
    out = open(f"{OUT}/piscan{a.tag}.jsonl", "a")
    vecs = json.load(open(a.vectors)) if a.vectors else [gen(a.mode, rng, a.P) for _ in range(a.n)]
    print("loaded", round(O.load_sec, 1), flush=True)
    for v in vecs:
        v = [(x - v[0]) % a.P for x in v]
        r, dt, extra = O.solve(v, a.tl)
        rec = {"cnf": a.cnf, "mode": a.mode, "v": v, "r": r, "sec": round(dt, 2)}
        out.write(json.dumps(rec) + "\n")
        out.flush()
        print(json.dumps(rec), flush=True)
