"""E-030 plot: per-round LER (Z+X) vs p, one panel per noise model, both decoders; 95% Jeffreys bars.
  uv run python -m search.experiments.e030.plot"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from search.experiments.e030.common import OUT  # noqa: E402

rows = json.loads((OUT / "direct_summary_R10.json").read_text())["rows"]
models = [m for m in ("lam1", "lam0.3", "lam0.1", "lam0") if any(r["noise"] == m for r in rows)]
col = {"ibm": "#555555", "c11": "#1f6fb4", "c13": "#d08a1a", "c16": "#b03030"}
lab = {"ibm": "IBM depth 8 (d_circ 8)", "c11": "c11 (period 11, d_circ 10)", "c13": "c13 (period 13)",
       "c16": "c16 (period 16)"}
fig, axs = plt.subplots(1, len(models), figsize=(4.2 * len(models), 3.8), squeeze=False)
for ax, m in zip(axs[0], models):
    for c in ("ibm", "c11", "c13", "c16"):
        for dec, ls, mk in (("bposd", "-", "o"), ("relay5", "--", "s")):
            rr = sorted([r for r in rows if r["noise"] == m and r["circ"] == c and r["dec"] == dec
                         and r["Z"]["errors"] < 0.9 * r["Z"]["shots"] and r["eps"] < 0.5], key=lambda r: r["p"])
            if not rr:
                continue
            x = [r["p"] for r in rr]; y = [max(r["eps"], r["lo"]) for r in rr]
            ax.errorbar(x, y, yerr=[[yy - r["lo"] for yy, r in zip(y, rr)], [r["hi"] - yy for yy, r in zip(y, rr)]],
                        color=col[c], ls=ls, marker=mk, ms=3, lw=1, capsize=2,
                        label=f"{lab[c]} {dec}" if m == models[0] else None)
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_title(f"SD6, idle = {m[3:]}·p"); ax.set_xlabel("p")
    ax.grid(alpha=.3, which="both")
axs[0][0].set_ylabel("logical error rate per round (Z+X)")
fig.legend(loc="lower center", ncol=4, fontsize=7, frameon=False)
fig.tight_layout(rect=(0, 0.1, 1, 1))
(OUT / "plots").mkdir(exist_ok=True)
fig.savefig(OUT / "plots" / "ler_vs_p.png", dpi=150)
print("saved")
