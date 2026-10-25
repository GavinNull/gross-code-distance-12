"""Audit claim 6: independent LER spot check.  Own circuit (core.stim_circuit, NO-RESET ancillas like Kunlun),
own mapping of SI Tab. S1 onto it, own DEM -> parity-check conversion, ldpc.BpOsdDecoder called directly.

Noise "kl" (my reading of Tab. S1, arXiv 2505.09684):
  each CNOT (= CZ + H)       : DEPOLARIZE2(9.8e-3)
  each CNOT layer            : DEPOLARIZE1(3.5e-3) on qubits not in a gate; DEPOLARIZE1(8e-4) on every qubit (H layer)
  ancilla H (X checks)       : DEPOLARIZE1(8e-4)
  ancilla measurement layer  : record flip 4.03e-2; PAULI_CHANNEL_1(1.09e-2, 0, 1.59e-2) (DD) on the data qubits
  data readout               : record flip 3.29e-2; no initialisation error
scale s multiplies every probability.
"""
import argparse
import json
import time

import numpy as np
import stim
from scipy.sparse import csc_matrix

from search.experiments.e036_audit.core import checks, kunlun_schedule, schedule_from_json, support
from search.experiments.e036_audit.core import observables

P0 = dict(cz=9.8e-3, idle=3.5e-3, h=8.0e-4, meas=4.03e-2, ddx=1.09e-2, ddz=1.59e-2, ro=3.29e-2)


def kl_circuit(T, S, variant, basis, R, s=1.0):
    P = {k: v * s for k, v in P0.items()}
    ks = checks(variant)
    nd = 18
    anc = {k: nd + i for i, k in enumerate(ks)}
    allq = list(range(nd + len(ks)))
    xa = [anc[k] for k in ks if k[0] == "X"]
    za = [anc[k] for k in ks if k[0] == "Z"]
    c = stim.Circuit()
    c.append("R" if basis == "Z" else "RX", list(range(nd)))
    c.append("R", xa + za)
    c.append("TICK")
    rec = {}
    nm = 0
    for j in range(R):
        c.append("H", xa)
        c.append("DEPOLARIZE1", xa, P["h"])
        c.append("TICK")
        for t in range(1, S + 1):
            used = set()
            pairs = []
            for k in ks:
                for q, tt in zip(support(k), T[k]):
                    if tt == t:
                        pairs += [anc[k], q] if k[0] == "X" else [q, anc[k]]
                        used |= {anc[k], q}
            c.append("CX", pairs)
            c.append("DEPOLARIZE2", pairs, P["cz"])
            rest = [q for q in allq if q not in used]
            if rest:
                c.append("DEPOLARIZE1", rest, P["idle"])
            c.append("DEPOLARIZE1", allq, P["h"])
            c.append("TICK")
        c.append("H", xa)
        c.append("DEPOLARIZE1", xa, P["h"])
        c.append("TICK")
        order = [k for k in ks if k[0] == "X"] + [k for k in ks if k[0] == "Z"]
        c.append("M", [anc[k] for k in order], P["meas"])
        c.append("PAULI_CHANNEL_1", list(range(nd)), [P["ddx"], 0, P["ddz"]])
        for k in order:
            rec[(k, j)] = nm
            nm += 1
        c.append("TICK")
        for k in ks:
            if k[0] != basis:
                continue
            lst = [rec[(k, j)]] + ([rec[(k, j - 2)]] if j >= 2 else [])
            c.append("DETECTOR", [stim.target_rec(x - nm) for x in lst])
    c.append("M" if basis == "Z" else "MX", list(range(nd)), P["ro"])
    dm = {q: nm + q for q in range(nd)}
    nm += nd
    for k in ks:
        if k[0] != basis:
            continue
        lst = [dm[q] for q in support(k)] + [rec[(k, R - 1)]] + ([rec[(k, R - 2)]] if R >= 2 else [])
        c.append("DETECTOR", [stim.target_rec(x - nm) for x in lst])
    for i, v in enumerate(observables(variant, basis)):
        c.append("OBSERVABLE_INCLUDE", [stim.target_rec(dm[q] - nm) for q in np.nonzero(v)[0]], i)
    return c


def dem_matrices(dem):
    cols, pri, obs = [], [], []
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        d, o = [], []
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                d.append(t.val)
            elif t.is_logical_observable_id():
                o.append(t.val)
        cols.append(d)
        obs.append(o)
        pri.append(inst.args_copy()[0])
    n = len(cols)
    rows = [r for c_ in cols for r in c_]
    cc = [i for i, c_ in enumerate(cols) for _ in c_]
    H = csc_matrix((np.ones(len(rows), np.uint8), (rows, cc)), shape=(dem.num_detectors, n))
    rows = [r for c_ in obs for r in c_]
    cc = [i for i, c_ in enumerate(obs) for _ in c_]
    Lm = csc_matrix((np.ones(len(rows), np.uint8), (rows, cc)), shape=(dem.num_observables, n))
    return H, Lm, np.array(pri)


def get(name, variant):
    if name == "kunlun":
        return kunlun_schedule(variant)
    return schedule_from_json(f"search/experiments/e036/{name}_spec.json", variant)


def run(variant, name, basis, R, shots, scale, seed, iters):
    from ldpc import BpOsdDecoder
    T, S = get(name, variant)
    c = kl_circuit(T, S, variant, basis, R, scale)
    dem = c.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    H, Lm, pri = dem_matrices(dem)
    dec = BpOsdDecoder(H, error_channel=list(pri), max_iter=iters, bp_method="minimum_sum", ms_scaling_factor=0,
                       osd_method="osd_cs", osd_order=7)
    det, obs = c.compile_detector_sampler(seed=seed).sample(shots, separate_observables=True)
    Ld = Lm.toarray()
    t0 = time.time()
    fails = 0
    for i in range(shots):
        e = dec.decode(det[i].astype(np.uint8))
        if ((Ld @ e) % 2 != obs[i]).any():
            fails += 1
    return {"variant": variant, "circuit": name, "basis": basis, "R": R, "scale": scale, "shots": shots,
            "fails": fails, "P": fails / shots, "seed": seed, "iters": iters, "sec": round(time.time() - t0, 1)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("variant")
    ap.add_argument("name")
    ap.add_argument("basis")
    ap.add_argument("--R", type=int, default=6)
    ap.add_argument("--shots", type=int, default=100000)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=7261026)
    ap.add_argument("--iters", type=int, default=100)
    a = ap.parse_args()
    r = run(a.variant, a.name, a.basis, a.R, a.shots, a.scale, a.seed, a.iters)
    print(json.dumps(r), flush=True)
    with open("results/E-036-audit/a5_ler.jsonl", "a") as f:
        f.write(json.dumps(r) + "\n")
