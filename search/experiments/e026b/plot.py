"""E-026b plots: per noise model, per-round (left) and per-layer (right) LER vs p, both decoders, 95% Jeffreys bars,
zero-count points as upper-limit triangles; leading-order A6 p^6 lines (lead.json) for p18 / fig12.
  uv run python -m search.experiments.e026b.plot"""
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from search.experiments.e026b.common import OUT, PERIOD

rows = json.loads((OUT / "direct_summary_R12.json").read_text())["rows"]
lead = json.loads((OUT / "lead_summary.json").read_text()) if (OUT / "lead_summary.json").exists() else None
COL = {"p18": "#c0392b", "fig12": "#2471a3", "ibm": "#7f8c8d"}
LBL = {"p18": "p18 (d_circ=12, period 18)", "fig12": "Fig.12 (11, period 8)", "ibm": "IBM (<=10, period 8)"}
MK = {"bposd": "o", "relay5": "s"}
models = [m for m in ("lam0", "lam0.1", "lam0.3", "lam1", "si1000cx") if any(r["noise"] == m for r in rows)]
fig, axs = plt.subplots(len(models), 2, figsize=(12, 4.2 * len(models)), squeeze=False)
for i, m in enumerate(models):
    for k in range(2):
        ax = axs[i][k]
        for c in ("p18", "fig12", "ibm"):
            sc = 1 if k == 0 else 1 / PERIOD[c]
            for dec in ("bposd", "relay5"):
                rr = sorted([r for r in rows if r["noise"] == m and r["circ"] == c and r["dec"] == dec], key=lambda r: r["p"])
                if not rr:
                    continue
                ps = np.array([r["p"] for r in rr]) * (1.03 if dec == "relay5" else 1)
                y = np.array([r["eps"] for r in rr]) * sc
                lo = np.array([r["lo"] for r in rr]) * sc; hi = np.array([r["hi"] for r in rr]) * sc
                ok = y > 0
                ax.errorbar(ps[ok], y[ok], yerr=[y[ok] - lo[ok], hi[ok] - y[ok]], fmt=MK[dec] + ("-" if dec == "bposd" else "--"),
                            color=COL[c], ms=4, capsize=2, mfc="white" if dec == "relay5" else COL[c],
                            label=f"{LBL[c]}, {dec}")
                if (~ok).any():
                    ax.plot(ps[~ok], hi[~ok], "v", color=COL[c], mfc="white", ms=6)
            if lead and m in lead["A6_coef"] and c in lead["A6_coef"][m]:
                pp = np.logspace(-4, np.log10(4e-3), 30)
                ax.plot(pp, lead["A6_coef"][m][c] * pp ** 6 * sc, ":", color=COL[c], lw=1,
                        label=f"{c} ideal A6 p^6 (enumerated families)")
        if m in ("lam1", "lam0.3", "lam0.1", "lam0"):
            pf = np.logspace(-4, np.log10(4e-3), 30)
            ax.plot(pf, pf ** 5 * np.exp(18.04 + 1337 * pf - 96007 * pf ** 2) / (1 if k == 0 else 8), "-", color="k",
                    lw=0.7, alpha=0.4, label="IBM 2308.07915 fit (lambda=1-like)")
        ax.set_xscale("log"); ax.set_yscale("log"); ax.grid(alpha=0.3, which="both")
        ax.set_xlim(8e-4, 4.5e-3); ax.set_ylim(1e-9, 1e-1)
        ax.set_title(f"{m}: " + ("per round" if k == 0 else "per layer"))
        ax.set_xlabel("p"); ax.set_ylabel("LER (Z+X)")
    axs[i][0].legend(fontsize=6, loc="lower right")
fig.tight_layout(); (OUT / "plots").mkdir(exist_ok=True)
fig.savefig(OUT / "plots" / "ler_vs_p_by_model.png", dpi=130)
print("saved")
