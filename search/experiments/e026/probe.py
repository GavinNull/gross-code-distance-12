"""E-026 stage 0: structural probe (no LER): circuit sizes, idle counts, DEM sizes, column degrees, lambda per round,
determinism.  uv run python -m search.experiments.e026.probe"""
import json, time
import numpy as np
from search.experiments.e026.common import CIRCS, OUT, noiseless, noisy, PERIOD

out = {}
for c in CIRCS:
    for b in "ZX":
        rec = {}
        for R in (6, 12):
            nl = noiseless(c, b, R)
            ops = {"CX": 0, "R": 0, "M": 0}
            for inst in nl.flattened():
                n = len(inst.targets_copy())
                if inst.name == "CX": ops["CX"] += n // 2
                elif inst.name in ("R", "RX"): ops["R"] += n
                elif inst.name in ("M", "MX"): ops["M"] += n
            nc = noisy(c, b, R, 1e-3)
            nidle = sum(len(i.targets_copy()) for i in nc.flattened() if i.name == "DEPOLARIZE1")
            t = time.time()
            dem = nc.detector_error_model(decompose_errors=False)
            nerr = 0; lam = 0.0; deg = []
            for inst in dem.flattened():
                if inst.type != "error": continue
                pr = inst.args_copy()[0]; ts = inst.targets_copy()
                nd = sum(1 for x in ts if x.is_relative_detector_id())
                nerr += 1; lam += pr; deg.append(nd)
            # determinism check
            s = nl.compile_detector_sampler().sample(64)
            rec[R] = dict(layers=nl.num_ticks, ops=ops, idle_locs=nidle, ndet=nl.num_detectors, nobs=nl.num_observables,
                          dem_errors=nerr, lambda_1e3=lam, deg_mean=float(np.mean(deg)), deg_max=int(max(deg)),
                          deterministic=bool(not s.any()), dem_s=round(time.time() - t, 1))
        d = {k: rec[12][k] - rec[6][k] for k in ("layers", "idle_locs", "dem_errors", "lambda_1e3")}
        d["per_round"] = {k: v / 6 for k, v in d.items()}
        rec["bulk_per_round"] = d["per_round"]
        out[f"{c}_{b}"] = rec
        print(c, b, json.dumps(rec), flush=True)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "probe.json").write_text(json.dumps(out, indent=1))
