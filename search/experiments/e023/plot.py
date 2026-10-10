"""E-023 plots from results/E-023-ler-benefit/analysis*.json.  experimenter.

    PYTHONPATH=. uv run python -m search.experiments.e023.plot --tag _m54
"""
from __future__ import annotations

import argparse
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from search.experiments.e023.common import D_CIRC, OUT  # noqa: E402

COL = {"bposd": "#1f77b4", "relay": "#d62728", "ideal": "#555555", "pymatching": "#2ca02c"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="")
    a = ap.parse_args(argv)
    A = json.loads((OUT / f"analysis{a.tag}.json").read_text())
    groups = {}
    for key, row in A.items():
        lo, hi, model, dec = key.split("|")
        groups.setdefault((lo, hi, model), {})[dec] = row
    for (lo, hi, model), rows in groups.items():
        fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
        for dec, row in rows.items():
            p = np.array(row["p"])
            c = COL.get(dec, "k")
            ax[0].plot(p, row["ler_lo_dcirc"], "--", color=c, label=f"{lo} (d_circ {D_CIRC.get(lo, '?')}) {dec}")
            ax[0].plot(p, row["ler_hi_dcirc"], "-", color=c, label=f"{hi} (d_circ {D_CIRC.get(hi, '?')}) {dec}")
            ax[0].fill_between(p, *row["ler_lo_95"], color=c, alpha=0.12)
            ax[0].fill_between(p, *row["ler_hi_95"], color=c, alpha=0.12)
            ax[1].plot(p, row["ratio"], "-o", ms=3, color=c, label=dec)
            ax[1].fill_between(p, *row["ratio_95"], color=c, alpha=0.15)
        for x in ax:
            x.set_xscale("log")
            x.set_xlabel("physical error rate p")
            x.grid(alpha=0.3, which="both")
        ax[0].set_yscale("log")
        ax[0].set_ylabel("LER per round (all logicals)")
        ax[0].legend(fontsize=6)
        ax[1].axhline(1, color="k", lw=0.8)
        ax[1].set_yscale("log")
        ax[1].set_ylabel(f"LER({lo}) / LER({hi})")
        ax[1].legend(fontsize=7)
        fig.suptitle(f"E-023  {lo} vs {hi}  [{model}]  (fixed-weight + structural cores; bands 95% bootstrap)")
        fig.tight_layout()
        out = OUT / "plots" / f"ler_{lo}_vs_{hi}_{model}{a.tag}.png"
        out.parent.mkdir(exist_ok=True)
        fig.savefig(out, dpi=140)
        plt.close(fig)
        print(out)


if __name__ == "__main__":
    main()
