"""Auditor (E-026b) claim 3: re-derive A6 totals, ratios, lambda* (log-linear and polynomial-in-lambda interpolation)
from lead.json, sensitivity of lambda* to an unknown multiplicative factor F = (1 + a18)/(1 + a12) from the missing
type-(a) weight-12 families, and the IBM-proxy arithmetic (C5 scaling) from probe.json.
  uv run python research/audits/2026-10-15-E-026b-scripts/lead_check.py"""
import json, math
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[3]
D = ROOT / "results/E-026b-idle-sensitivity"
L = json.loads((D / "lead.json").read_text())
lams = sorted(float(m[3:]) for m in next(iter(L.values())) if m.startswith("lam"))
A = {c: np.array([sum(v["lam%g" % x]["A6_per_round_at_PE"] for f, v in L.items() if f.startswith(c)) / 1e-18
                  for x in lams]) for c in ("p18", "fig12")}
r = A["p18"] / A["fig12"]; lams = np.array(lams)
def cross(rr, target=1.0):
    for i in range(len(lams) - 1):
        if (rr[i] - target) * (rr[i + 1] - target) <= 0:
            t = math.log(target / rr[i]) / math.log(rr[i + 1] / rr[i]); return lams[i] + t * (lams[i + 1] - lams[i])
    return None
res = {"lams": lams.tolist(), "A6_p18": A["p18"].tolist(), "A6_fig12": A["fig12"].tolist(), "ratio": r.tolist(),
       "lambda_star_loglin": cross(r), "lambda_star_layer_loglin": cross(r * 8 / 18)}
# polynomial (deg 6 in lambda) fit of each A6 on the grid, exact root of ratio = 1
pf = {c: np.polynomial.Polynomial.fit(lams, A[c], 6) for c in A}
xs = np.linspace(0, 1, 100001); rr = pf["p18"](xs) / pf["fig12"](xs)
res["poly_fit_max_rel_resid"] = {c: float(np.max(np.abs(pf[c](lams) / A[c] - 1))) for c in A}
res["lambda_star_poly"] = float(xs[np.argmax(rr >= 1)])
res["lambda_star_layer_poly"] = float(xs[np.argmax(rr * 8 / 18 >= 1)])
# sensitivity: true ratio = F * enumerated ratio
res["sensitivity_F"] = {F: float(xs[np.argmax(F * rr >= 1)]) if (F * rr >= 1).any() else ">1" for F in (0.1, 0.3, 0.5, 2, 3, 10, 30, 100)}
# how large must the type-(a) A6 of p18 be (if fig12's were 0) to move lambda* below 0.1 / to make p18 lose at lambda=0
i01 = list(lams).index(0.1); i0 = 0
res["A6a_p18_needed_lose_at_lam0.1"] = float(A["fig12"][i01] - A["p18"][i01])
res["A6a_p18_needed_lose_at_lam0"] = float(A["fig12"][i0] - A["p18"][i0])
res["fold_over_enumerated_p18_lam0.1"] = res["A6a_p18_needed_lose_at_lam0.1"] / float(A["p18"][i01])
res["fold_over_enumerated_p18_lam0"] = res["A6a_p18_needed_lose_at_lam0"] / float(A["p18"][i0])
# IBM proxy: C5(lam) = e^18.04 (mass(lam)/mass(1))^5, own masses from check_noise.json
cn = json.loads((ROOT / "results/E-026b-audit/check_noise.json").read_text())["mass"]
m1 = cn["ibm_lam1"]["mass_per_round"]
res["C5_proxy"] = {x: math.exp(18.04) * (cn["ibm_lam%g" % x]["mass_per_round"] / m1) ** 5 for x in (0, 0.1, 0.3, 1)}
print(json.dumps(res, indent=1))
(ROOT / "results/E-026b-audit/lead_check.json").write_text(json.dumps(res, indent=1, default=str))
