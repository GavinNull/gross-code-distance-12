"""E-038: validate the bulk symbolic model and the CNF legality encoding against stim and the evaluator.

For random legal schedules of a class (SAT model of enc.Enc with random time assumptions):
  1. python legal() agrees with the CNF (every SAT model is legal);
  2. own periodic stim circuit (model.stim_circuit) builds a DEM (stim raises on non-deterministic detectors), and the
     evaluator template (candidate.memory_circuit, validate_schedule) accepts the schedule;
  3. interior mechanism sets are EQUAL: {(detector mask, observable)} of all bulk single-fault mechanisms whose
     detectors all lie in rounds [2, R-2], vs all stim DEM mechanisms whose detectors all lie there (R = 8);
  4. bulk min weight (<= 3) vs exact min weight of the own stim DEM at R = 8 and of the evaluator DEM at R = 8.
usage: uv run python -m search.experiments.e038.validate_model N 7 --n 20     (or W 8, W 9 ...)
"""
import argparse
import json
import random
import time

from pysat.solvers import Solver

from search.experiments.e036_audit.core import min_weight_le
from search.experiments.e038.enc import Enc
from search.experiments.e038.model import Bulk, bulk_min, legal, stim_circuit, stim_mechs


def sample(E, s, rng, tries=40):
    for i in range(tries):
        ass = []
        for e in rng.sample(E.ev, max(1, 6 - i // 6)):
            iv = E.tau[e]
            l = iv.eq(rng.randint(iv.lo, iv.hi))
            if l not in (True, False):
                ass.append(l)
        for k in rng.sample(E.ks, 6):
            iv = E.pi[k]
            if iv.lo < iv.hi:
                l = iv.eq(rng.randint(iv.lo, iv.hi))
                if l not in (True, False):
                    ass.append(l)
        for c in E.cl[s._ptr:]:
            s.add_clause(c)
        s._ptr = len(E.cl)
        if s.solve(assumptions=ass):
            return E.decode(s.get_model())
    return None


def evaluator_check(sch, basis, R):
    from evaluators import candidate as cand
    from search.experiments.e036.common import code
    from evaluators.noise import add_noise
    spec = cand.parse_schedule(sch.spec())
    probs = cand.validate_schedule(spec, code(sch.variant))
    circ = add_noise(cand.memory_circuit(spec, code(sch.variant), basis, R), "sd6", 1e-3)
    return probs, circ


def interior_compare(sch, basis, R):
    circ, dets = stim_circuit(sch, basis, R)
    sm = stim_mechs(circ)
    inv = {v: kj for kj, v in dets.items()}
    lo, hi = 2, R - 2

    def stim_interior(d):
        out = []
        i = 0
        while d:
            if d & 1:
                k, j = inv[i]
                if not (lo <= j <= hi):
                    return None
                out.append((k, j))
            d >>= 1
            i += 1
        return frozenset(out)
    S = set()
    for d, o in sm:
        if d == 0:
            S.add((frozenset(), o))
            continue
        x = stim_interior(d)
        if x is not None:
            S.add((x, o))
    bk = Bulk(sch, basis, W=R)
    B = set()
    for d, o, tag in bk.mechs():
        out = []
        ok = True
        i = 0
        dd = d
        while dd:
            if dd & 1:
                c = bk.readers[i // bk.NJ]
                j = i % bk.NJ - 4
                if not (lo <= j <= hi):
                    ok = False
                    break
                out.append((c, j))
            dd >>= 1
            i += 1
        if ok and (out or o):
            B.add((frozenset(out), o))
    return S, B, circ, sm


def main(cls, n_or_p, n, seed, R):
    rng = random.Random(seed)
    E = Enc("bb18", cls, n_or_p)
    s = Solver(name="cd15", bootstrap_with=E.cl)
    s._ptr = len(E.cl)
    stats = {"cls": cls, "arg": n_or_p, "n": 0, "legal_fail": 0, "eval_problems": 0, "interior_mismatch": 0,
             "bulk_vs_stim": [], "seed": seed, "R": R}
    t0 = time.time()
    for it in range(n):
        sch = sample(E, s, rng)
        if sch is None:
            print("no sample")
            break
        ok, why = legal(sch)
        stats["legal_fail"] += (not ok)
        if not ok:
            print("ILLEGAL", why)
            continue
        row = {}
        for b in ("Z", "X"):
            S, B, circ, sm = interior_compare(sch, b, R)
            if S != B:
                stats["interior_mismatch"] += 1
                print("MISMATCH", b, len(S - B), len(B - S), json.dumps(sch.to_json()))
            probs, ecirc = evaluator_check(sch, b, R)
            if probs:
                stats["eval_problems"] += 1
                print("EVAL", probs[:3])
            wb, _ = bulk_min(sch, 3, W=6, bases=(b,))
            ws, _ = min_weight_le(sm, 3)
            we, _ = min_weight_le(stim_mechs(ecirc), 3)
            row[b] = (wb, ws, we)
        stats["bulk_vs_stim"].append(row)
        stats["n"] += 1
        print(it, row, round(time.time() - t0, 1), flush=True)
    print(json.dumps(stats))
    with open("results/E-038-bb18-d4/validate_model.jsonl", "a") as f:
        f.write(json.dumps(stats) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cls")
    ap.add_argument("arg", type=int)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=20261026)
    ap.add_argument("--R", type=int, default=8)
    a = ap.parse_args()
    main(a.cls, a.arg, a.n, a.seed, a.R)
