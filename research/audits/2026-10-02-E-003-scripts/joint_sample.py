"""E-003 audit: joint X/Z sampling of Strikis Fig.12 vs IBM, many decoders on the SAME shots.

Usage: uv run python joint_sample.py --tag noisy_p0.005 --boundary noisy --p 0.005 --shots 500 --seed 31 \
           --decoders A,F,B,D --workers 3

1. For each schedule, noiseless Z/X memory circuits (12 rounds) -> evaluators.l2.build_joint_circuit(sd6, boundary).
   Sanity: with boundary='noisy' the per-sector DEM equals the E-003/E-002 per-basis DEM (checked here).
2. Sample `shots` shots (stim seed fixed), save detectors/observables.
3. Decode each sector with each decoder setting (same shots), multiprocessing (<= 3 workers).
Output: results/E-003-audit/<tag>/{shots_<sched>.npz, fails_<sched>_<sector>_<dec>.npy, meta.json}
"""
import argparse
import json
import os
import time
from multiprocessing import get_context

import numpy as np
import scipy.sparse as sp

from common import code_and_scheds, memory, OUT

DECODERS = {
    # A = E-002/E-003 setting (IBM repo): min-sum, 1e4 iters, adaptive scaling, OSD-CS order 7
    "A": ("osd", dict(max_iter=10000, bp_method="minimum_sum", ms_scaling_factor=0, osd_method="osd_cs", osd_order=7)),
    # F = A but higher OSD order (stronger post-processing)
    "F": ("osd", dict(max_iter=10000, bp_method="minimum_sum", ms_scaling_factor=0, osd_method="osd_cs", osd_order=12)),
    # B = short BP (100 iters), otherwise A
    "B": ("osd", dict(max_iter=100, bp_method="minimum_sum", ms_scaling_factor=0, osd_method="osd_cs", osd_order=7)),
    # D = BP+LSD (different post-processor), 100 iters, lsd_cs order 7
    "D": ("lsd", dict(max_iter=100, bp_method="minimum_sum", ms_scaling_factor=0, lsd_method="lsd_cs", lsd_order=7)),
    # G = BP+LSD with long BP and higher order
    "G": ("lsd", dict(max_iter=10000, bp_method="minimum_sum", ms_scaling_factor=0, lsd_method="lsd_cs", lsd_order=10)),
    # P = product-sum BP 1000 iters + OSD-CS 7
    "P": ("osd", dict(max_iter=1000, bp_method="product_sum", osd_method="osd_cs", osd_order=7)),
}


def sector_matrices(model, num_det, num_obs):
    cols = [(d, o, pr) for (d, o), pr in model.items() if d]
    rows, cidx, orows, ocidx = [], [], [], []
    for j, (d, o, _) in enumerate(cols):
        rows.extend(d); cidx.extend([j] * len(d)); orows.extend(o); ocidx.extend([j] * len(o))
    H = sp.csc_matrix((np.ones(len(rows), np.uint8), (rows, cidx)), shape=(num_det, len(cols)))
    L = sp.csr_matrix((np.ones(len(orows), np.uint8), (orows, ocidx)), shape=(num_obs, len(cols)))
    return H, L, np.array([pr for _, _, pr in cols])


def dem_key_set(model):
    return sorted((d, o, round(pr, 12)) for (d, o), pr in model.items() if d or o)


_CACHE = {}


def _work(args):
    d, sched, sec, dec, lo, hi = args
    from ldpc import BpOsdDecoder, BpLsdDecoder
    key = (d, sched, sec, dec)
    if key not in _CACHE:
        z = np.load(os.path.join(d, f"H_{sched}_{sec}.npz"))
        H = sp.csc_matrix((z["data"], z["indices"], z["indptr"]), shape=tuple(z["shape"]))
        Lz = np.load(os.path.join(d, f"L_{sched}_{sec}.npz"))
        L = sp.csr_matrix((Lz["data"], Lz["indices"], Lz["indptr"]), shape=tuple(Lz["shape"]))
        kind, kw = DECODERS[dec]
        cls = BpOsdDecoder if kind == "osd" else BpLsdDecoder
        _CACHE.clear()
        _CACHE[key] = (cls(H, error_channel=list(z["priors"]), **kw), L)
    D, L = _CACHE[key]
    s = np.load(os.path.join(d, f"shots_{sched}.npz"))
    nz = int(s["nz"]); oz = int(s["oz"])
    dets = s["dets"][lo:hi]; obs = s["obs"][lo:hi]
    dets = dets[:, :nz] if sec == "Z" else dets[:, nz:]
    obs = obs[:, :oz] if sec == "Z" else obs[:, oz:]
    t0 = time.process_time()
    fail = np.zeros(hi - lo, bool); conv = np.zeros(hi - lo, bool)
    for i in range(hi - lo):
        if not dets[i].any():
            fail[i] = obs[i].any(); conv[i] = True
            continue
        e = D.decode(dets[i].astype(np.uint8))
        conv[i] = bool(D.converge)
        fail[i] = bool(((L @ e) % 2 != obs[i]).any())
    return key, lo, fail, conv, time.process_time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--boundary", default="noisy")
    ap.add_argument("--p", type=float, default=0.005)
    ap.add_argument("--shots", type=int, default=500)
    ap.add_argument("--seed", type=int, default=31)
    ap.add_argument("--decoders", default="A")
    ap.add_argument("--scheds", default="strikis,ibm")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--chunk", type=int, default=25)
    a = ap.parse_args()
    d = OUT / a.tag
    d.mkdir(parents=True, exist_ok=True)
    from evaluators.codes import CSSCode
    from evaluators.l2 import build_joint_circuit, split_dem
    code, S = code_and_scheds()
    css = CSSCode.from_checks(code.HX, code.HZ)
    meta = json.loads((d / "meta.json").read_text()) if (d / "meta.json").exists() else {}
    meta.update({"boundary": a.boundary, "p": a.p, "seed": a.seed, "noise_model": "sd6", "rounds": 12})
    scheds = a.scheds.split(",")
    for i, name in enumerate(scheds):
        if (d / f"shots_{name}.npz").exists():
            continue
        circ = {b: memory(code, S[name], "strikis", 12, b, 0.0) for b in "ZX"}   # pipelined generator
        J = build_joint_circuit(css, circ, S[name].data, noise_model="sd6", p=a.p, boundary=a.boundary)
        dem = J.circuit.detector_error_model()
        model = split_dem(dem, J.num_detectors_z, J.num_observables_z)
        info = {"joint_info": {k: v for k, v in J.info.items() if isinstance(v, (int, float, str))}}
        for sec, nd, no in (("Z", J.num_detectors_z, J.num_observables_z), ("X", J.num_detectors_x, J.num_observables_x)):
            H, L, pri = sector_matrices(model[sec], nd, no)
            np.savez(d / f"H_{name}_{sec}.npz", data=H.data, indices=H.indices, indptr=H.indptr, shape=H.shape, priors=pri)
            np.savez(d / f"L_{name}_{sec}.npz", data=L.data, indices=L.indices, indptr=L.indptr, shape=L.shape)
            info[f"mechanisms_{sec}"] = H.shape[1]
            if a.boundary == "noisy":
                # sanity: sector DEM == the experiment's per-basis noisy memory DEM
                ref = memory(code, S[name], name, 12, sec, a.p)
                rm = split_dem(ref.detector_error_model(), ref.num_detectors, ref.num_observables)["Z"]
                A_, B_ = dem_key_set(model[sec]), dem_key_set(rm)
                same_keys = [x[:2] for x in A_] == [x[:2] for x in B_]
                maxdiff = max(abs(x[2] - y[2]) for x, y in zip(A_, B_)) if same_keys else None
                info[f"dem_equals_experiment_{sec}"] = {"same_mechanisms": same_keys, "max_prob_diff": maxdiff}
        smp = J.circuit.compile_detector_sampler(seed=a.seed + 1000 * i)
        dets, obs = smp.sample(a.shots, separate_observables=True)
        np.savez_compressed(d / f"shots_{name}.npz", dets=dets, obs=obs, nz=J.num_detectors_z, oz=J.num_observables_z)
        info["stim_seed"] = a.seed + 1000 * i
        meta[name] = info
        print(name, info, flush=True)
        (d / "meta.json").write_text(json.dumps(meta, indent=1, default=str))
    tasks = []
    for dec in a.decoders.split(","):
        for name in scheds:
            for sec in "ZX":
                f = d / f"fails_{name}_{sec}_{dec}.npy"
                if f.exists():
                    continue
                for lo in range(0, a.shots, a.chunk):
                    tasks.append((str(d), name, sec, dec, lo, min(a.shots, lo + a.chunk)))
    acc = {}
    t0 = time.time()
    with get_context("spawn").Pool(a.workers) as pool:
        for key, lo, fail, conv, cpu in pool.imap_unordered(_work, tasks):
            r = acc.setdefault(key, {"fail": {}, "conv": {}, "cpu": 0.0})
            r["fail"][lo] = fail; r["conv"][lo] = conv; r["cpu"] += cpu
            n = sum(len(v) for v in r["fail"].values())
            if n == a.shots:
                _, name, sec, dec = key
                F = np.concatenate([r["fail"][k] for k in sorted(r["fail"])])
                C = np.concatenate([r["conv"][k] for k in sorted(r["conv"])])
                np.save(d / f"fails_{name}_{sec}_{dec}.npy", F)
                np.save(d / f"conv_{name}_{sec}_{dec}.npy", C)
                meta.setdefault("decode", {})[f"{name}_{sec}_{dec}"] = {"fails": int(F.sum()), "shots": a.shots,
                                                                         "bp_converged": int(C.sum()),
                                                                         "cpu_s": round(r["cpu"], 1)}
                (d / "meta.json").write_text(json.dumps(meta, indent=1, default=str))
                print(f"[{time.time()-t0:.0f}s] {name} {sec} {dec}", meta["decode"][f"{name}_{sec}_{dec}"], flush=True)


if __name__ == "__main__":
    main()
