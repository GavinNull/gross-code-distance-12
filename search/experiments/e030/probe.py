"""E-030 structural probe: per-round (bulk, R=11 minus R=10) DEM column count, prior mass, idle locations per round,
noiseless determinism, for each circuit and noise model.  uv run python -m search.experiments.e030.probe"""
import json

from search.experiments.e030.common import OUT, PERIOD, noisy, noiseless

res = {}
for c in ("ibm", "c11", "c12", "c13", "c16"):
    for b in "ZX":
        noiseless(c, b, 10).detector_error_model(allow_gauge_detectors=False)
    for m in ("lam0", "lam0.1", "lam0.3", "lam1"):
        row = {}
        for b in "ZX":
            vals = []
            for R in (10, 11):
                circ = noisy(c, b, R, 1e-3, m)
                dem = circ.detector_error_model(decompose_errors=False)
                ps = [i.args_copy()[0] for i in dem.flattened() if i.type == "error"]
                idle = sum(len(i.targets_copy()) for i in circ.flattened() if i.name == "DEPOLARIZE1")
                vals.append((len(ps), sum(ps), idle))
            row[b] = {"cols_per_round": vals[1][0] - vals[0][0], "mass_per_round": round(vals[1][1] - vals[0][1], 4),
                      "idle_locs_per_round": vals[1][2] - vals[0][2]}
        res[f"{c}_{m}"] = row
        print(c, m, row, flush=True)
(OUT / "probe.json").write_text(json.dumps(res, indent=1))
