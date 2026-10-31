"""E-041: LER of the period-9 d_circ = 4 circuit vs Kunlun and E-038's bb18_n8_d4, E-036 pipeline (Tab. S1 'kl' noise on
the evaluator's noiseless circuit, BP-OSD min-sum 100 iters OSD-CS 7, Jeffreys 95%), 200,000 shots, R = 6, scale 1 and
0.1, seed 20261031 (fresh samples for all three circuits).

Two noise mappings:
  kl      : E-036's kl_noise unchanged.  A layer containing CX is a "CZ layer" even if it also contains measurements.
  klmix   : conservative for pipelined circuits: a layer that contains a (non-final) measurement lasts the readout time,
            so every qubit not measured in it gets the readout dynamical-decoupling channel (p_DX, p_DZ) instead of the
            CZ-slot idle p_I; CX pairs keep p_cz and the p_H single-qubit layer.  For circuits without mixed CX +
            measurement layers (Kunlun, n8) klmix == kl (asserted).
usage: uv run python -m search.experiments.e041.ler <circuit> <basis> <scale> <kl|klmix>"""
import json
import sys
import time

import numpy as np
import stim

from search.experiments.e036.common import noiseless
from search.experiments.e036.dcirc import get_spec
from search.experiments.e036.ler import IBM_BPOSD, KL, jeffreys, kl_noise

OUT = "results/E-041-bb18-p9"


def kl_noise_mixed(c: stim.Circuit, s: float = 1.0) -> stim.Circuit:
    P = {k: min(v * s, 0.5) for k, v in KL.items()}
    allq = list(range(c.num_qubits))
    out = stim.Circuit()
    segs, cur = [], []
    for op in c.flattened():
        if op.name == "TICK":
            segs.append(cur)
            cur = []
        else:
            cur.append(op)
    segs.append(cur)
    for i, layer in enumerate(segs):
        final = i == len(segs) - 1
        ops = [op for op in layer if op.name not in ("DETECTOR", "OBSERVABLE_INCLUDE")]
        names = {op.name for op in ops}
        has_cx = "CX" in names
        has_m = bool(names & {"M", "MX"})
        used, measured = set(), set()
        for op in ops:
            for t in op.targets_copy():
                if t.is_qubit_target:
                    used.add(t.value)
                    if op.name in ("M", "MX"):
                        measured.add(t.value)
        for op in layer:
            if op.name in ("M", "MX"):
                out.append(op.name, [t.value for t in op.targets_copy()], P["p_F"] if final else P["p_M"])
            else:
                out.append(op)
                if op.name == "CX":
                    out.append("DEPOLARIZE2", [t.value for t in op.targets_copy()], P["p_cz"])
        if has_cx and has_m and not final:
            others = [q for q in allq if q not in measured]
            out.append("PAULI_CHANNEL_1", others, [P["p_DX"], 0, P["p_DZ"]])
            out.append("DEPOLARIZE1", allq, P["p_H"])
        elif has_cx:
            idle = [q for q in allq if q not in used]
            if idle:
                out.append("DEPOLARIZE1", idle, P["p_I"])
            out.append("DEPOLARIZE1", allq, P["p_H"])
        elif has_m and not final:
            others = [q for q in allq if q not in used]
            if others:
                out.append("PAULI_CHANNEL_1", others, [P["p_DX"], 0, P["p_DZ"]])
        elif not final:
            out.append("DEPOLARIZE1", allq, P["p_H"])
        if not final:
            out.append("TICK")
    return out


def run(name, basis, scale, mapping, R=6, shots=200000, seed=20261031):
    from stimbposd import BPOSD
    spec = get_spec("bb18", name)
    base = noiseless(spec, "bb18", basis, R)
    circ = kl_noise(base, scale) if mapping == "kl" else kl_noise_mixed(base, scale)
    same = str(kl_noise(base, scale)) == str(kl_noise_mixed(base, scale))
    dem = circ.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    dec = BPOSD(dem, **IBM_BPOSD)
    sampler = circ.compile_detector_sampler(seed=seed)
    t0 = time.time()
    fails = done = 0
    while done < shots:
        b = min(5000, shots - done)
        det, obs = sampler.sample(b, separate_observables=True)
        pred = dec.decode_batch(det)
        fails += int(np.any(pred != obs, axis=1).sum())
        done += b
    lo, hi = jeffreys(fails, done)
    return {"circuit": name, "basis": basis, "scale": scale, "mapping": mapping, "kl_equals_klmix": same, "R": R,
            "shots": done, "fails": fails, "P": fails / done, "lo": lo, "hi": hi, "dem_errors": dem.num_errors,
            "sec": round(time.time() - t0, 1), "seed": seed}


if __name__ == "__main__":
    name, basis, scale, mapping = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
    r = run(name, basis, scale, mapping)
    print(json.dumps(r), flush=True)
    with open(f"{OUT}/ler.jsonl", "a") as f:
        f.write(json.dumps(r) + "\n")
