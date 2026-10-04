"""E-006 side probe: how much would a *correlated* (joint X/Z) exact MLE gain over the per-sector MLE reference?

Joint MLE: same MILP on the full joint DEM (all detectors, one column per joint mechanism -- stim already merged
identical joint symptoms), failure = any observable wrong.  Run on the direct-sampling shots of a tag where the
per-sector MLE ran (all D-failure shots + the random subsample), regenerated from the same stim seeds.
Result: per-shot (sector-MLE fail, joint-MLE fail) for these shots and an HT estimate of LER_jointMLE.

uv run python -m search.decoders.joint_probe --tag bb72_p0.003 --max-shots 400 --workers 6
"""
from __future__ import annotations

import argparse
import json
import time
from multiprocessing import get_context

import numpy as np
import scipy.sparse as sp

from search.decoders.common import RESULTS, build_model, sample_dem
from search.decoders.exact import MilpMLE

_M = {}


def joint_matrices(m):
    rows, cols, orows, ocols = [], [], [], []
    no = m.circuit.num_observables
    j = 0
    pri = []
    for inst in m.dem.flattened():
        if inst.type != "error":
            continue
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                rows.append(t.val); cols.append(j)
            elif t.is_logical_observable_id():
                orows.append(t.val); ocols.append(j)
        pri.append(inst.args_copy()[0]); j += 1
    H = sp.csc_matrix((np.ones(len(rows), np.uint8), (rows, cols)), shape=(m.circuit.num_detectors, j))
    L = sp.csr_matrix((np.ones(len(orows), np.uint8), (orows, ocols)), shape=(no, j))
    pri = np.array(pri)
    return H, L, pri


def run(args):
    code, p, rounds, seed, b, bs, idx = args
    key = (code, p)
    t0 = time.process_time()
    if key not in _M:
        m = build_model(code, p, rounds)
        H, L, pri = joint_matrices(m)
        _M.clear()
        _M[key] = (m, H, L, MilpMLE(H, np.log((1 - pri) / pri)))
    m, H, L, dec = _M[key]
    s_seed = int(np.random.SeedSequence([seed, b]).generate_state(1, dtype=np.uint32)[0])
    dets, obs, _ = sample_dem(m, bs, s_seed)
    out = []
    for i in idx:
        d = dets[i].astype(np.uint8)
        if not d.any():
            out.append((b, int(i), bool(obs[i].any()), "OPTIMAL", 0.0))
            continue
        r = dec.decode(d, time_limit=300)
        f = bool(((L @ r.e) % 2 != obs[i]).any()) if r.e is not None else True
        out.append((b, int(i), f, r.status, r.seconds))
    return out, time.process_time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--max-shots", type=int, default=400)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    d = RESULTS / "direct" / a.tag
    args = json.loads((d / "args.json").read_text())
    jobs = []
    meta = {}
    rng = np.random.default_rng(5)
    for f in sorted(d.glob("batch_*.npz")):
        z = np.load(f)
        b = int(f.stem.split("_")[1])
        done = np.flatnonzero(z["ref_done"])
        meta[b] = {"ref_fail": (z["Z_ref_fail"] | z["X_ref_fail"]), "ref_done": z["ref_done"],
                   "sub": float(z["sub"]) if "sub" in z else args["sub"],
                   "sure": np.zeros(len(z["ref_done"]), bool)}
        for n in ("bposd", "relay5"):
            meta[b]["sure"] |= z[f"Z_{n}_fail"] | z[f"X_{n}_fail"]
        jobs.append((args["code"], args["p"], args["rounds"], args["seed"], b, args["batch_size"], done))
    tot = sum(len(j[-1]) for j in jobs)
    if tot > a.max_shots:   # thin uniformly (keeps HT valid: extra inclusion factor)
        keep = a.max_shots / tot
        jobs = [j[:-1] + (j[-1][rng.random(len(j[-1])) < keep],) for j in jobs]
    else:
        keep = 1.0
    res = []
    cpu = 0.0
    with get_context("spawn").Pool(a.workers) as pool:
        for out, c in pool.imap_unordered(run, jobs):
            res += out
            cpu += c
            print(len(res), f"cpu {cpu/3600:.2f}h", flush=True)
    N = sum(len(v["ref_done"]) for v in meta.values())
    ht_joint = ht_sec = 0.0
    both = {"sec_fail_joint_fail": 0, "sec_fail_joint_ok": 0, "sec_ok_joint_fail": 0, "sec_ok_joint_ok": 0}
    for b, i, fj, st, sec_t in res:
        mm = meta[b]
        w = (1.0 if mm["sure"][i] else 1.0 / mm["sub"]) / keep
        fs = bool(mm["ref_fail"][i])
        ht_joint += w * fj
        ht_sec += w * fs
        both[f"sec_{'fail' if fs else 'ok'}_joint_{'fail' if fj else 'ok'}"] += 1
    summ = {"tag": a.tag, "shots_total": N, "solved": len(res), "thinning": keep, "cpu_hours": cpu / 3600,
            "LER_sector_MLE_HT_on_probe": ht_sec / N, "LER_joint_MLE_HT": ht_joint / N, "pairs": both,
            "statuses": {s: sum(1 for r in res if r[3] == s) for s in set(r[3] for r in res)},
            "mean_s": float(np.mean([r[4] for r in res]))}
    print(json.dumps(summ, indent=1))
    (RESULTS / f"joint_probe_{a.tag}.json").write_text(json.dumps({"summary": summ, "rows": res}, indent=1))


if __name__ == "__main__":
    main()
