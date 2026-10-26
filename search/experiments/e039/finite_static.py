"""E-039: EXACT finite-R decision for non-wrapping N(S): complete static enumeration of all finite-R witness patterns
of weight <= 3 (absolute rounds: H, M slots in rounds 0..R-1, D slots in 0..R, where D(q, R) = data error after the
last round), all slot types with a valid residual (HH, HHM, DDH, DHH, HHH -- the only types whose residual can be a
non-trivial logical of the 14-check code; D, H, DD, DH, DDD, DDM, DMM, DHM, HMM never are, see static.py counts),
encoded with finite.FinitePE.  The CNF (legality + all clauses) is SAT iff some N(S) schedule has no undetectable
logical of weight <= 3 in the R-round memory experiment, in both bases (finite model = stim DEM, validate_finite).
usage: uv run python -m search.experiments.e039.finite_static --S 7 --R 1 [--dump]"""
import argparse
import itertools
import json
import time

from pysat.solvers import Solver

from search.experiments.e038.enc import Enc
from search.experiments.e039 import finite
from search.experiments.e039.finite_cegar import fmin
from search.experiments.e039.static import multisets

TYPES = ("HH", "HHM", "DDH", "DHH", "HHH")


def patterns(basis, heads, R):
    out = set()
    rng = [range(R + 1) if h[0] == "D" else range(R) for h in heads]
    for v in itertools.product(*rng):
        slots = tuple(sorted((h + (r,) for h, r in zip(heads, v)), key=repr))
        if len(set(slots)) < len(slots):
            continue
        out.add((basis, slots))
    return sorted(out, key=repr)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--S", type=int, default=7)
    ap.add_argument("--R", type=int, default=1)
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--types", default=",".join(TYPES))
    a = ap.parse_args()
    t0 = time.time()
    E = Enc("bb18", "N", a.S)
    PE = finite.FinitePE(E, a.R)
    npat = ncl = 0
    for b in ("Z", "X"):
        for m in multisets("bb18", b, set(a.types.split(","))):
            for pat in patterns(b, m, a.R):
                cl = PE.clauses(pat)
                assert all(len(c) for c in cl), pat
                for c in cl:
                    E.add(c)
                npat += 1
                ncl += len(cl)
    tb = time.time() - t0
    tag = f"finite_static_N{a.S}_R{a.R}" + ("" if a.types == ",".join(TYPES) else "_" + a.types.replace(",", ""))
    if a.dump:
        with open(f"results/E-039-bb18-pipe/{tag}.cnf", "w") as f:
            f.write(f"p cnf {E.nv} {len(E.cl)}\n")
            for c in E.cl:
                f.write(" ".join(map(str, c)) + " 0\n")
    s = Solver(name="cd15", bootstrap_with=E.cl)
    r = s.solve()
    rec = {"S": a.S, "R": a.R, "types": a.types, "patterns": npat, "pattern_clauses": ncl, "vars": E.nv, "clauses": len(E.cl),
           "result": "SAT" if r else "UNSAT", "build": round(tb, 1), "solve": round(time.time() - t0 - tb, 1)}
    if r:
        sch = E.decode(s.get_model())
        w, wits = fmin(sch, a.R, 4)
        rec["check_w"] = w          # must be None (no weight <= 3) by completeness
        rec["sched"] = sch.to_json()
        json.dump(sch.to_json(), open(f"results/E-039-bb18-pipe/found_{tag}.json", "w"))
    print(json.dumps(rec), flush=True)
    with open("results/E-039-bb18-pipe/finite_static.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
