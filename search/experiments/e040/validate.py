"""E-040: validate the bulk model (bulk.Sector) against stim DEMs of the evaluator template (memory_circuit + sd6).

For random signatures (representative time vectors from sigs_P*.json): evaluator validate_schedule must return no
problem; stim DEM (Z and X basis, R rounds, sd6) must be deterministic; and the set of (detector set, observable
vector) of DEM mechanisms whose detectors all lie in rounds [lo, hi] must EQUAL the set of bulk-model mechanisms whose
detectors (after one global round shift delta per basis) all lie in [lo, hi].

    PYTHONPATH=.:tests uv run python -m search.experiments.e040.validate --code bb90 --P 8 --n 10
"""
from __future__ import annotations

import argparse
import json
import random

import numpy as np

from evaluators.candidate import build_circuits, parse_schedule, validate_schedule
from evaluators.noise import add_noise
from search.experiments.e040.bulk import Sector, spec_of
from search.experiments.e040.codes import MOD, OUT


def stim_set(circ, lo, hi, k):
    dem = circ.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    coords = dem.get_detector_coordinates()
    out = set()
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        ds, ob = [], [0] * k
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                ds.append(t.val)
            elif t.is_logical_observable_id():
                ob[t.val] ^= 1
        if not ds:
            continue
        cs = [(int(coords[d][0]), int(coords[d][1])) for d in ds]
        if all(lo <= j <= hi for _, j in cs):
            out.add((frozenset(cs), tuple(ob)))
    return out


def model_set(S, lo, hi, delta):
    out = set()
    for f in S.all_mechanisms(lo - delta - 4, hi - delta + 4):
        D, e = S.effect([f])
        if not D:
            continue
        D2 = frozenset((c, r + delta) for c, r in D)
        if all(lo <= j <= hi for _, j in D2):
            out.add((D2, tuple(int(v) for v in (S.L @ e % 2))))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--R", type=int, default=9)
    ap.add_argument("--seed", type=int, default=20261029)
    a = ap.parse_args()
    C = MOD[a.code]
    code = C.css()
    rows = json.loads((OUT / f"sigs_P{a.P}.json").read_text())
    rng = random.Random(a.seed)
    lo, hi = 3, a.R - 4
    res = []
    for row in rng.sample(rows, a.n):
        d = spec_of(a.code, row["tx"], row["tz"], a.P)
        spec = parse_schedule(d).canonical()
        probs = validate_schedule(spec, code)
        assert not probs, probs[:3]
        circs = build_circuits(spec, code, a.R)
        rec = {"tx": row["tx"], "tz": row["tz"]}
        for basis, kind in (("Z", "X"), ("X", "Z")):
            circ = add_noise(circs[basis], "sd6", 1e-3)
            ss = stim_set(circ, lo, hi, code.k)
            S = Sector(a.code, kind, row["tx"], row["tz"], a.P)
            best = None
            for delta in range(-8, 9):
                ms = model_set(S, lo, hi, delta)
                if ms == ss:
                    best = delta
                    break
            rec[basis] = {"n_stim": len(ss), "equal": best is not None, "delta": best}
            assert best is not None, (rec, len(ss))
        res.append(rec)
        print(json.dumps(rec), flush=True)
    with open(OUT / "validate.jsonl", "a") as f:
        for r in res:
            f.write(json.dumps({"code": a.code, "P": a.P, **r}) + "\n")
    print("ALL EQUAL", len(res))


if __name__ == "__main__":
    main()
