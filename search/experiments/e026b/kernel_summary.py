"""E-026b: practical-decoder leading-order model per noise model and the resulting comparisons.
  D5(dec) per round (Z+X) = sum_b S5_b * weighted failure fraction_b  (kernel/ files; p18 n = 3000 per basis with
          per-sample npz -> bootstrap 95% CI; fig12 n = 600 per basis, json only -> point estimate)
  eps_model(p) = D5 p^5 + A6 p^6     (A6: ideal p^6 coefficient of the enumerated families, lead_summary.json)
  IBM proxy    = C5(lam) p^5         (lead_summary.json; IBM fit scaled by fault mass^5 -- an assumption)
Reports, for each model and decoder, the p-range within [1e-4, 4e-3] where p18 is below fig12 / the IBM proxy, per round
and per layer (p18 / 18 vs others / 8).  Leading-order estimates only.
  uv run python -m search.experiments.e026b.kernel_summary"""
import glob, json
import numpy as np
from search.experiments.e026b.common import OUT, PERIOD

PE = 1e-3
K = OUT / "kernel"
ls = json.loads((OUT / "lead_summary.json").read_text())
lrow = {r["model"]: r for r in ls["rows"]}
rng = np.random.default_rng(5)
D5 = {}
for f in sorted(glob.glob(str(K / "p18_*_s26602_n3000.npz"))):
    nm = f.split("/")[-1]; _, b, m = nm.split("_")[:3]
    d = np.load(f); w = d["w"]; S5 = float(d["S5"])
    for dec in ("bposd", "relay5"):
        fl = d[dec].astype(float)
        pt = S5 * (w * fl).sum() / w.sum()
        idx = rng.integers(len(w), size=(2000, len(w)))
        bs = S5 * (w[idx] * fl[idx]).sum(1) / w[idx].sum(1)
        e = D5.setdefault(("p18", m, dec), {"pt": 0.0, "bs": 0.0, "fails": 0, "n": 0})
        e["pt"] += pt; e["bs"] = e["bs"] + bs; e["fails"] += int(fl.sum()); e["n"] += len(w)
for f in sorted(glob.glob(str(K / "fig12_*.json"))):
    r = json.loads(open(f).read())
    for dec in ("bposd", "relay5"):
        e = D5.setdefault(("fig12", r["model"], dec), {"pt": 0.0, "bs": None, "fails": 0, "n": 0})
        e["pt"] += r["D5_per_round"][dec]; e["fails"] += r["fails"][dec]; e["n"] += r["n"]
out = {}
ps = np.logspace(-4, np.log10(4e-3), 400)


def rng_where(mask):
    if not mask.any():
        return None
    i = np.nonzero(mask)[0]
    return [float(ps[i[0]]), float(ps[i[-1]])]


for (c, m, dec), e in sorted(D5.items()):
    coef = e["pt"] / PE ** 5
    ci = None if e["bs"] is None or isinstance(e["bs"], float) else [float(x) / PE ** 5 for x in np.quantile(e["bs"], [0.025, 0.975])]
    out.setdefault(m, {}).setdefault(dec, {})[c] = {"D5_coef": coef, "D5_coef_ci": ci, "kernel_fails": e["fails"], "kernel_n": e["n"],
                                                    "A6_coef": lrow[m][f"A6_{c}"]}
for m, dd in out.items():
    for dec, cc in dd.items():
        if "p18" not in cc:
            continue
        p18 = cc["p18"]; C5 = lrow[m]["C5_ibm_proxy"]
        f18 = p18["D5_coef"] * ps ** 5 + p18["A6_coef"] * ps ** 6
        res = {"C5_ibm_proxy": C5, "D5_p18_over_C5": p18["D5_coef"] / C5}
        hi = p18["D5_coef_ci"][1] if p18["D5_coef_ci"] else p18["D5_coef"]
        f18hi = hi * ps ** 5 + p18["A6_coef"] * ps ** 6
        ib = C5 * ps ** 5
        res["p18_below_ibm_round"] = rng_where(f18 < ib)
        res["p18_below_ibm_layer"] = rng_where(f18 / PERIOD["p18"] < ib / PERIOD["ibm"])
        res["p18_below_ibm_round_D5_upperCI"] = rng_where(f18hi < ib)
        if "fig12" in cc:
            fg = cc["fig12"]["D5_coef"] * ps ** 5 + cc["fig12"]["A6_coef"] * ps ** 6
            res["p18_below_fig12_round"] = rng_where(f18 < fg)
            res["p18_below_fig12_layer"] = rng_where(f18 / PERIOD["p18"] < fg / PERIOD["fig12"])
            res["p18_below_fig12_round_D5_upperCI"] = rng_where(f18hi < fg)
        cc["compare"] = res
        print(m, dec, json.dumps({k: (v if not isinstance(v, float) else f"{v:.3g}") for k, v in res.items()}),
              "D5 p18 %.3g CI %s" % (p18["D5_coef"], p18["D5_coef_ci"] and [f"{x:.3g}" for x in p18["D5_coef_ci"]]),
              "fig12 D5 %.3g" % cc["fig12"]["D5_coef"] if "fig12" in cc else "")
(OUT / "kernel_summary.json").write_text(json.dumps(out, indent=1))

# lambda_max: largest lambda at which p18 (practical-decoder leading-order model) is below the IBM proxy at p = 1e-4
# (if it is below at 1e-4 it is below on [p_lo, 1e-4] too, since both go as p^5 there).  g < 1 <=> p18 wins at 1e-4.
P0 = 1e-4
lam_max = {}
for dec in ("bposd", "relay5"):
    for unit, fac in (("round", 1.0), ("layer", PERIOD["ibm"] / PERIOD["p18"])):
        pts = []
        for m, dd in out.items():
            if not m.startswith("lam") or dec not in dd or "p18" not in dd[dec]:
                continue
            p18 = dd[dec]["p18"]; C5 = lrow[m]["C5_ibm_proxy"]
            vals = [p18["D5_coef"]] + (p18["D5_coef_ci"] or [p18["D5_coef"]] * 2)
            g = [fac * (v + p18["A6_coef"] * P0) / C5 for v in vals]
            pts.append((float(m[3:]), g))
        pts.sort()
        est = []
        for k in range(3):
            x = None
            for (l1, g1), (l2, g2) in zip(pts, pts[1:]):
                if g1[k] < 1 <= g2[k]:
                    t = np.log(1 / g1[k]) / np.log(g2[k] / g1[k]); x = l1 + t * (l2 - l1); break
            if x is None and all(g[k] < 1 for _, g in pts):
                x = ">1"
            est.append(x)
        lam_max[f"{dec}_{unit}"] = {"point": est[0], "D5_lowCI": est[1], "D5_highCI": est[2],
                                    "g_by_lambda": {l: [round(v, 4) for v in g] for l, g in pts}}
        print("lambda_max vs IBM proxy", dec, unit, est, {l: round(g[0], 3) for l, g in pts})
(OUT / "kernel_summary.json").write_text(json.dumps({"by_model": out, "lambda_max_vs_ibm_proxy_at_1e-4": lam_max}, indent=1))
