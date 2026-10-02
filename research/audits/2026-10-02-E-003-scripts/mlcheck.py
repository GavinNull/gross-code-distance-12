"""Decoder-optimality diagnostic: for every decoding failure, compare the likelihood weight of the decoder's
correction e_hat with that of the TRUE sampled fault set e_true (stim DEM sampler, return_errors=True).

W(e) = sum_j e_j * log((1-p_j)/p_j)   (lower = more likely).
  * W(e_hat) <= W(e_true): the decoder found a solution at least as likely as the truth but in the wrong logical class
    -> a minimum-weight (most-likely-error) decoder would also very likely fail: "intrinsic" failure.
  * W(e_hat) >  W(e_true): the truth itself was a better explanation -> the decoder failed to find it: "decoder" failure.
Same E-002/E-003 decoder setting (A). DEM = the experiments' per-basis noisy memory circuit DEM, columns = DEM
instructions in order (no merging needed: stim already fuses identical mechanisms).

uv run python mlcheck.py --shots 300 --p 0.005 --seed 555 --workers 3
"""
import argparse
import json
import time
from multiprocessing import get_context

import numpy as np
import scipy.sparse as sp

from common import code_and_scheds, memory, OUT

KW = dict(max_iter=10000, bp_method="minimum_sum", ms_scaling_factor=0, osd_method="osd_cs", osd_order=7)


def dem_cols(dem):
    rows, cols, orows, ocols, pri = [], [], [], [], []
    j = 0
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                rows.append(t.val); cols.append(j)
            elif t.is_logical_observable_id():
                orows.append(t.val); ocols.append(j)
        pri.append(inst.args_copy()[0]); j += 1
    H = sp.csc_matrix((np.ones(len(rows), np.uint8), (rows, cols)), shape=(dem.num_detectors, j))
    L = sp.csr_matrix((np.ones(len(orows), np.uint8), (orows, ocols)), shape=(dem.num_observables, j))
    return H, L, np.array(pri)


def run(args):
    name, basis, p, shots, seed = args
    from ldpc import BpOsdDecoder
    code, S = code_and_scheds()
    c = memory(code, S[name], name, 12, basis, p)
    dem = c.detector_error_model()
    H, L, pri = dem_cols(dem)
    H.sum_duplicates()
    # sanity: H/L must reproduce the sampler's detector/observable data
    dets, obs, errs = dem.compile_sampler(seed=seed).sample(shots, return_errors=True)
    assert np.array_equal((errs.astype(np.uint8) @ H.T.toarray()) % 2 == 1, dets)
    w = np.log((1 - pri) / pri)
    dec = BpOsdDecoder(H, error_channel=list(pri), **KW)
    out = {"shots": shots, "fail": 0, "intrinsic": 0, "decoder": 0, "bp_conv": 0, "W_true": [], "W_hat_fail": [],
           "W_true_fail": [], "nfaults": errs.sum(1).tolist()}
    t0 = time.process_time()
    for s in range(shots):
        e = dec.decode(dets[s].astype(np.uint8))
        out["bp_conv"] += bool(dec.converge)
        wt = float(w[errs[s]].sum())
        out["W_true"].append(wt)
        if ((L @ e) % 2 != obs[s]).any():
            wh = float(w[e.astype(bool)].sum())
            out["fail"] += 1
            out["W_hat_fail"].append(wh); out["W_true_fail"].append(wt)
            if wh <= wt + 1e-9:
                out["intrinsic"] += 1
            else:
                out["decoder"] += 1
    out["cpu_s"] = time.process_time() - t0
    return name, basis, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", type=int, default=300)
    ap.add_argument("--p", type=float, default=0.005)
    ap.add_argument("--seed", type=int, default=555)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--split", type=int, default=3, help="split each (sched,basis) into this many seeds")
    a = ap.parse_args()
    per = a.shots // a.split
    tasks = [(n, b, a.p, per, a.seed + 100 * k + (0 if n == "strikis" else 50) + (0 if b == "Z" else 7))
             for k in range(a.split) for n in ("strikis", "ibm") for b in "ZX"]
    res = {}
    with get_context("spawn").Pool(a.workers) as pool:
        for name, basis, out in pool.imap_unordered(run, tasks):
            r = res.setdefault(f"{name}_{basis}", {"shots": 0, "fail": 0, "intrinsic": 0, "decoder": 0, "bp_conv": 0,
                                                   "cpu_s": 0.0, "W_hat_fail": [], "W_true_fail": [], "W_true_mean": []})
            for k in ("shots", "fail", "intrinsic", "decoder", "bp_conv", "cpu_s"):
                r[k] += out[k]
            r["W_hat_fail"] += out["W_hat_fail"]; r["W_true_fail"] += out["W_true_fail"]
            r["W_true_mean"].append(float(np.mean(out["W_true"])))
            print(name, basis, {k: r[k] for k in ("shots", "fail", "intrinsic", "decoder", "bp_conv")},
                  f"cpu {out['cpu_s']:.0f}s", flush=True)
    (OUT / f"mlcheck_p{a.p}.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
