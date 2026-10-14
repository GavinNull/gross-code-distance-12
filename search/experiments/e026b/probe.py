"""E-026b stage 0 (no LER): validation of the post-processing + per-round fault mass per model.
  1) lam1 output == evaluator sd6 output (exact circuit equality) and rescale_idle(sd6, 1) == sd6 (exact).
  2) lam0 DEM == evaluator uniform_depolarizing(idle=False) DEM (independent route to "no idle"), exact.
  3) per bulk round (R=12 minus R=6, /6) summed DEM prior and number of DEM errors per model at p = 1e-3, split into
     idle and non-idle mass.
  uv run python -m search.experiments.e026b.probe"""
import json
from evaluators.noise import add_noise
from search.experiments.e026b.common import OUT, CIRCS, MODELS, noiseless, noisy, rescale_idle

out = {"checks": {}, "mass": {}}
for c in CIRCS:
    for b in "ZX":
        nl = noiseless(c, b, 4)
        sd6 = add_noise(nl, "sd6", 2e-3)
        ok1 = noisy(c, b, 4, 2e-3, "lam1") == sd6 and rescale_idle(sd6, 1.0) == sd6
        d0 = noisy(c, b, 4, 2e-3, "lam0").detector_error_model(decompose_errors=False)
        d0r = add_noise(nl, "uniform_depolarizing", 2e-3, idle=False).detector_error_model(decompose_errors=False)
        ok2 = d0.approx_equals(d0r, atol=1e-12)
        out["checks"][f"{c}_{b}"] = {"lam1_equals_sd6": bool(ok1), "lam0_dem_equals_noidle": bool(ok2)}
        print(c, b, ok1, ok2, flush=True)
        assert ok1 and ok2
for c in CIRCS:
    for m in MODELS:
        tot = {}
        for R in (6, 12):
            dem = noisy(c, "Z", R, 1e-3, m).detector_error_model(decompose_errors=False)
            lam = sum(i.args_copy()[0] for i in dem.flattened() if i.type == "error")
            n = sum(1 for i in dem.flattened() if i.type == "error")
            tot[R] = (lam, n)
        out["mass"][f"{c}_{m}"] = {"lambda_per_round_1e-3": (tot[12][0] - tot[6][0]) / 6,
                                   "dem_errors_per_round": (tot[12][1] - tot[6][1]) / 6}
        print(c, m, out["mass"][f"{c}_{m}"], flush=True)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "probe.json").write_text(json.dumps(out, indent=1))
