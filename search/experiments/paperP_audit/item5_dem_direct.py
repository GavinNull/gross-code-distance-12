"""Item 5: direct circuit-distance decision for c11 on the evaluator's SD6 DEM (no extended code, no bulk model).
Is there a set of <= W distinct DEM mechanisms (merged by (detectors, observables) signature) with zero detector
parity and odd parity on some observable?  Own CP-SAT model (parity via XOR constraints with auxiliary literals),
spatial translation symmetry breaking (the circuit is translation invariant under the 45 code translations, so a
solution can be translated to touch a detector of check 0), single worker.  Solutions re-verified by XOR.
  PYTHONPATH=.:tests uv run python search/experiments/paperP_audit/item5_dem_direct.py <basis> <R> <W> [timelimit_s] [--nosym] [--xor]
"""
import json, sys, time
from collections import defaultdict
from pathlib import Path
import numpy as np
from ortools.sat.python import cp_model
from evaluators import candidate as cand
from evaluators.noise import add_noise
from search.theory.B_audit.common import get_code

ROOT = Path(__file__).resolve().parents[3]


def mechanisms(basis, R):
    spec = json.loads((ROOT / "search/experiments/e030/c11_spec.json").read_text())
    circ = add_noise(cand.memory_circuit(cand.parse_schedule(spec), get_code("bb90"), basis, R), "sd6", 1e-3)
    dem = circ.detector_error_model(decompose_errors=False, flatten_loops=True)
    coords = circ.get_detector_coordinates()
    sigs = set()
    for e in dem.flattened():
        if e.type != "error":
            continue
        ds, os_ = set(), set()
        for t in e.targets_copy():
            if t.is_relative_detector_id():
                ds ^= {t.val}
            elif t.is_logical_observable_id():
                os_ ^= {t.val}
        if ds or os_:
            sigs.add((frozenset(ds), frozenset(os_)))
    return sorted(sigs, key=lambda s: (sorted(s[0]), sorted(s[1]))), dem.num_detectors, coords


def main():
    basis, R, W = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    tl = float(sys.argv[4]) if len(sys.argv) > 4 and not sys.argv[4].startswith("--") else 3600
    sym = "--nosym" not in sys.argv
    t0 = time.time()
    M, nd, coords = mechanisms(basis, R)
    assert all(m[0] for m in M), "a mechanism flips only observables (weight-1 logical)"
    md = cp_model.CpModel(); e = [md.NewBoolVar("") for _ in M]
    byd, byo = defaultdict(list), defaultdict(list)
    for i, (ds, os_) in enumerate(M):
        for d in ds: byd[d].append(e[i])
        for o in os_: byo[o].append(e[i])
    xor = "--xor" in sys.argv
    for d, l in byd.items():
        if xor:
            md.AddBoolXOr(l + [md.NewConstant(1)])                   # even parity
        else:
            md.Add(sum(l) == 2 * md.NewIntVar(0, len(l) // 2, ""))   # even parity (integer form)
    ps = []
    for o, l in byo.items():
        p = md.NewBoolVar("")
        if xor:
            md.AddBoolXOr(l + [p.Not()])
        else:
            md.Add(sum(l) == 2 * md.NewIntVar(0, len(l) // 2, "") + p)
        ps.append(p)
    md.AddBoolOr(ps)
    md.Add(sum(e) <= W)
    if sym:
        check0 = {d for d in range(nd) if int(coords[d][0]) == 0}
        md.AddBoolOr([e[i] for i, (ds, _) in enumerate(M) if ds & check0])
    s = cp_model.CpSolver(); s.parameters.num_workers = 1; s.parameters.max_time_in_seconds = tl
    st = s.Solve(md)
    found = None
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        sol = [i for i in range(len(M)) if s.Value(e[i])]
        dd, oo = set(), set()
        for i in sol:
            dd ^= set(M[i][0]); oo ^= set(M[i][1])
        assert not dd and oo
        found = len(sol)
    print(json.dumps({"basis": basis, "R": R, "W<=": W, "sym": sym, "xor": xor, "n_mech": len(M), "n_det": nd,
                      "status": s.StatusName(st), "found_weight": found, "solve_s": round(s.WallTime(), 1),
                      "total_s": round(time.time() - t0, 1)}), flush=True)


if __name__ == "__main__":
    main()
