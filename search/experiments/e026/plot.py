"""E-026 plots: per-round and per-layer LER vs p (direct sampling, 95% intervals), IBM paper fit, optional
leading-order structural curves (lead.json).  uv run python -m search.experiments.e026.plot"""
import json, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from search.experiments.e026.common import OUT, PERIOD

rows = json.loads((OUT / "direct_summary_sd6_R12.json").read_text())["rows"]
st = json.loads((OUT / "structural.json").read_text())["per_round_ZX"] if (OUT / "structural.json").exists() else {}
COL = {"p18": "#c0392b", "fig12": "#2471a3", "ibm": "#7f8c8d"}
LBL = {"p18": "new period-18 (d_circ=12)", "fig12": "SBB Fig. 12 (d_circ=11)", "ibm": "IBM depth-8 (d_circ<=10)"}
MK = {"bposd": "o", "relay5": "s"}
fig, axs = plt.subplots(1, 2, figsize=(12, 5))
for k, ax in enumerate(axs):
    for c in ("p18", "fig12", "ibm"):
        for dec in ("bposd", "relay5"):
            rr = sorted([r for r in rows if r["circ"] == c and r["dec"] == dec], key=lambda r: r["p"])
            if not rr:
                continue
            sc = 1 if k == 0 else 1 / PERIOD[c]
            ps = np.array([r["p"] for r in rr]); y = np.array([r["eps"] for r in rr]) * sc
            lo = np.array([r["lo"] for r in rr]) * sc; hi = np.array([r["hi"] for r in rr]) * sc
            ym = np.where(y > 0, y, np.nan)
            ax.errorbar(ps * (1.02 if dec == "relay5" else 1), ym, yerr=[np.nan_to_num(ym - lo), hi - np.nan_to_num(ym)],
                        fmt=MK[dec] + ("-" if dec == "bposd" else "--"), color=COL[c], ms=5, capsize=2,
                        mfc="white" if dec == "relay5" else COL[c], label=f"{LBL[c]}, {dec}")
            for r in rr:  # zero-count points: plot upper limit
                if r["eps"] == 0:
                    ax.plot([r["p"] * 1.02], [r["hi"] * sc], "v", color=COL[c], mfc="white")
        if st and c in st:
            pp = np.logspace(-4, -3, 20); sc = 1 if k == 0 else 1 / PERIOD[c]
            ax.plot(pp, st[c]["coef_A6_ideal"] * pp ** 6 * sc, ":", color=COL[c], lw=1.2,
                    label=f"{c} ideal leading order A6 p^6 (enumerated families)")
            ax.plot(pp, st[c]["coef_D5_bposd"] * pp ** 5 * sc, "-.", color=COL[c], lw=1.0,
                    label=f"{c} BP-OSD own weight-5 kernel D5 p^5 (one family)")
    pf = np.logspace(-4, math.log10(5e-3), 40)
    fit = pf ** 5 * np.exp(18.04 + 1337 * pf - 96007 * pf ** 2)
    ax.plot(pf, fit / (1 if k == 0 else 8), "-", color="k", lw=0.8, alpha=0.5, label="IBM 2308.07915 Table 6 fit")
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlabel("physical error rate p (SD6 with idle noise)")
    ax.set_ylabel("LER per syndrome round (Z+X)" if k == 0 else "LER per layer (time step)")
    ax.grid(alpha=0.3, which="both")
axs[0].legend(fontsize=7, loc="lower right")
axs[0].set_title("gross [[144,12,12]], R = 12, per round"); axs[1].set_title("per unit time (round / period)")
fig.tight_layout(); (OUT / "plots").mkdir(exist_ok=True)
fig.savefig(OUT / "plots" / "ler_vs_p.png", dpi=150)
print("saved")
