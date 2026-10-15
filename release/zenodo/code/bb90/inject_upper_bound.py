"""Upper bound d_circ <= 10 for c16 (and any circuit of this template): inject the weight-10 witnesses.

witnesses/bb90_upper_bound_weight10.json holds, for each memory basis b, a weight-10 logical operator of [[90,8,10]]
of the type that flips the b-basis observables (X type for the Z basis, Z type for the X basis).  It is applied as
ten single-qubit flips immediately after the data initialisation (each flip is the after-reset flip of one data
qubit, i.e. one SD6 mechanism).  For R = 1, 2, 3, 6, 10, 13 and both bases: no detector fires and the logical
observable flips; omitting any one of the ten flips is detected.

    python code/bb90/inject_upper_bound.py c16
"""
import json
import sys
from pathlib import Path

import numpy as np
import stim

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common_cli import Verdict                      # noqa: E402
from bb90 import bbcode, ext as E                   # noqa: E402
from gross12.noise import add_sd6                   # noqa: E402
from gross12.paths import WITNESSES                 # noqa: E402
from gross12.schedule import build_circuits         # noqa: E402

names = sys.argv[1:] or ["c16"]
code = bbcode.load_code()
V = Verdict()
W = json.load(open(WITNESSES / "bb90_upper_bound_weight10.json"))
for basis in "ZX":
    supp = W["witnesses"][basis]["support"]
    H, L = E.hl(code, basis)
    v = np.zeros(90, np.uint8); v[supp] = 1
    V(len(supp) == 10 and not ((H @ v) % 2).any() and ((L @ v) % 2).any(),
      f"witness {basis} basis: weight {len(supp)}, commutes with H{basis}, flips logical rows "
      f"{np.flatnonzero((L @ v) % 2).tolist()}")
err = {"Z": "X_ERROR", "X": "Z_ERROR"}
for name in names:
    spec = E.circuit(name).canonical()
    for basis in "ZX":
        supp = W["witnesses"][basis]["support"]
        for R in (1, 2, 3, 6, 10, 13):
            c = build_circuits(spec, code, R)[basis]
            noisy = add_sd6(c)
            assert noisy[0].name == ("R" if basis == "Z" else "RX") and noisy[1].name == err[basis]
            assert set(range(90)) <= {t.value for t in noisy[1].targets_copy()}
            ops = list(c)

            def run(sub):
                inj = stim.Circuit()
                inj.append(ops[0]); inj.append(err[basis], sub, 1.0)
                for op in ops[1:]:
                    inj.append(op)
                s = inj.compile_detector_sampler(seed=3).sample(2, append_observables=True)
                return s[0, :inj.num_detectors], s[0, inj.num_detectors:]
            dets, obs = run(supp)
            minus = [run(supp[:i] + supp[i + 1:])[0].any() for i in range(10)]
            V(not dets.any() and obs.any() and all(minus),
              f"[{name}] {basis} basis R={R}: weight-10 injection fires no detector, flips observables "
              f"{np.flatnonzero(obs).tolist()}; omitting any one flip is detected ({sum(minus)}/10)")
V.exit()
