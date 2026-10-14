"""E-026: structural (leading-order) summary per round, Z+X summed.
  S_t     = sum over enumerated logicals and t-subsets of prod q (per round, from R differences, PE = 1e-3)
  A6      = ideal (most-likely-error) p^6 coefficient from lead2.json
  D5(dec) = S_5 x (prior-weighted fraction of 5-subsets on which the decoder fails; kernel/ JSON, seeds with weights)
Leading-order only, enumerated families only (W11 complete for fig12; W12 type (b) for p18 and fig12; W12 type (a) and
everything for ibm NOT enumerated) -> estimates, not bounds.   uv run python -m search.experiments.e026.structural"""
import glob, itertools, json
import numpy as np
from search.experiments.e026.common import OUT

PE = 1e-3


def S_t(name, R, t):
    d = np.load(OUT / "lift" / f"{name}_R{R}.npz"); logs, lq = d["logs"], d["logq"]
    comb = np.array(list(itertools.combinations(range(logs.shape[1]), t))); tot = 0.0
    for i in range(0, len(logs), 2000):
        tot += np.exp(lq[logs[i:i + 2000]][:, comb].sum(2)).sum()
    return tot


fam = {"fig12": [("w11", 4, 5)], "p18": [("w11z", 3, 4)]}
lead = json.loads((OUT / "lead2.json").read_text())
kern = {}
for f in glob.glob(str(OUT / "kernel" / "*_s26403.json")):
    r = json.loads(open(f).read())
    if r["t"] != 5:
        continue
    k = kern.setdefault(r["name"], {"wsum": 0.0, "wideal": 0.0, "bposd": 0.0, "relay5": 0.0})
    k["wsum"] += r["wsum"]; k["wideal"] += r["wideal"]
    for nm in ("bposd", "relay5"):
        k[nm] += r["wfail"][nm]
out = {}
for c, fl in fam.items():
    o = {"S5": 0.0, "A6_ideal": 0.0, "D5_bposd": 0.0, "D5_relay5": 0.0, "D5_ideal_at_PE": 0.0}
    for b in "ZX":
        for mode, R1, R2 in fl:
            nm1, nm2 = f"{c}_{b}_{mode}_R{R1}", f"{c}_{b}_{mode}_R{R2}"
            s5 = S_t(f"{c}_{b}_{mode}", R2, 5) - S_t(f"{c}_{b}_{mode}", R1, 5)
            k = kern[nm1]
            o["S5"] += s5
            o["D5_bposd"] += s5 * k["bposd"] / k["wsum"]; o["D5_relay5"] += s5 * k["relay5"] / k["wsum"]
            o["D5_ideal_at_PE"] += s5 * k["wideal"] / k["wsum"]
        for key in ([f"{c}_{b}_w11", f"{c}_{b}_w11z"] if c == "fig12" else [f"{c}_{b}_w11z"]):
            o["A6_ideal"] += lead[key]["per_round"][-1]["A6_per_round_at_PE"]
    o["coef_A6_ideal"] = o["A6_ideal"] / PE ** 6
    for nm in ("bposd", "relay5"):
        o[f"coef_D5_{nm}"] = o[f"D5_{nm}"] / PE ** 5
    out[c] = o
    print(c, json.dumps({k: f"{v:.3e}" for k, v in o.items()}))
# crossovers
ibm_fit_c5 = float(np.exp(18.04))   # IBM 2308.07915 Table 6, BP-OSD, per round, p^5 prefactor at p -> 0
r = out["p18"]["coef_A6_ideal"] / out["fig12"]["coef_A6_ideal"]
x = {"A6_ratio_p18_over_fig12": r,
     "ideal_p18_vs_ibmfit_crossover_p": ibm_fit_c5 / out["p18"]["coef_A6_ideal"],
     "ideal_fig12_vs_ibmfit_crossover_p": ibm_fit_c5 / out["fig12"]["coef_A6_ideal"],
     "D5_bposd_p18_over_ibmfit": out["p18"]["coef_D5_bposd"] / ibm_fit_c5,
     "D5_bposd_fig12_over_ibmfit": out["fig12"]["coef_D5_bposd"] / ibm_fit_c5}
print(json.dumps(x, indent=1))
(OUT / "structural.json").write_text(json.dumps({"per_round_ZX": out, "derived": x}, indent=1))
