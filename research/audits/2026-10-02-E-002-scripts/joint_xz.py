"""E-002 audit: isolate causes of the p=0.006 excess.

Samples X- and Z-sector syndromes from the SAME shots (stim.FlipSimulator with stabilizer
randomization disabled = pure Pauli-frame propagation of the noise, like the IBM code), decodes each
sector with its own DEM using exactly E-002's decoder settings, and reports
  P_Z, P_X (marginals), P_either (true joint failure, the paper's definition), and the
  independence approximation 1-(1-P_Z)(1-P_X) used by E-002.

Variants (--variant):
  e002   : E-002 boundary: noisy data init and noisy data readout for BOTH sectors
           (Z sector == E-002 Z-memory circuit, X sector == E-002 X-memory circuit), 12 noisy cycles.
  paper1 : paper boundary: perfect initial code state, 12 noisy cycles, 1 noiseless closing cycle,
           noiseless readout (arXiv:2308.07915 Sec. 6 "adding one noiseless cycle at the end").

Run: PYTHONPATH=. uv run python research/audits/2026-10-02-E-002-scripts/joint_xz.py \
        --variant paper1 --p 0.006 --shots 320 --workers 3 --seed 2026 --out results/E-002-audit/joint_paper1_p0.006.json
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import time

import numpy as np
import stim

from baselines.bb_code import gross_code
from baselines.circuit import memory_circuit
from baselines.gross import DECODER_KW
from baselines.schedule import ibm_depth8

NOISE = {"DEPOLARIZE1", "DEPOLARIZE2", "X_ERROR", "Z_ERROR", "Y_ERROR"}


def strip_noise(c: stim.Circuit, keep_segment) -> stim.Circuit:
    """Remove noise channels (and measurement flip args) in segments where keep_segment(seg) is False."""
    out = stim.Circuit()
    seg = 0
    for inst in c.flattened():
        if inst.name == "TICK":
            seg += 1
            out.append(inst)
            continue
        if not keep_segment(seg):
            if inst.name in NOISE:
                continue
            if inst.name in ("M", "MX") and inst.gate_args_copy():
                out.append(inst.name, inst.targets_copy())
                continue
        out.append(inst)
    return out


def build(variant: str, basis: str, p: float, rounds: int = 12, detectors="basis"):
    code = gross_code()
    sched = ibm_depth8(code)
    L = code.logical_z() if basis == "Z" else code.logical_x()
    if variant == "e002":
        return memory_circuit(sched, code.HX, code.HZ, L, rounds, basis, p, detectors), code, sched
    if variant == "paper1":
        c = memory_circuit(sched, code.HX, code.HZ, L, rounds + 1, basis, p, detectors)
        last_noisy_seg = 8 * rounds   # segments 1..8*rounds are the noisy cycles; 0 = init layer
        return strip_noise(c, lambda s: 1 <= s <= last_noisy_seg), code, sched
    raise ValueError(variant)


def sampling_circuit(variant, p):
    """Z-basis circuit (no detectors needed) whose noise acts on both sectors as in the variant.
    For 'e002' add Z_ERROR(p) on data right after the initial reset (X-memory prep error) and
    Z_ERROR(p) on data just before the final readout (X-memory readout flip)."""
    c, code, sched = build(variant, "Z", p)
    data = sched.data
    body = stim.Circuit()
    seg = 0
    insts = list(c.flattened())
    # index of final data measurement = last 'M' instruction
    last_m = max(i for i, inst in enumerate(insts) if inst.name == "M")
    for i, inst in enumerate(insts):
        if i == last_m:
            break
        if inst.name in ("DETECTOR", "OBSERVABLE_INCLUDE"):
            continue
        if inst.name == "TICK":
            if seg == 0 and variant == "e002":
                body.append("Z_ERROR", data, p)
            seg += 1
        body.append(inst)
    if variant == "e002":
        body.append("Z_ERROR", data, p)
        body.append("X_ERROR", data, p)   # Z readout flip (E-002 uses M(p); same effect on the frame)
    return body, code, sched


def sample(variant, p, shots, seed):
    body, code, sched = sampling_circuit(variant, p)
    sim = stim.FlipSimulator(batch_size=shots, disable_stabilizer_randomization=True, num_qubits=288, seed=seed)
    sim.do(body)
    mf = sim.get_measurement_flips()          # (num_meas, shots)
    frames = sim.peek_pauli_flips()          # list of PauliString, one per shot
    data = sched.data
    xf = np.zeros((shots, len(data)), dtype=np.uint8)
    zf = np.zeros((shots, len(data)), dtype=np.uint8)
    for s, P in enumerate(frames):
        xm, zm = P.to_numpy()
        xf[s] = xm[data]
        zf[s] = zm[data]
    R = 12 if variant == "e002" else 13
    n2 = 72
    zmeas = np.stack([mf[144 * c: 144 * c + 72] for c in range(R)])          # (R, 72, shots)
    xmeas = np.stack([mf[144 * c + 72: 144 * c + 144] for c in range(R)])
    HX, HZ = code.HX.astype(np.uint8), code.HZ.astype(np.uint8)
    LZ, LX = code.logical_z().astype(np.uint8), code.logical_x().astype(np.uint8)

    def events(meas, H, frame):
        diffs = [meas[0]] + [meas[c] ^ meas[c - 1] for c in range(1, R)]
        final = ((H @ frame.T) % 2).astype(bool) ^ meas[R - 1]
        return np.concatenate(diffs + [final], axis=0).T.astype(np.uint8)   # (shots, R*72+72)

    detZ = events(zmeas, HZ, xf)
    detX = events(xmeas, HX, zf)
    obsZ = ((xf @ LZ.T) % 2).astype(np.uint8)
    obsX = ((zf @ LX.T) % 2).astype(np.uint8)
    return detZ, obsZ, detX, obsX


_DEC = {}


def _init(variant, p):
    import stimbposd
    for b in "ZX":
        c, _, _ = build(variant, b, p)
        _DEC[b] = stimbposd.BPOSD(c.detector_error_model(), **DECODER_KW)


def _decode(args):
    b, dets = args
    t0 = time.process_time()
    pred = _DEC[b].decode_batch(dets)
    return pred, time.process_time() - t0


def selfcheck(variant, p, seed):
    """The manually computed per-sector events must equal what stim computes for the per-sector circuits
    sampled with the same RNG seed (noise draws are identical because noise instructions are identical
    up to the extra Z_ERROR/X_ERROR lines, so instead we check against a DEM-consistency criterion):
    every sampled detector pattern must be explainable, i.e. we compare detector-fire rates."""
    out = {}
    detZ, obsZ, detX, obsX = sample(variant, p, 4096, seed)
    for b, det, obs in (("Z", detZ, obsZ), ("X", detX, obsX)):
        c, _, _ = build(variant, b, p)
        d2, o2 = c.compile_detector_sampler(seed=seed + 1).sample(4096, separate_observables=True)
        out[b] = {"num_det_manual": det.shape[1], "num_det_circuit": c.num_detectors,
                  "mean_fire_manual": float(det.mean()), "mean_fire_circuit": float(d2.mean()),
                  "max_abs_diff_per_detector_rate": float(np.abs(det.mean(0) - d2.mean(0)).max()),
                  "obs_rate_manual": float(obs.any(1).mean()), "obs_rate_circuit": float(o2.any(1).mean())}
    return out


def zero_noise_check(variant):
    """With p=0 everything must be zero (sanity of index bookkeeping)."""
    detZ, obsZ, detX, obsX = sample(variant, 0.0, 64, 1)
    return int(detZ.sum() + obsZ.sum() + detX.sum() + obsX.sum())


def single_fault_check(variant, p, seed, trials=200):
    """Exact check of event bookkeeping: inject ONE random fault (from the stim DEM of each sector,
    via explain), not needed; instead compare against stim detector flips of the per-sector circuit
    driven by the same FlipSimulator noise realisation."""
    res = {}
    for b in "ZX":
        c, code, sched = build(variant, b, p)
        # run the per-sector circuit (with its own DETECTORs) in a FlipSimulator with the same seed;
        # its noise instructions are a subset/superset of the sampling circuit's only for e002 (extra
        # Z_ERROR/X_ERROR lines), so this exact comparison is done for paper1 only.
        if variant != "paper1":
            continue
        sim = stim.FlipSimulator(batch_size=trials, disable_stabilizer_randomization=True, num_qubits=288, seed=seed)
        sim.do(c)
        d_stim = sim.get_detector_flips().T.astype(np.uint8)
        o_stim = sim.get_observable_flips().T.astype(np.uint8)
        detZ, obsZ, detX, obsX = sample(variant, p, trials, seed)
        det, obs = (detZ, obsZ) if b == "Z" else (detX, obsX)
        res[b] = {"det_equal": bool((d_stim == det).all()), "obs_equal": bool((o_stim == obs).all()),
                  "shots_with_events": int(det.any(1).sum()), "shots_with_obs_flip": int(obs.any(1).sum())}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, choices=["e002", "paper1"])
    ap.add_argument("--p", type=float, required=True)
    ap.add_argument("--shots", type=int, required=True)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", required=True)
    ap.add_argument("--check-only", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    rep = {"variant": a.variant, "p": a.p, "shots": a.shots, "seed": a.seed, "decoder": DECODER_KW,
           "zero_noise_sum": zero_noise_check(a.variant),
           "selfcheck_rates": selfcheck(a.variant, a.p, a.seed + 7),
           "exact_check": single_fault_check(a.variant, a.p, a.seed + 9)}
    print(json.dumps(rep, indent=1), flush=True)
    if a.check_only:
        return
    detZ, obsZ, detX, obsX = sample(a.variant, a.p, a.shots, a.seed)
    chunks = []
    step = max(1, a.shots // (a.workers * 6))
    for b, det in (("Z", detZ), ("X", detX)):
        for i in range(0, a.shots, step):
            chunks.append((b, i, det[i:i + step]))
    ctx = mp.get_context("spawn")
    with ctx.Pool(a.workers, initializer=_init, initargs=(a.variant, a.p)) as pool:
        outs = pool.map(_decode, [(b, d) for b, _, d in chunks], chunksize=1)
    predZ = np.zeros_like(obsZ, dtype=bool)
    predX = np.zeros_like(obsX, dtype=bool)
    cpu = 0.0
    for (b, i, d), (pred, sec) in zip(chunks, outs):
        (predZ if b == "Z" else predX)[i:i + len(d)] = pred
        cpu += sec
    failZ = (predZ != obsZ.astype(bool)).any(1)
    failX = (predX != obsX.astype(bool)).any(1)
    N = a.shots
    PZ, PX = failZ.mean(), failX.mean()
    Peither = (failZ | failX).mean()
    Pboth = (failZ & failX).mean()
    per = lambda P: 1 - (1 - P) ** (1 / 12)
    fit = a.p ** 5 * np.exp(18.04 + 1337 * a.p - 96007 * a.p ** 2)
    rep.update({"errors_Z": int(failZ.sum()), "errors_X": int(failX.sum()),
                "errors_either": int((failZ | failX).sum()), "errors_both": int((failZ & failX).sum()),
                "PZ": PZ, "PX": PX, "P_either": Peither, "P_both": Pboth,
                "P_indep_approx": 1 - (1 - PZ) * (1 - PX), "P_both_if_indep": PZ * PX,
                "pL_either": per(Peither), "pL_indep": per(1 - (1 - PZ) * (1 - PX)),
                "paper_fit_pL": fit, "ratio_either_to_fit": per(Peither) / fit,
                "decoder_cpu_s": round(cpu, 1), "wall_s": round(time.time() - t0, 1)})
    # bootstrap CI for ratio of joint to independence estimate and for pL_either
    rng = np.random.default_rng(a.seed)
    bs = []
    for _ in range(2000):
        idx = rng.integers(0, N, N)
        z, x = failZ[idx], failX[idx]
        bs.append((per((z | x).mean()), per(1 - (1 - z.mean()) * (1 - x.mean()))))
    bs = np.array(bs)
    rep["pL_either_boot95"] = np.percentile(bs[:, 0], [2.5, 97.5]).tolist()
    rep["indep_over_joint_boot95"] = np.percentile(bs[:, 1] / bs[:, 0], [2.5, 97.5]).tolist()
    np.savez_compressed(a.out.replace(".json", "_fails.npz"), failZ=failZ, failX=failX)
    json.dump(rep, open(a.out, "w"), indent=1, default=float)
    print(json.dumps({k: v for k, v in rep.items() if k not in ("selfcheck_rates",)}, indent=1, default=float))


if __name__ == "__main__":
    main()
