"""A5: upper bound.  Take the project's weight-12 supports, re-verify with the own code that each is a logical
(in ker H, not in the stabiliser row space, flips some own L), and inject them as 12 reset-flip faults (an SD6 fault
location) right after the data reset in the OWN noiseless circuit; expect 0 detectors and a flipped observable.
Usage: a5_inject12.py SPEC"""
import sys, json
sys.path.insert(0, "research/audits/2026-10-22-E-032-scripts")
import numpy as np, stim
from alib32 import *

spec = load_spec(sys.argv[1])
HX, HZ, LX, LZ = code()
sup = json.load(open("results/E-032-gross-short-period/inject12_u11_spec.json"))
out = {}
for basis in "ZX":
    s = sup[basis]["support"]
    v = np.zeros(N, np.uint8); v[s] = 1
    H, Hother, L = (HZ, HX, LZ) if basis == "Z" else (HX, HZ, LX)
    r = {"weight": int(v.sum()), "in_kerH": not (H.astype(int) @ v % 2).any(),
         "not_stabiliser": rank(np.vstack([Hother, v])) > rank(Hother), "own_L_flips": int((L.astype(int) @ v % 2).sum())}
    for R in (1, 2, 3, 6, 10, 31):
        c = memory_circuit(spec, basis, R, noise=False)
        ops = list(c)
        inj = stim.Circuit()
        inj.append(ops[0])   # data reset
        assert ops[0].name == ("R" if basis == "Z" else "RX")
        inj.append("X_ERROR" if basis == "Z" else "Z_ERROR", s, 1.0)
        for op in ops[1:]:
            inj.append(op)
        d, o = inj.compile_detector_sampler().sample(4, separate_observables=True)
        r[f"R{R}"] = {"detectors_fired": int(d.sum(1).max()), "obs_flipped": int(o.sum(1).min())}
    out[basis] = r
    print(basis, json.dumps(r), flush=True)
json.dump(out, open("results/E-032-audit/a5_inject12.json", "w"))
