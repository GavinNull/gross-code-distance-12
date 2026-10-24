"""SM S15 (upper bound d_circ <= 12 for circuits A, B, C): inject the weight-12 witnesses.

witnesses/upper_bound_weight12.json holds, for each memory basis b, a weight-12 logical operator of the gross code
of the type that flips the b-basis observables (X type for the Z basis, Z type for the X basis).  It is applied as
twelve single-qubit flips immediately after the data initialisation (each flip is the after-reset flip of one data
qubit, i.e. one SD6 mechanism).  For every circuit, R = 1, 2, 3, 6, 10 and both bases: no detector fires and the
logical observable flips; omitting any one of the twelve flips is detected.
With --search the witnesses are recomputed (CP-SAT minimum-weight logical flipping logical row 0).

    python code/inject_upper_bound.py A B C
"""
import json
import sys

import numpy as np
import stim

from common_cli import Verdict, circuit, load_code
from gross12.ext import hl
from gross12.noise import add_sd6
from gross12.paths import WITNESSES
from gross12.schedule import build_circuits

args = [x for x in sys.argv[1:] if not x.startswith("--")]
names = args or ["A", "B", "C"]
code = load_code()
V = Verdict()
W = json.load(open(WITNESSES / "upper_bound_weight12.json"))
if "--search" in sys.argv:
    from ortools.sat.python import cp_model
    for basis in "ZX":
        H, L = hl(code, basis)
        M = cp_model.CpModel(); x = [M.NewBoolVar("") for _ in range(144)]
        for row in H:
            k = M.NewIntVar(0, 6, ""); M.Add(sum(x[j] for j in np.nonzero(row)[0]) == 2 * k)
        k = M.NewIntVar(0, 72, ""); M.Add(sum(x[j] for j in np.nonzero(L[0])[0]) == 2 * k + 1)
        M.Minimize(sum(x))
        s = cp_model.CpSolver(); s.parameters.max_time_in_seconds = 120; s.parameters.num_workers = 1
        st = s.Solve(M)
        supp = [j for j in range(144) if s.Value(x[j])]
        print(basis, "CP-SAT:", s.StatusName(st), "weight", len(supp), supp)
        W["witnesses"][basis]["support"] = supp
for basis in "ZX":
    supp = W["witnesses"][basis]["support"]
    H, L = hl(code, basis)
    v = np.zeros(144, np.uint8); v[supp] = 1
    V(len(supp) == 12 and not ((H @ v) % 2).any() and ((L @ v) % 2).any(),
      f"witness {basis} basis: weight {len(supp)}, commutes with H{basis}, flips logical rows "
      f"{np.flatnonzero((L @ v) % 2).tolist()}")
err = {"Z": "X_ERROR", "X": "Z_ERROR"}
for name in names:
    spec = circuit(name).canonical()
    for basis in "ZX":
        supp = W["witnesses"][basis]["support"]
        for R in (1, 2, 3, 6, 10):
            c = build_circuits(spec, code, R)[basis]
            noisy = add_sd6(c)
            # the after-reset flips of the data qubits are the second instruction of the SD6 circuit
            assert noisy[0].name == ("R" if basis == "Z" else "RX") and noisy[1].name == err[basis]
            assert set(range(144)) <= {t.value for t in noisy[1].targets_copy()}
            ops = list(c)

            def run(sub):
                inj = stim.Circuit()
                inj.append(ops[0]); inj.append(err[basis], sub, 1.0)
                for op in ops[1:]:
                    inj.append(op)
                s = inj.compile_detector_sampler(seed=3).sample(2, append_observables=True)
                return s[0, :inj.num_detectors], s[0, inj.num_detectors:]
            dets, obs = run(supp)
            minus = [run(supp[:i] + supp[i + 1:])[0].any() for i in range(12)]
            V(not dets.any() and obs.any() and all(minus),
              f"[{name}] {basis} basis R={R}: weight-12 injection fires no detector, flips observables "
              f"{np.flatnonzero(obs).tolist()}; omitting any one flip is detected ({sum(minus)}/12)")
V.exit()
