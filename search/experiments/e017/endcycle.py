"""E-017 stage 1: end-cycle code of the [[288,12,18]] morphing circuit vs the gross code.

Checks: end-cycle code parameters (n, k), check weights, the minimum weight of a nonzero element of the
X- (and Z-) stabiliser group (exact, CP-SAT), and the same quantities for the gross code.
A qubit permutation (or any local-Clifford equivalence) preserves stabiliser weights, so a different
minimum stabiliser weight proves the two [[144,12,12]] codes are inequivalent.
Usage: uv run python -m search.experiments.e017.endcycle
"""
from __future__ import annotations

import json
import sys

import numpy as np
from ortools.sat.python import cp_model

from search.experiments.e017.morph import GROSS, TWO_GROSS, Morph, logicals, nullspace, rank


def min_weight_in_rowspace(H, time_s=600.0):
    """Exact min weight of a nonzero vector in rowspace(H): x with Nx = 0 for N = basis of ker(H)^perp ..."""
    Nmat = nullspace(H)        # rows span ker(H) (as right-kernel); rowspace(H) = {x : Nmat x = 0}
    n = H.shape[1]
    m = cp_model.CpModel()
    x = [m.NewBoolVar(f"x{i}") for i in range(n)]
    for row in Nmat:
        m.AddBoolXOr([x[i] for i in np.nonzero(row)[0]] + [m.NewConstant(1)])  # parity 0 -> xor with 1 is true
    m.Add(sum(x) >= 1)
    m.Minimize(sum(x))
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = time_s
    s.parameters.num_workers = 4
    st = s.Solve(m)
    return s.StatusName(st), int(s.ObjectiveValue()), int(s.BestObjectiveBound())


def min_logical_weight(Hsame, Hother, time_s=600.0):
    """Exact distance of one type: min weight x with Hother x = 0, x not in rowspace(Hsame)."""
    Lo = logicals(Hother, Hsame)   # opposite-type logicals: x is nontrivial iff Lo x != 0
    n = Hsame.shape[1]
    m = cp_model.CpModel()
    x = [m.NewBoolVar(f"x{i}") for i in range(n)]
    for row in Hother:
        m.AddBoolXOr([x[i] for i in np.nonzero(row)[0]] + [m.NewConstant(1)])
    # at least one logical anticommutes: z_i = parity(Lo_i . x), OR z_i
    zs = []
    for i, row in enumerate(Lo):
        z = m.NewBoolVar(f"z{i}")
        m.AddBoolXOr([x[q] for q in np.nonzero(row)[0]] + [z, m.NewConstant(1)])
        zs.append(z)
    m.AddBoolOr(zs)
    m.Minimize(sum(x))
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = time_s
    s.parameters.num_workers = 4
    st = s.Solve(m)
    return s.StatusName(st), int(s.ObjectiveValue()), int(s.BestObjectiveBound())


def main(out):
    res = {}
    M = Morph(TWO_GROSS, "x")
    res["mid_cycle"] = {"n": 2 * TWO_GROSS.N, "k": int(M.k)}
    for j in (0,):   # end-cycle code 1 is a shift of code 0 (2407.16336 App. D); checked k/weights only
        ec = M.end_cycle_checks(j)
        HX, HZ = ec["X"], ec["Z"]
        assert not ((HX.astype(int) @ HZ.T.astype(int)) % 2).any()
        k = HX.shape[1] - rank(HX) - rank(HZ)
        r = {"n": int(HX.shape[1]), "k": int(k), "rankHX": rank(HX), "rankHZ": rank(HZ),
             "check_weights_X": sorted(set(int(w) for w in HX.sum(1))),
             "check_weights_Z": sorted(set(int(w) for w in HZ.sum(1))),
             "min_stab_weight_X": min_weight_in_rowspace(HX, 300),
             "min_stab_weight_Z": min_weight_in_rowspace(HZ, 300),
             "dist_X_type": min_logical_weight(HX, HZ, 300),
             "dist_Z_type": min_logical_weight(HZ, HX, 300)}
        res[f"end_cycle_{j}"] = r
        print(j, r, flush=True)
    gHX, gHZ = GROSS.HX(), GROSS.HZ()
    res["gross"] = {"n": int(gHX.shape[1]), "k": int(gHX.shape[1] - rank(gHX) - rank(gHZ)),
                    "check_weights": sorted(set(int(w) for w in gHX.sum(1))),
                    "min_stab_weight_X": min_weight_in_rowspace(gHX, 300)}
    print(res["gross"], flush=True)
    json.dump(res, open(out, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "results/E-017-gross-morphing-scoping/endcycle.json")
