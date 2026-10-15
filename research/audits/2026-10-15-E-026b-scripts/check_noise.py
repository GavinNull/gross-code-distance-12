"""Auditor (E-026b) claim 1: compare the experimenter's post-processed models with the independent builder.
  - merged-column DEM (key -> prior) equality, R = 12, p = 4e-3, lam in {0, 0.1, 0.3, 1}, 3 circuits x 2 bases
  - lam1 text equality with evaluator sd6; lam0 DEM vs evaluator uniform_depolarizing(idle=False)
  - census: number/targets of DEPOLARIZE1 in sd6 output vs idle slots; any 1q gate in template
  - per-round DEM mass at 1e-3 (R12 - R6)/6 for lam in {0, .1, .3, 1}
  - layer composition per period (CX-only layers vs layers containing M/R)
  PYTHONPATH=.:tests uv run python research/audits/2026-10-15-E-026b-scripts/check_noise.py"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mynoise import circuit, build_dem, noiseless, ROOT
from search.experiments.e026b.common import noisy as exp_noisy
from evaluators.noise import add_noise
OUT = ROOT / "results/E-026b-audit"; OUT.mkdir(parents=True, exist_ok=True)
res = {"dem_equal": {}, "text": {}, "census": {}, "mass": {}, "layers": {}}
for c in ("p18", "fig12", "ibm"):
    for b in "ZX":
        nl = noiseless(c, b, 12)
        names = {i.name for i in nl.flattened()}
        sd6 = add_noise(nl, "sd6", 4e-3)
        nd1 = sum(1 for i in sd6.flattened() if i.name == "DEPOLARIZE1")
        nt = sum(len(i.targets_copy()) for i in sd6.flattened() if i.name == "DEPOLARIZE1")
        mine1 = circuit(c, b, 12, 4e-3, 1.0)
        nt_mine = sum(len(i.targets_copy()) for i in mine1.flattened() if i.name == "DEPOLARIZE1")
        res["census"][f"{c}_{b}"] = dict(ops=sorted(names), sd6_D1_instr=nd1, sd6_D1_targets=nt, my_idle_slots=nt_mine)
        res["text"][f"{c}_{b}"] = dict(lam1_eq_sd6=str(exp_noisy(c, b, 12, 4e-3, "lam1")) == str(sd6),
                                       my_lam1_eq_sd6=str(mine1) == str(sd6))
        for lam in (0.0, 0.1, 0.3, 1.0):
            m = "lam%g" % lam
            _, _, _, q1, k1 = build_dem(exp_noisy(c, b, 12, 4e-3, m))
            _, _, _, q2, k2 = build_dem(circuit(c, b, 12, 4e-3, lam))
            same = set(k1) == set(k2)
            md = max(abs(q1[k1[k]] - q2[k2[k]]) / q2[k2[k]] for k in k2) if same else None
            res["dem_equal"][f"{c}_{b}_{m}"] = dict(same_cols=same, ncol=len(k2), max_rel_prior_diff=md)
        _, _, _, q0, k0 = build_dem(add_noise(nl, "uniform_depolarizing", 4e-3, idle=False))
        _, _, _, qm, km = build_dem(circuit(c, b, 12, 4e-3, 0.0))
        res["dem_equal"][f"{c}_{b}_lam0_vs_evaluator_noidle"] = dict(
            same_cols=set(k0) == set(km), max_rel_prior_diff=max(abs(q0[k0[k]] - qm[km[k]]) / qm[km[k]] for k in km))
        print(c, b, res["census"][f"{c}_{b}"], res["text"][f"{c}_{b}"], flush=True)
    for lam in (0.0, 0.1, 0.3, 1.0):
        t = {}
        for R in (6, 12):
            _, _, _, q, _ = build_dem(circuit(c, "Z", R, 1e-3, lam)); t[R] = (q.sum(), len(q))
        res["mass"][f"{c}_lam{lam:g}"] = dict(mass_per_round=(t[12][0] - t[6][0]) / 6, cols_per_round=(t[12][1] - t[6][1]) / 6)
    # layer composition, bulk: R=3 minus R=2
    comp = {}
    for R in (2, 3):
        layers = [[]]
        for i in noiseless(c, "Z", R).flattened():
            if i.name == "TICK": layers.append([])
            elif i.name in ("CX", "R", "RX", "M", "MX"): layers[-1].append(i.name)
        comp[R] = dict(n=len(layers), cx_only=sum(1 for L in layers if L and set(L) == {"CX"}),
                       with_MR=sum(1 for L in layers if set(L) & {"R", "RX", "M", "MX"}))
    res["layers"][c] = {k: comp[3][k] - comp[2][k] for k in comp[3]}
    print(c, res["mass"], res["layers"][c], flush=True)
for k, v in res["dem_equal"].items():
    print(k, v)
(OUT / "check_noise.json").write_text(json.dumps(res, indent=1, default=str))
