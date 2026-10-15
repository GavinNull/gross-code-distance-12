"""Auditor: weight-12 upper bound for circuit A at R=1,2 by data-qubit injection (release witnesses/upper_bound_weight12.json).

Insert the Pauli flips (X for Z-basis memory, Z for X-basis memory) on the witness support right after the first
noise instruction that follows the data reset in the SD6 circuit (i.e. where a reset fault acts), with all other noise
removed.  Check: no detector fires, an observable flips, each single flip alone has the signature of a DEM column
of the circuit (my own export, results/E-029-audit/A_<B>_R<R>.txt) and the 12 signatures are distinct.
"""
import json
import sys

import numpy as np
import stim

sys.path[:0] = [".", "tests"]
from evaluators.candidate import build_circuits, parse_schedule  # noqa: E402
from evaluators.noise import add_noise  # noqa: E402
from evaluators.tasks import build_code, get_task  # noqa: E402

NOISE = {"DEPOLARIZE1", "DEPOLARIZE2", "X_ERROR", "Y_ERROR", "Z_ERROR"}
code, _ = build_code(get_task("gross-dcirc"), None)
spec = parse_schedule(json.load(open("search/experiments/e024a/cs_P18_H24.json"))).canonical()
W = json.load(open("release/zenodo/witnesses/upper_bound_weight12.json"))["witnesses"]


def run(noisy, qubits, p):
    """insert p-flips on `qubits` right after the first noise instruction (following a reset) that touches each qubit."""
    out = stim.Circuit()
    pending = set(qubits)
    seen_reset = set()
    for inst in noisy:
        if inst.name in ("R", "RX", "RY", "MR", "MRX"):
            seen_reset |= {t.value for t in inst.targets_copy()}
        if inst.name in NOISE:
            tg = {t.value for t in inst.targets_copy()}
            hit = sorted(q for q in pending if q in tg and q in seen_reset)
            if hit:
                out.append(f"{p}_ERROR", hit, 1.0)
                pending -= set(hit)
            continue
        out.append(inst)
    assert not pending, pending
    det, obs = out.compile_detector_sampler().sample(1, separate_observables=True)
    return tuple(np.nonzero(det[0])[0].tolist()), tuple(np.nonzero(obs[0])[0].tolist())


for B in "ZX":
    w = W[B]
    p = "X" if w["type"] == "X" else "Z"
    for R in (1, 2):
        noisy = add_noise(build_circuits(spec, code, R)[B], "sd6", 1e-3).flattened()
        inst = open(f"results/E-029-audit/A_{B}_R{R}.txt").read().split("\n")
        nr, nc = map(int, inst[0].split()[:2])
        cols = set()
        for ln in inst[1:1 + nc]:
            v = list(map(int, ln.split()))
            k = v[0]
            cols.add((tuple(v[1:1 + k]), tuple(v[2 + k:2 + k + v[1 + k]])))
        sig = [run(noisy, [q], p) for q in w["support"]]
        d, o = run(noisy, w["support"], p)
        print(json.dumps(dict(basis=B, R=R, weight=len(w["support"]), detectors_fired=len(d), observables=list(o),
                              singles_are_dem_columns=all(s in cols for s in sig), singles_distinct=len(set(sig)) == 12)))
