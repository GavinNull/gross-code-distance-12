"""E-026b: leading-order summary from lead.json: per model A6 (Z+X, per round, p^6 coefficient), ratio p18/fig12
per round and per layer, lambda* by log-linear interpolation on the grid, and a PROXY comparison with IBM:
ibm per-round ~ C5(lam) p^5 with C5(1) = exp(18.04) (IBM 2308.07915 Table 6 BP-OSD fit; E-026 reproduced it at
lambda = 1 within 0.9-1.2x) and C5(lam) = C5(1) * (mass(lam)/mass(1))^5 (fault-mass scaling, probe.json) -- an
assumption, not a measurement.  p18 beats this proxy for p < C5/A6.
  uv run python -m search.experiments.e026b.lead_summary"""
import json, math
from search.experiments.e026b.common import OUT, PERIOD

lead = json.loads((OUT / "lead.json").read_text())
probe = json.loads((OUT / "probe.json").read_text())["mass"]
PE = 1e-3
models = list(next(iter(lead.values())).keys())
A = {m: {"p18": 0.0, "fig12": 0.0} for m in models}
for fam, d in lead.items():
    c = fam.split("_")[0]
    for m in models:
        A[m][c] += d[m]["A6_per_round_at_PE"] / PE ** 6
ibm_m = {x: probe[f"ibm_lam{x:g}"]["lambda_per_round_1e-3"] for x in (0.0, 0.1, 0.3, 1.0)}


def ibm_mass(lam):
    """DEM prior mass per round is affine in lambda (idle channel enters additively); checked on the 4 probe points."""
    return ibm_m[0.0] + lam * (ibm_m[1.0] - ibm_m[0.0])


for x in (0.1, 0.3):
    assert abs(ibm_mass(x) / ibm_m[x] - 1) < 2e-3, (x, ibm_mass(x), ibm_m[x])
rows = []
for m in models:
    r = A[m]["p18"] / A[m]["fig12"]
    lam = float(m[3:]) if m.startswith("lam") else None
    mass = ibm_mass(lam) if lam is not None else probe["ibm_si1000cx"]["lambda_per_round_1e-3"]
    C5 = math.exp(18.04) * (mass / ibm_m[1.0]) ** 5
    # p18 per round A6 p^6 < C5 p^5  <=>  p < C5/A6 ; per layer: A6 p^6/18 < C5 p^5/8 <=> p < C5*18/(8*A6)
    row = dict(model=m, lam=lam, A6_p18=A[m]["p18"], A6_fig12=A[m]["fig12"], ratio_round=r,
               ratio_layer=r * PERIOD["fig12"] / PERIOD["p18"], C5_ibm_proxy=C5,
               pstar_round_vs_ibm=C5 / A[m]["p18"], pstar_layer_vs_ibm=C5 * PERIOD["p18"] / (PERIOD["ibm"] * A[m]["p18"]))
    rows.append(row)
    print(json.dumps({k: (f"{v:.3g}" if isinstance(v, float) else v) for k, v in row.items()}))


def cross(key):
    g = sorted([r for r in rows if r["lam"] is not None], key=lambda r: r["lam"])
    for a, b in zip(g, g[1:]):
        if (a[key] - 1) * (b[key] - 1) <= 0 and a[key] != b[key]:
            t = (math.log(1) - math.log(a[key])) / (math.log(b[key]) - math.log(a[key]))
            return a["lam"] + t * (b["lam"] - a["lam"])
    return None
for r in rows:
    r["pstar_round_vs_ibm_over_1e-4"] = r["pstar_round_vs_ibm"] / 1e-4
    r["pstar_layer_vs_ibm_over_1e-4"] = r["pstar_layer_vs_ibm"] / 1e-4
x = {"lambda_star_round_vs_fig12": cross("ratio_round"), "lambda_star_layer_vs_fig12": cross("ratio_layer"),
     "lambda_star_round_vs_ibm_proxy_at_1e-4": cross("pstar_round_vs_ibm_over_1e-4"),
     "lambda_star_layer_vs_ibm_proxy_at_1e-4": cross("pstar_layer_vs_ibm_over_1e-4")}
print(x)
(OUT / "lead_summary.json").write_text(json.dumps({"rows": rows, "crossing": x,
    "A6_coef": {m: A[m] for m in ("lam0", "lam0.1", "lam0.3", "lam1", "si1000cx")}}, indent=1))
