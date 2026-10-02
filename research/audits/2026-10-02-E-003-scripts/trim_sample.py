"""Item 3: sample the boundary-equalised (trimmed) per-basis circuits, decode with E-002 setting A.
Reuses joint_sample._work; each (schedule, basis) circuit is stored as a pseudo-schedule '<sched><basis>' with a
single sector 'Z' = the whole circuit.

uv run python trim_sample.py --tag trim_p0.005 --p 0.005 --shots 400 --seed 77 --decoders A --workers 3
"""
import argparse
import json
import time
from multiprocessing import get_context

import numpy as np

from common import code_and_scheds, memory, dem_matrices, OUT
from joint_sample import _work
from trim import trim


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--p", type=float, default=0.005)
    ap.add_argument("--shots", type=int, default=400)
    ap.add_argument("--seed", type=int, default=77)
    ap.add_argument("--decoders", default="A")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--chunk", type=int, default=20)
    a = ap.parse_args()
    d = OUT / a.tag
    d.mkdir(parents=True, exist_ok=True)
    code, S = code_and_scheds()
    meta = json.loads((d / "meta.json").read_text()) if (d / "meta.json").exists() else {}
    names = []
    for i, (name, sched) in enumerate(S.items()):
        for j, b in enumerate("ZX"):
            nm = f"{name}{b}"
            names.append(nm)
            if (d / f"shots_{nm}.npz").exists():
                continue
            c, removed = trim(memory(code, sched, name, 12, b, a.p), sched.data)
            H, L, pri = dem_matrices(c)
            H = H.tocsc()
            np.savez(d / f"H_{nm}_Z.npz", data=H.data, indices=H.indices, indptr=H.indptr, shape=H.shape, priors=pri)
            L = L.tocsr()
            np.savez(d / f"L_{nm}_Z.npz", data=L.data, indices=L.indices, indptr=L.indptr, shape=L.shape)
            seed = a.seed + 10 * i + j
            dets, obs = c.compile_detector_sampler(seed=seed).sample(a.shots, separate_observables=True)
            np.savez_compressed(d / f"shots_{nm}.npz", dets=dets, obs=obs, nz=c.num_detectors, oz=c.num_observables)
            meta[nm] = {"removed": removed, "stim_seed": seed, "p": a.p}
            (d / "meta.json").write_text(json.dumps(meta, indent=1))
    tasks = [(str(d), nm, "Z", dec, lo, min(a.shots, lo + a.chunk)) for dec in a.decoders.split(",")
             for nm in names if not (d / f"fails_{nm}_Z_{dec}.npy").exists() for lo in range(0, a.shots, a.chunk)]
    acc = {}
    t0 = time.time()
    with get_context("spawn").Pool(a.workers) as pool:
        for key, lo, fail, conv, cpu in pool.imap_unordered(_work, tasks):
            r = acc.setdefault(key, {"fail": {}, "conv": {}, "cpu": 0.0})
            r["fail"][lo] = fail; r["conv"][lo] = conv; r["cpu"] += cpu
            if sum(len(v) for v in r["fail"].values()) == a.shots:
                _, nm, sec, dec = key
                F = np.concatenate([r["fail"][k] for k in sorted(r["fail"])])
                np.save(d / f"fails_{nm}_Z_{dec}.npy", F)
                meta.setdefault("decode", {})[f"{nm}_{dec}"] = {"fails": int(F.sum()), "shots": a.shots,
                                                                 "cpu_s": round(r["cpu"], 1)}
                (d / "meta.json").write_text(json.dumps(meta, indent=1))
                print(f"[{time.time()-t0:.0f}s] {nm} {dec}", meta["decode"][f"{nm}_{dec}"], flush=True)


if __name__ == "__main__":
    main()
