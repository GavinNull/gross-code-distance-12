"""Shared style and helpers for paper/scripts/fig*.py (PRL single-column figures).

Palette: Okabe-Ito subset (colour-blind safe; validated with the dataviz palette checker,
CVD separation in the 6-8 band, so every figure also uses a secondary encoding: text labels
or marker shapes). Nothing in this module carries data.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "paper" / "figures"
COLW = 3.4  # PRL single column, inches

BLUE = "#0072B2"
ORANGE = "#E69F00"
GREEN = "#009E73"
PURPLE = "#CC79A7"
VERMILION = "#D55E00"
GREY = "#6b6b6b"
INK = "#1a1a1a"


def style() -> None:
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["STIXGeneral", "Times New Roman", "DejaVu Serif"],
        "mathtext.fontset": "stix",
        "font.size": 7.5,
        "axes.labelsize": 7.5,
        "axes.titlesize": 7.5,
        "xtick.labelsize": 6.5,
        "ytick.labelsize": 6.5,
        "legend.fontsize": 6.5,
        "axes.linewidth": 0.6,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "xtick.major.size": 2.5,
        "ytick.major.size": 2.5,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02,
    })


def load(rel: str):
    p = ROOT / rel
    if not p.exists():
        raise SystemExit(f"MISSING DATA FILE: {rel} (results/ is not in git; needs the data archive)")
    return json.loads(p.read_text())


def check(cond: bool, msg: str) -> None:
    """Fail loudly: a mismatch against the audited numbers aborts the figure."""
    if not cond:
        raise SystemExit(f"AUDIT MISMATCH: {msg}")


def save(fig, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.pdf")
    fig.savefig(OUT / f"{name}.png", dpi=300)
    print(f"wrote {OUT / name}.pdf / .png")
