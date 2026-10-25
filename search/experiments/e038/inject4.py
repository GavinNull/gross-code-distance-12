"""E-038: weight-4 upper bound by explicit injection: in the evaluator memory circuit (noiseless) put X (Z) errors on
the support of a weight-4 Z-memory-flipping X logical (X-memory: Z logical) right after the data reset, simulate,
and check that no detector fires and some observable flips.  usage: uv run python -m search.experiments.e038.inject4 SPEC"""
import itertools
import json
import sys

import numpy as np
import stim

from evaluators import candidate as cand
from search.experiments.e036.common import code
from search.experiments.e036_audit.core import code_mats, observables, rank

spec = cand.parse_schedule(json.load(open(sys.argv[1])))
C = code("bb18")
HX, HZ = code_mats("bb18")
out = {}
for basis in ("Z", "X"):
    Hc, Hs = (HZ, HX) if basis == "Z" else (HX, HZ)   # error commutes with Hc checks, nontrivial mod Hs
    L = observables("bb18", basis)
    found = None
    for sup in itertools.combinations(range(18), 4):
        v = np.zeros(18, np.uint8)
        v[list(sup)] = 1
        if (Hc @ v % 2).any():
            continue
        if not ((L @ v) % 2).any():
            continue
        found = sup
        break
    rows = []
    for R in range(1, 7):
        c = cand.memory_circuit(spec, C, basis, R)
        c2 = stim.Circuit()
        done = False
        for inst in c:
            c2.append(inst)
            if not done:  # first instruction = data reset (R or RX, possibly with ancillas)
                c2.append("X_ERROR" if basis == "Z" else "Z_ERROR", list(found), 1.0)
                done = True
        s = c2.compile_detector_sampler()
        det, obs = s.sample(1, separate_observables=True)
        rows.append((R, int(det.sum()), int(obs.sum())))
    out[basis] = {"support": found, "R_dets_obs": rows}
print(json.dumps(out))
