"""E-033 ideal (most-likely-error decoder) leading-order comparison, union form (estimate, not a bound).
  ibm  : A5 per round (Z+X) from lead_ibm_W10_ZX_R1-2-3.json (R=2->3 difference; counts saturated from R=1).
  u11  : A6 per round from lead_u11_W12_Z_R1-2.json (R=1->2 difference, Z basis; Z+X taken as 2 x Z unless an X file
         exists -- an assumption, stated in the journal).
  fig12: A6 per round (Z+X) from E-026b lead_summary.json (W11 complete + W12 type (b) only: a lower bound on the
         union-form A6 of Fig. 12).
p*(u11 vs ibm) = A5(ibm) / A6(u11) (ignores ibm's p^6 and u11's p^7 terms; direction of the error not fixed);
u11 vs fig12: both p^6, ratio A6(u11)/A6(fig12) independent of p.
  uv run python -m search.experiments.e033.crossover"""
import json

from search.experiments.e033.common import OUT, ROOT

ibm = json.loads((OUT / "lead_ibm_W10_ZX_R1-2-3.json").read_text())["per_round"]
u = json.loads((OUT / "lead_u11_W12_Z_R1-2.json").read_text())["per_round"]
f12 = {r["model"]: r["A6_fig12"] for r in
       json.loads((ROOT / "results/E-026b-idle-sensitivity/lead_summary.json").read_text())["rows"]}
out = {}
for m in ("lam0", "lam0.1", "lam1"):
    a5 = ibm["Z"][m][-1] + ibm["X"][m][-1]
    a6u = 2 * u["Z"][m][-1]
    out[m] = dict(A5_ibm=a5, A6_u11=a6u, A6_fig12=f12[m], pstar_u11_vs_ibm=a5 / a6u, A6_ratio_u11_over_fig12=a6u / f12[m])
    print(m, {k: f"{v:.3g}" for k, v in out[m].items()})
(OUT / "crossover.json").write_text(json.dumps(out, indent=1))
