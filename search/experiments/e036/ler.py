"""E-036 step 6: logical error rate under the Kunlun component noise (SI Tab. S1) on the CNOT template.

Noise model "kl" (applied identically to every circuit; all circuits use the non-wrapping template
prep layer -> S CNOT layers -> measurement layer):
  CNOT layer : DEPOLARIZE2(p_cz = 9.8e-3) after each CX (= CZ conjugated by H);
               DEPOLARIZE1(p_I = 3.5e-3) on every qubit not in a CX in that layer (idle for one CZ slot);
               DEPOLARIZE1(p_H = 8.0e-4) on every qubit after the layer (the interleaved single-qubit layer).
  prep layer : ancilla prepared noiselessly (Kunlun does not reset; init error is absorbed, SI p.16);
               DEPOLARIZE1(p_H) on every qubit (the opening single-qubit layer).
  meas layer : check outcome flipped with p_M = 4.03e-2 (record flip only); every other qubit gets the
               dynamical-decoupling channel PAULI_CHANNEL_1(p_D^X = 1.09e-2, 0, p_D^Z = 1.59e-2) for the 920 ns readout.
  data       : initialised noiselessly; final readout flipped with p_F = 3.29e-2.
  scale s    : every probability multiplied by s ("kl" = s 1; "kl0.1" = s 0.1, a 10x better device).
Decoder: BP-OSD (stimbposd; IBM parameters: min-sum, 10^4 iterations, OSD-CS order 7), same for all circuits,
built from each circuit's own DEM.  Z and X memories sampled separately (memory-basis detectors only), R rounds.
"""
import argparse
import json
import math
import time

import numpy as np
import stim

from search.experiments.e036.common import OUT, code, load_spec, noiseless
from search.experiments.e036.dcirc import get_spec

KL = dict(p_cz=9.8e-3, p_I=3.5e-3, p_H=8.0e-4, p_M=4.03e-2, p_DX=1.09e-2, p_DZ=1.59e-2, p_F=3.29e-2)
IBM_BPOSD = dict(max_bp_iters=10000, bp_method="min_sum", ms_scaling_factor=0, osd_method="osd_cs", osd_order=7)


def kl_noise(c: stim.Circuit, s: float = 1.0) -> stim.Circuit:
    P = {k: min(v * s, 0.5) for k, v in KL.items()}
    nq = c.num_qubits
    allq = list(range(nq))
    out = stim.Circuit()
    layer = []

    def flush(layer, final=False):
        ops = [op for op in layer if op.name not in ("DETECTOR", "OBSERVABLE_INCLUDE")]
        anns = [op for op in layer if op.name in ("DETECTOR", "OBSERVABLE_INCLUDE")]
        names = {op.name for op in ops}
        has_cx = "CX" in names
        has_m = bool(names & {"M", "MX"})
        used = set()
        for op in ops:
            for t in op.targets_copy():
                if t.is_qubit_target:
                    used.add(t.value)
        for op in ops:
            if op.name in ("M", "MX"):
                qs = [t.value for t in op.targets_copy()]
                pf = P["p_F"] if final else P["p_M"]
                out.append(op.name, qs, pf)
            else:
                out.append(op)
                if op.name == "CX":
                    out.append("DEPOLARIZE2", [t.value for t in op.targets_copy()], P["p_cz"])
        if has_cx:
            idle = [q for q in allq if q not in used]
            if idle:
                out.append("DEPOLARIZE1", idle, P["p_I"])
            out.append("DEPOLARIZE1", allq, P["p_H"])
        elif has_m and not final:
            others = [q for q in allq if q not in used]
            if others:
                out.append("PAULI_CHANNEL_1", others, [P["p_DX"], 0, P["p_DZ"]])
        elif not final:  # prep-only layer
            out.append("DEPOLARIZE1", allq, P["p_H"])
        for a in anns:
            out.append(a)

    ops = list(c.flattened())
    # split at TICK; the last segment (final data readout + detectors) is "final"
    segs = []
    cur = []
    for op in ops:
        if op.name == "TICK":
            segs.append(cur)
            cur = []
        else:
            cur.append(op)
    segs.append(cur)
    for i, sg in enumerate(segs):
        fin = i == len(segs) - 1
        flush(sg, final=fin)
        if not fin:
            out.append("TICK")
    return out


def jeffreys(k, n):
    from scipy.stats import beta
    lo = beta.ppf(0.025, k + 0.5, n - k + 0.5) if k > 0 else 0.0
    hi = beta.ppf(0.975, k + 0.5, n - k + 0.5) if k < n else 1.0
    return lo, hi


def run_one(variant, name, basis, R, shots, scale, seed):
    from stimbposd import BPOSD
    spec = get_spec(variant, name)
    circ = kl_noise(noiseless(spec, variant, basis, R), scale)
    dem = circ.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    dec = BPOSD(dem, **IBM_BPOSD)
    sampler = circ.compile_detector_sampler(seed=seed)
    t0 = time.time()
    fails = 0
    done = 0
    B = 5000
    while done < shots:
        b = min(B, shots - done)
        det, obs = sampler.sample(b, separate_observables=True)
        pred = dec.decode_batch(det)
        fails += int(np.any(pred != obs, axis=1).sum())
        done += b
    lo, hi = jeffreys(fails, done)
    return {"variant": variant, "circuit": name, "basis": basis, "R": R, "scale": scale, "shots": done, "fails": fails,
            "P": fails / done, "lo": lo, "hi": hi, "dem_errors": dem.num_errors, "sec": round(time.time() - t0, 1),
            "seed": seed}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("variant")
    ap.add_argument("circuit")
    ap.add_argument("basis")
    ap.add_argument("--R", type=int, default=6)
    ap.add_argument("--shots", type=int, default=200000)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=20261025)
    a = ap.parse_args()
    r = run_one(a.variant, a.circuit, a.basis, a.R, a.shots, a.scale, a.seed)
    print(json.dumps(r), flush=True)
    with open(OUT / "ler.jsonl", "a") as f:
        f.write(json.dumps(r) + "\n")
