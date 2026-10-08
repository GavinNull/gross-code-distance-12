"""E-017: weight-12 upper-bound witnesses by injection, and verification of DFS solutions.

(a) end-cycle logical witness: a minimum-weight logical of the end-cycle code (found by CP-SAT, weight 12),
    injected as Pauli errors (prob. 1) on left qubits in the idle slot of the reset layer of round t of the
    noiseless memory circuit; each is one component of the sd6 idle DEPOLARIZE1 there. Check: 0 detectors fire,
    >= 1 observable flips, for R = 1..6, both bases, t in {1, ..., R} (t=1: right after the data reset).
Usage: uv run python -m search.experiments.e017.witness --out results/E-017-gross-morphing-scoping/witness_endcycle.json
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import stim
from ortools.sat.python import cp_model

from search.experiments.e017.morph import TWO_GROSS, Morph, logicals


def end_cycle_logical(M, j, P, seconds=600, fix=None):
    ec = M.end_cycle_checks(j)
    Hs, Ho = (ec["X"], ec["Z"]) if P == "X" else (ec["Z"], ec["X"])
    Lo = logicals(Ho, Hs)
    n = Hs.shape[1]
    m = cp_model.CpModel()
    x = [m.NewBoolVar("") for _ in range(n)]
    one = m.NewConstant(1)
    for row in Ho:
        m.AddBoolXOr([x[i] for i in np.nonzero(row)[0]] + [one])
    zs = []
    for row in Lo:
        z = m.NewBoolVar("")
        m.AddBoolXOr([x[i] for i in np.nonzero(row)[0]] + [z, one])
        zs.append(z)
    m.AddBoolOr(zs)
    m.Add(sum(x) <= 12)
    if fix is not None:
        m.Add(x[fix] == 1)
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = seconds
    s.parameters.num_workers = 4
    st = s.Solve(m)
    print('cpsat', s.StatusName(st), round(s.WallTime(), 1), flush=True)
    assert s.StatusName(st) in ("OPTIMAL", "FEASIBLE"), s.StatusName(st)
    return [i for i in range(n) if s.Value(x[i])]


def inject(circ: stim.Circuit, layer: int, qubits, P):
    """Insert P_ERROR(1) on qubits at the end of layer `layer` (before the layer-th TICK)."""
    out = stim.Circuit()
    tick = 0
    done = False
    for ins in circ.flattened():
        if ins.name == "TICK":
            if tick == layer and not done:
                out.append(f"{P}_ERROR", qubits, 1.0)
                done = True
            tick += 1
        out.append(ins)
    assert done
    return out


def check(circ):
    det, obs = circ.compile_detector_sampler().sample(4, separate_observables=True)
    return (not det.any()), bool(obs.any(axis=1).all())


# weight-12 end-cycle logicals found by dfsw on ec_j{j}_{P}.txt (results/E-017-gross-morphing-scoping/dfs/ec_dfs.txt)
DFS_SUPPORTS = {(0, "X"): [12, 37, 17, 70, 69, 64, 18, 109, 141, 89, 116, 110],
                (0, "Z"): [0, 7, 27, 58, 79, 59, 6, 52, 98, 131, 99, 104],
                (1, "X"): [0, 25, 5, 58, 57, 52, 6, 97, 129, 77, 104, 98],
                (1, "Z"): [12, 19, 39, 70, 64, 18, 71, 91, 143, 110, 111, 116]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hom", default="x")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    M = Morph(TWO_GROSS, a.hom)
    res = []
    cache = {}
    for basis in "ZX":
        P = "X" if basis == "Z" else "Z"          # error type flipping the memory observable
        for R in range(1, 7):
            for t in range(1, R + 1):
                j_prev = 1 - ((1 + t - 1) % 2)      # end-cycle code before round t (first_j = 1)
                if (j_prev, P) not in cache:
                    cache[(j_prev, P)] = DFS_SUPPORTS[(j_prev, P)]
                supp = cache[(j_prev, P)]
                c = M.memory_circuit(basis, R, first_j=1)
                layer = 8 * (t - 1)                 # reset layer of round t
                ok_det, ok_obs = check(inject(c, layer, supp, P))
                res.append({"basis": basis, "R": R, "t": t, "weight": len(supp), "support": supp,
                            "no_detector": ok_det, "flips_observable": ok_obs})
                print(basis, R, t, len(supp), ok_det, ok_obs, flush=True)
    json.dump(res, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
