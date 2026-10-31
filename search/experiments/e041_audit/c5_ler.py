"""c5: independent LER spot check.  My own noiseless circuit (core.circuit, reset ancillas, R = 6) + my own
implementation of the Tab. S1 layer mapping (arXiv 2505.09684 SI Tab. S1 values as recorded in E-036's journal):
  p_cz 9.8e-3 (DEPOLARIZE2 on CX pairs), p_I 3.5e-3 (idle in a CZ slot), p_H 8.0e-4 (single-qubit gate layer, all
  qubits, in every CZ layer and in a prep-only layer), p_M 4.03e-2 (ancilla readout flip), DD during a readout
  window: X 1.09e-2 / Z 1.59e-2 on every qubit not used in that layer, p_F 3.29e-2 (final data readout).  No init error.
Mapping 'kl'   : a layer with a CX is a CZ slot (even if it also contains measurements).
Mapping 'mix'  : a layer with a CX AND a measurement is ALSO a readout window: every qubit not measured in it gets DD
                 in addition to the CZ-slot channels (no p_I).  (Conservative: two sequential readout windows/cycle.)
Decoder: stimbposd BPOSD (min-sum, 100 iters, scaling 0, OSD-CS order 7), as E-036.  Fresh seeds.
usage: uv run python -m search.experiments.e041_audit.c5_ler <circuit kunlun|w9> <basis> <scale> <kl|mix> <shots> <seed>"""
import json
import sys
import time

import numpy as np
import stim

from search.experiments.e041_audit import core as C

TAB = dict(cz=9.8e-3, I=3.5e-3, H=8.0e-4, M=4.03e-2, DX=1.09e-2, DZ=1.59e-2, F=3.29e-2)
SPECS = {"w9": "search/experiments/e041/bb18_w9_d4_spec.json", "kunlun": "results/E-041-audit/kunlun_spec.json",
         "n8": "search/experiments/e038/bb18_n8_d4_spec.json"}


def apply(c0, scale, mapping):
    P = {k: min(v * scale, 0.5) for k, v in TAB.items()}
    nq = c0.num_qubits
    segs, cur = [], []
    for op in c0:
        if isinstance(op, stim.CircuitRepeatBlock):
            raise ValueError
        if op.name == "TICK":
            segs.append(cur)
            cur = []
        else:
            cur.append(op)
    segs.append(cur)
    out = stim.Circuit()
    nmix = 0
    for i, seg in enumerate(segs):
        final = i == len(segs) - 1
        gates = [op for op in seg if op.name not in ("DETECTOR", "OBSERVABLE_INCLUDE")]
        names = {op.name for op in gates}
        used, measured = set(), set()
        for op in gates:
            qs = [t.value for t in op.targets_copy() if t.is_qubit_target]
            used |= set(qs)
            if op.name in ("M", "MX"):
                measured |= set(qs)
        cx, ms = "CX" in names, bool(names & {"M", "MX"})
        for op in seg:
            if op.name in ("M", "MX"):
                out.append(op.name, [t.value for t in op.targets_copy()], P["F"] if final else P["M"])
            elif op.name in ("X_ERROR", "Z_ERROR", "DEPOLARIZE1", "DEPOLARIZE2"):
                continue
            else:
                out.append(op)
                if op.name == "CX":
                    out.append("DEPOLARIZE2", [t.value for t in op.targets_copy()], P["cz"])
        if final:
            continue
        if cx and ms and mapping == "mix":
            nmix += 1
            others = [q for q in range(nq) if q not in measured]
            out.append("PAULI_CHANNEL_1", others, [P["DX"], 0, P["DZ"]])
            out.append("DEPOLARIZE1", list(range(nq)), P["H"])
        elif cx:
            idle = [q for q in range(nq) if q not in used]
            if idle:
                out.append("DEPOLARIZE1", idle, P["I"])
            out.append("DEPOLARIZE1", list(range(nq)), P["H"])
        elif ms:
            others = [q for q in range(nq) if q not in used]
            if others:
                out.append("PAULI_CHANNEL_1", others, [P["DX"], 0, P["DZ"]])
        else:
            out.append("DEPOLARIZE1", list(range(nq)), P["H"])
        out.append("TICK")
    return out, nmix


def jeffreys(k, n):
    from scipy.stats import beta
    return (beta.ppf(0.025, k + 0.5, n - k + 0.5) if k else 0.0, beta.ppf(0.975, k + 0.5, n - k + 0.5))


def main():
    name, basis, scale, mapping, shots, seed = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4], \
        int(sys.argv[5]), int(sys.argv[6])
    from stimbposd import BPOSD
    S = C.load(SPECS[name])
    R = 6
    c0, _ = C.circuit(S, basis, R, p=0.0, reset=True)
    c, nmix = apply(c0, scale, mapping)
    dem = c.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    dec = BPOSD(dem, max_bp_iters=100, bp_method="min_sum", ms_scaling_factor=0, osd_method="osd_cs", osd_order=7)
    smp = c.compile_detector_sampler(seed=seed)
    t0 = time.time()
    fails = done = 0
    while done < shots:
        b = min(5000, shots - done)
        det, obs = smp.sample(b, separate_observables=True)
        fails += int(np.any(dec.decode_batch(det) != obs, axis=1).sum())
        done += b
    lo, hi = jeffreys(fails, done)
    r = dict(circuit=name, basis=basis, scale=scale, mapping=mapping, R=R, shots=done, fails=fails, P=fails / done,
             lo=lo, hi=hi, mixed_layers=nmix, dem_errors=dem.num_errors, seed=seed, sec=round(time.time() - t0, 1))
    print(json.dumps(r), flush=True)
    with open("results/E-041-audit/c5_ler.jsonl", "a") as f:
        f.write(json.dumps(r) + "\n")


if __name__ == "__main__":
    main()
