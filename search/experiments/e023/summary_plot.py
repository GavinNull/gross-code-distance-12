"""E-023 summary figure: LER ratio (lower-d_circ circuit / higher-d_circ circuit) vs p for every pair, noise model and
decoder estimate, from the analysis_*.json files.  experimenter."""
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from search.experiments.e023.common import OUT  # noqa: E402

PANELS = [
    ("sc5 d=5 surface: bad (3) / good (5)  [SD6, positive control]", [("_sc5_sd6", "pymatching", "MWPM"), ("_sc5_sd6", "ideal", "ideal (MLE lb)")]),
    ("[[54]] morphing: paper (6) / repo (7)  [SD6, time-bulk]", [("_m54_sd6_bulkMC", "bposd", "BP-OSD"), ("_m54_sd6_bulkMC", "relay", "Relay-BP"), ("_m54_sd6_bulkMC", "ideal", "ideal (MLE lb)")]),
    ("[[54]] morphing: paper (6) / repo (7)  [SI1000, time-bulk]", [("_m54_si1000_bulkMC", "bposd", "BP-OSD"), ("_m54_si1000_bulkMC", "relay", "Relay-BP"), ("_m54_si1000_bulkMC", "ideal", "ideal (MLE lb)")]),
    ("BB108: IBM (8) / two-colour (10)  [SD6]", [("_bb108_sd6_fit", "bposd_fit", "BP-OSD (cores+MC fit)"), ("_bb108_sd6_fit", "relay_fit", "Relay-BP (cores+MC fit)"), ("_bb108_sd6_struct", "bposd_struct", "BP-OSD cores only"), ("_bb108_sd6_struct", "ideal", "ideal (MLE lb)")]),
    ("BB108: IBM (8) / two-colour (10)  [SI1000, cores only]", [("_bb108_si1000_struct", "bposd_struct", "BP-OSD cores only"), ("_bb108_si1000_struct", "relay_struct", "Relay-BP cores only"), ("_bb108_si1000_struct", "ideal", "ideal (MLE lb)")]),
    ("[[144]]->[[72]] morphing f_y: sw11 (6) / sw01 (7)  [SD6]", [("_m72_sd6_ideal", "ideal", "ideal (MLE lb)")]),
]
COL = {"BP-OSD": "#1f77b4", "Relay-BP": "#d62728", "MWPM": "#2ca02c", "ideal (MLE lb)": "#444444",
       "BP-OSD (cores+MC fit)": "#1f77b4", "Relay-BP (cores+MC fit)": "#d62728", "BP-OSD cores only": "#6baed6",
       "Relay-BP cores only": "#fc9272"}

fig, axs = plt.subplots(2, 3, figsize=(15, 8.5))
for ax, (title, items) in zip(axs.ravel(), PANELS):
    for tag, dec, lab in items:
        A = json.loads((OUT / f"analysis{tag}.json").read_text())
        row = [v for k, v in A.items() if k.endswith("|" + dec)][0]
        p = np.array(row["p"])
        m = p <= 1e-3 + 1e-12 if "ideal" in dec or "struct" in dec else p > 0
        ls = "--" if ("struct" in dec or "ideal" in dec) else "-"
        ax.plot(p[m], np.array(row["ratio"])[m], ls, marker="o", ms=3, color=COL[lab], label=lab)
        lo, hi = np.array(row["ratio_95"][0]), np.array(row["ratio_95"][1])
        if not np.allclose(lo, hi):
            ax.fill_between(p[m], lo[m], hi[m], color=COL[lab], alpha=0.13)
    ax.axhline(1, color="k", lw=0.8)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_ylim(0.03, 300)
    ax.set_title(title, fontsize=9)
    ax.set_xlabel("p"); ax.set_ylabel("LER ratio (low d_circ / high d_circ), per round")
    ax.grid(alpha=0.3, which="both")
    ax.legend(fontsize=7)
fig.suptitle("E-023: does +1 (or +2) proven d_circ buy a lower LER?  ratio > 1 = higher-d_circ circuit wins; bands = 95%", fontsize=11)
fig.tight_layout()
out = OUT / "plots" / "summary_ratios.png"
fig.savefig(out, dpi=140)
print(out)
