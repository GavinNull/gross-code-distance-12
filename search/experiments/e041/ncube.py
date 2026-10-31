"""E-041 cubes for N8s6 (non-wrapping CNOT layers 1..8, span <= 6 per check; in W9 after deleting the CNOT-free layer):
cube b in {0,1}^14:  b_k = 0 -> check k avoids layer 8 (all tau <= 7);  b_k = 1 -> check k avoids layer 1 (tau >= 2).
Span <= 6 forces at least one of the two, so the 2^14 cubes cover the class; time reversal t -> 9 - t (theory C
lemma 4; maps N8s6 to itself and b to its complement) lets us fix b_X0 = 0 for bulk statements.
Each cube = base CNF (rcegar pickle: legality + span + static patterns [+ lazy]) + unit clauses, solved by the
CaDiCaL 3.0.1 binary with a wall-clock limit (optionally writing a DRAT proof).
usage: uv run python -m search.experiments.e041.ncube --base <dumped N8s6 cnf> --sample 12 --seed 1 --tl 900"""
import argparse
import json
import os
import pickle
import subprocess
import sys
import time

import numpy as np

OUT = "results/E-041-bb18-p9"
SCR = os.environ.get("E041_SCRATCH", OUT)


def cube_units(tau_le, b):
    """tau_le[(k_index, a)][t] = literal of tau <= t (dict str->lit) ; returns unit literals for cube b."""
    units = []
    for k in range(14):
        for a in range(6):
            le = tau_le[f"{k}:{a}"]
            if b[k] == 0:
                units.append(le["7"])            # tau <= 7
            else:
                units.append(-le["1"])           # not tau <= 1
    return units


def dump_base(tag, path):
    sys.setrecursionlimit(100000)
    E, PE, pats = pickle.load(open(f"{OUT}/{tag}_enc.pkl", "rb"))
    with open(path, "w") as f:
        f.write(f"p cnf {E.nv} {len(E.cl)}\n")
        for c in E.cl:
            f.write(" ".join(map(str, c)) + " 0\n")
    tl = {}
    for i, k in enumerate(E.ks):
        for a in range(6):
            iv = E.tau[(k, a)]
            assert iv.lo == 1 and iv.hi == 8
            tl[f"{i}:{a}"] = {str(t): iv.u[t] for t in range(1, 8)}
    json.dump({"tau_le": tl, "nv": E.nv, "ncl": len(E.cl), "lazy": len(pats)}, open(path + ".map.json", "w"))


def solve(base, mp, b, tl, proof=None, seed=0):
    units = cube_units(mp["tau_le"], b)
    path = os.path.join(SCR, f"ncube_{os.getpid()}.cnf")
    body = open(base).read().split("\n", 1)[1]
    with open(path, "w") as f:
        f.write(f"p cnf {mp['nv']} {mp['ncl'] + len(units)}\n")
        f.write(body)
        if not body.endswith("\n"):
            f.write("\n")
        for u in units:
            f.write(f"{u} 0\n")
    cmd = ["tools/cadical/build/cadical", "-q", "-t", str(int(tl)), f"--seed={seed}", path]
    if proof:
        cmd = ["tools/cadical/build/cadical", "-q", "-t", str(int(tl)), "--binary=false", path, proof]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True)
    dt = time.time() - t0
    st, model = None, []
    for line in r.stdout.splitlines():
        if line.startswith("s "):
            st = line[2:].strip()
        elif line.startswith("v "):
            model += [int(x) for x in line[2:].split() if x != "0"]
    return {"SATISFIABLE": "SAT", "UNSATISFIABLE": "UNSAT"}.get(st, "TIMEOUT"), dt, model, path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="N8s6")
    ap.add_argument("--base", required=True)
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--cubes", help="json list of 14-bit vectors")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--tl", type=float, default=900)
    ap.add_argument("--log", default="ncube.jsonl")
    a = ap.parse_args()
    if a.dump:
        dump_base(a.tag, a.base)
        print("dumped")
        sys.exit()
    mp = json.load(open(a.base + ".map.json"))
    rng = np.random.default_rng(a.seed)
    if a.cubes:
        cubes = json.load(open(a.cubes))
    else:
        cubes = [[0] + [int(x) for x in rng.integers(0, 2, 13)] for _ in range(a.sample)]
    for b in cubes:
        r, dt, model, path = solve(a.base, mp, b, a.tl)
        rec = {"base": a.base, "lazy": mp["lazy"], "b": b, "r": r, "sec": round(dt, 1)}
        if r == "SAT":
            rec["model_pos_count"] = sum(1 for x in model if x > 0)
            json.dump({"b": b, "model": model}, open(f"{OUT}/ncube_sat_{''.join(map(str, b))}.json", "w"))
        with open(f"{OUT}/{a.log}", "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(json.dumps(rec), flush=True)
        os.remove(path)
