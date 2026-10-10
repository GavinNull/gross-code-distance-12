"""Audit E-021 (b6): upper bound. Minimum-weight data logical (CP-SAT, own) for each basis, injected as
probability-1 errors right after the data reset into the evaluator's noiseless circuits; R = 1, 3, 6, 10.
Also counts the injected faults as distinct DEM mechanisms of the SD6 circuit (reset-flip locations).
    PYTHONPATH=.:tests uv run python research/audits/2026-10-10-E-021-scripts/b6_inject.py
"""
import json, sys
sys.path.insert(0, "research/audits/2026-10-10-E-021-scripts")
from b_common import *
from ortools.sat.python import cp_model

spec = load_spec().canonical()
info = {}
for basis in "ZX":
    H, L = (HZ, LZ) if basis == "Z" else (HX, LX)
    M = cp_model.CpModel(); x = [M.NewBoolVar("") for _ in range(144)]
    for row in H:
        k = M.NewIntVar(0, 6, ""); M.Add(sum(x[j] for j in np.nonzero(row)[0]) == 2 * k)
    # flip logical 0 (any logical suffices for an upper bound)
    row = L[0]; k = M.NewIntVar(0, 72, ""); M.Add(sum(x[j] for j in np.nonzero(row)[0]) == 2 * k + 1)
    M.Minimize(sum(x))
    s = cp_model.CpSolver(); s.parameters.max_time_in_seconds = 120; s.parameters.num_workers = 1
    st = s.Solve(M)
    supp = [j for j in range(144) if s.Value(x[j])]
    rec = {"weight": len(supp), "status": s.StatusName(st), "bound": s.BestObjectiveBound(), "support": supp}
    err = "X_ERROR" if basis == "Z" else "Z_ERROR"
    for R in (1, 3, 6, 10):
        c = build_circuits(spec, code, R)[basis]
        ops = list(c)
        assert ops[0].name == ("R" if basis == "Z" else "RX")
        inj = stim.Circuit(); inj.append(ops[0]); inj.append(err, supp, 1.0)
        for op in ops[1:]:
            inj.append(op)
        smp = inj.compile_detector_sampler(seed=3).sample(8, append_observables=True)
        nd = inj.num_detectors
        rec[f"R{R}"] = {"any_detector": bool(smp[:, :nd].any()), "obs_flipped": smp[0, nd:].astype(int).tolist()}
        # removing one injected error must be detected (sanity)
        inj2 = stim.Circuit(); inj2.append(ops[0]); inj2.append(err, supp[1:], 1.0)
        for op in ops[1:]:
            inj2.append(op)
        rec[f"R{R}"]["minus_one_detected"] = bool(inj2.compile_detector_sampler(seed=3).sample(1)[0].any())
    info[basis] = rec
    print(basis, rec, flush=True)
json.dump(info, open(f"{OUT}/b6_inject.json", "w"), indent=1)
