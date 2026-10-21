"""E-033 structural probe (no LER): bulk per-round (R=11 minus R=10) DEM column count, prior mass at p=1e-3, idle
locations, noiseless determinism; and lam1 == evaluator sd6 check.  uv run python -m search.experiments.e033.probe"""
import json

from evaluators.noise import add_noise
from search.experiments.e033.common import OUT, noisy, noiseless

res = {}
for c in ("ibm", "fig12", "u11"):
    for b in "ZX":
        nl = noiseless(c, b, 10)
        nl.detector_error_model(allow_gauge_detectors=False)
        assert not nl.compile_detector_sampler().sample(64).any()
        assert str(noisy(c, b, 10, 1e-3, "lam1")) == str(add_noise(nl, "sd6", 1e-3))
    for m in ("lam0", "lam0.1", "lam1"):
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
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "probe.json").write_text(json.dumps(res, indent=1))
