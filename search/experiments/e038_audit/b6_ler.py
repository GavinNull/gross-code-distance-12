"""E-038 audit, claim 4: independent LER spot check of N8 vs Kunlun with the E-036 auditor's pipeline (its own no-reset
circuit and its own Tab. S1 mapping, ldpc.BpOsdDecoder min-sum 100 iters OSD-CS 7; nothing from e036/ or e038/
except the N8 json being audited), new seed.
usage: uv run python -m search.experiments.e038_audit.b6_ler {kunlun|n8} {Z|X} SCALE [--shots 100000] [--seed 8261026]"""
import argparse
import json
import time

import numpy as np

from search.experiments.e036_audit.a5_ler import dem_matrices, kl_circuit
from search.experiments.e036_audit.core import kunlun_schedule, schedule_from_json


def run(name, basis, scale, shots, seed, R=6, iters=100):
    from ldpc import BpOsdDecoder
    if name == "kunlun":
        T, S = kunlun_schedule("bb18")
    else:
        T, S = schedule_from_json("search/experiments/e038/bb18_n8_d4_spec.json", "bb18")
    c = kl_circuit(T, S, "bb18", basis, R, scale)
    dem = c.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    H, Lm, pri = dem_matrices(dem)
    dec = BpOsdDecoder(H, error_channel=list(pri), max_iter=iters, bp_method="minimum_sum", ms_scaling_factor=0,
                       osd_method="osd_cs", osd_order=7)
    det, obs = c.compile_detector_sampler(seed=seed).sample(shots, separate_observables=True)
    Ld = Lm.toarray()
    t0 = time.time()
    fails = 0
    for i in range(shots):
        if not det[i].any():
            if obs[i].any():
                fails += 1
            continue
        e = dec.decode(det[i].astype(np.uint8))
        if ((Ld @ e) % 2 != obs[i]).any():
            fails += 1
    return {"circuit": name, "S": S, "basis": basis, "R": R, "scale": scale, "shots": shots, "fails": fails,
            "dem_errors": dem.num_errors, "seed": seed, "sec": round(time.time() - t0, 1)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("basis")
    ap.add_argument("scale", type=float)
    ap.add_argument("--shots", type=int, default=100000)
    ap.add_argument("--seed", type=int, default=8261026)
    a = ap.parse_args()
    r = run(a.name, a.basis, a.scale, a.shots, a.seed)
    print(json.dumps(r), flush=True)
    with open("results/E-038-audit/b6_ler.jsonl", "a") as f:
        f.write(json.dumps(r) + "\n")
