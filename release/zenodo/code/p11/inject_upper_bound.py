"""Upper bounds for the period-11 circuits and their relatives: inject the data-logical witnesses.

u11 (gross code): witnesses/upper_bound_weight12.json, a weight-12 X-type logical (Z basis) and Z-type logical
(X basis), d_circ <= 12.  c11, c12, c13 ([[90,8,10]]): witnesses/bb90_upper_bound_weight10.json, weight 10,
d_circ <= 10.  The witness is applied as single-qubit flips immediately after the data initialisation (each flip is
the after-reset flip of one data qubit, i.e. one SD6 mechanism).  For every R of the list and both bases: no
detector fires and the logical observable flips; omitting any one flip is detected.

    python code/p11/inject_upper_bound.py u11 c11 c12 c13 [--R 1,2,3,6,10,31]
"""
import json
import sys
from pathlib import Path

import numpy as np
import stim

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common_cli import Verdict, parse_range         # noqa: E402
from p11 import common as C                          # noqa: E402
from gross12.noise import add_sd6                    # noqa: E402
from gross12.schedule import build_circuits          # noqa: E402

args = sys.argv[1:]
Rarg = None
if "--R" in args:
    i = args.index("--R"); Rarg = parse_range(args[i + 1]); args = args[:i] + args[i + 2:]
names = args or ["u11", "c11", "c12", "c13"]
WFILE = {"gross": ("upper_bound_weight12.json", 12, [1, 2, 3, 6, 10, 31]),
         "bb90": ("bb90_upper_bound_weight10.json", 10, [1, 2, 5, 11, 25])}
V = Verdict()
err = {"Z": "X_ERROR", "X": "Z_ERROR"}
checked = set()
for name in names:
    fam = C.family_of(name)
    code = C.load_code(fam)
    fn, w, Rs = WFILE[fam]
    W = json.load(open(C.WITNESSES / fn))
    if fam not in checked:
        checked.add(fam)
        for basis in "ZX":
            supp = W["witnesses"][basis]["support"]
            H, L = C.hl(code, basis)
            v = np.zeros(code.n, np.uint8); v[supp] = 1
            V(len(supp) == w and not ((H @ v) % 2).any() and ((L @ v) % 2).any(),
              f"witness {fn} {basis} basis: weight {len(supp)}, commutes with H{basis}, flips logical rows "
              f"{np.flatnonzero((L @ v) % 2).tolist()}")
    spec = C.circuit(name).canonical()
    for basis in "ZX":
        supp = W["witnesses"][basis]["support"]
        for R in (Rarg or Rs):
            c = build_circuits(spec, code, R)[basis]
            noisy = add_sd6(c)
            # the after-reset flips of the data qubits are the second instruction of the SD6 circuit
            assert noisy[0].name == ("R" if basis == "Z" else "RX") and noisy[1].name == err[basis]
            assert set(range(code.n)) <= {t.value for t in noisy[1].targets_copy()}
            ops = list(c)

            def run(sub):
                inj = stim.Circuit()
                inj.append(ops[0]); inj.append(err[basis], sub, 1.0)
                for op in ops[1:]:
                    inj.append(op)
                s = inj.compile_detector_sampler(seed=3).sample(2, append_observables=True)
                return s[0, :inj.num_detectors], s[0, inj.num_detectors:]
            dets, obs = run(supp)
            minus = [run(supp[:i] + supp[i + 1:])[0].any() for i in range(w)]
            V(not dets.any() and obs.any() and all(minus),
              f"[{name}] {basis} basis R={R}: weight-{w} injection fires no detector, flips observables "
              f"{np.flatnonzero(obs).tolist()}; omitting any one flip is detected ({sum(minus)}/{w})")
V.exit()
