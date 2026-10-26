"""E-039: validate the finite-R model (finite.mechs) against stim for random legal N(S) schedules.
For each schedule, basis, R: the set {(detector set, observable)} of finite.mechs equals the set of stim DEM mechanisms
of e038.model.stim_circuit (own periodic circuit = evaluator-style memory circuit for non-wrapping schedules; detector
map (check, j) -> index), and the exact min weight (<= 3) agrees with the evaluator template + SD6.
usage: uv run python -m search.experiments.e039.validate_finite --S 7 --n 20 --R 1,2,3"""
import argparse
import json
import random

from pysat.solvers import Solver

from search.experiments.e036_audit.core import min_weight_le
from search.experiments.e038.enc import Enc
from search.experiments.e038.model import stim_circuit, stim_mechs
from search.experiments.e039 import finite


def sample(E, s, rng):
    for i in range(50):
        ass = []
        for e in rng.sample(E.ev, 6):
            l = E.tau[e].eq(rng.randint(E.tau[e].lo, E.tau[e].hi))
            if l not in (True, False):
                ass.append(l)
        if s.solve(assumptions=ass):
            return E.decode(s.get_model())


def evaluator_min(sch, basis, R):
    from evaluators import candidate as cand
    from evaluators.noise import add_noise
    from search.experiments.e036.common import code
    spec = cand.parse_schedule(sch.spec())
    c = add_noise(cand.memory_circuit(spec, code(sch.variant), basis, R), "sd6", 1e-3)
    ms = [(d, o) for d, o in stim_mechs(c)]
    return min_weight_le(ms, 3)[0]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--S", type=int, default=7)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--R", default="1,2,3")
    ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--evaluator", action="store_true")
    a = ap.parse_args()
    rng = random.Random(a.seed)
    E = Enc("bb18", "N", a.S)
    s = Solver(name="cd15", bootstrap_with=E.cl)
    out = open("results/E-039-bb18-pipe/validate_finite.jsonl", "a")
    nok = nbad = 0
    for i in range(a.n):
        sch = sample(E, s, rng)
        for R in map(int, a.R.split(",")):
            for b in "ZX":
                c, dets = stim_circuit(sch, b, R)
                inv = {v: kj for kj, v in dets.items()}
                st = set()
                for d, o in stim_mechs(c):
                    # re-index into finite.mechs bit layout
                    readers = [k for k in sch.ks if k[0] == b]
                    ridx = {k: j for j, k in enumerate(readers)}
                    dd = 0
                    x = d
                    while x:
                        lo = x & -x
                        idx = lo.bit_length() - 1
                        k, j = inv[idx]
                        dd ^= 1 << (ridx[k] * (R + 1) + j)
                        x ^= lo
                    st.add((dd, o))
                mine = {(d, o) for d, o, _ in finite.mechs(sch, b, R) if d or o}
                eq = mine == st
                wm = min_weight_le([(d, o) for d, o, _ in finite.mechs(sch, b, R)], 3)[0]
                ws = min_weight_le(sorted(st), 3)[0]
                we = evaluator_min(sch, b, R) if a.evaluator else None
                ok = eq and wm == ws and (we is None or we == wm)
                nok += ok
                nbad += not ok
                rec = {"i": i, "R": R, "basis": b, "set_equal": eq, "n_mine": len(mine), "n_stim": len(st),
                       "w_mine": wm, "w_stim": ws, "w_eval": we}
                out.write(json.dumps(rec) + "\n")
                if not ok:
                    print("MISMATCH", rec, flush=True)
    print(json.dumps({"ok": nok, "bad": nbad}))
