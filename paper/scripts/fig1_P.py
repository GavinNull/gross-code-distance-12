"""Fig. 1 of revision P (conceptual): (a) round-offset cochains delta(A_i, B_j) of three gross-code circuits,
(b) the two-hook negative cycle on a weight-10 extended logical of the period-11 circuit, (c) the pair obstruction.

Data: paper/figures/fig1_P_data.json (fig1_P_data.py). Panel (c) is a schematic and carries no data.
Usage (repository root):  uv run python paper/scripts/fig1_P.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

from fig_common import BLUE, GREY, INK, ORANGE, VERMILION, check, load, save, style  # noqa: E402

LIGHT = "#eef3f8"
TINT = {0: "#f2f2f2", 1: "#cfe3f1", -1: "#f6dcc4", 2: "#9cc7e4"}


def panel_a(ax, d):
    ax.set_xlim(0, 3 * 4.3)
    ax.set_ylim(-2.4, 5.2)
    ax.set_aspect("equal")
    ax.axis("off")
    names = [("ibmg", "IBM depth 8"), ("g10", r"$g_{10}$"), ("u11", r"$u_{11}$")]
    for n, (key, lab) in enumerate(names):
        x0 = 0.9 + 4.3 * n
        M = d["delta"][key]
        for i in range(3):
            for j in range(3):
                v = M[i][j]
                ax.add_patch(Rectangle((x0 + j, 2 - i), 0.92, 0.92, fc=TINT.get(v, LIGHT), ec="white", lw=0.8))
                ax.text(x0 + j + 0.46, 2 - i + 0.46, f"{v:d}".replace("-", "−"), ha="center", va="center",
                        fontsize=7, color=INK)
        for j in range(3):
            ax.text(x0 + j + 0.46, 3.15, f"$B_{j + 1}$", ha="center", va="bottom", fontsize=6.3, color=GREY)
        for i in range(3):
            ax.text(x0 - 0.12, 2 - i + 0.46, f"$A_{i + 1}$", ha="right", va="center", fontsize=6.3, color=GREY)
        ax.text(x0 + 1.4, 3.85, lab, ha="center", va="bottom", fontsize=7.2, color=INK)
        ax.text(x0 + 1.4, -0.45, f"$P={d['period'][key]}$, $d_{{\\rm circ}}={d['dcirc'][key]}$",
                ha="center", va="top", fontsize=6.5, color=INK)
    ax.text(0.0, -1.35, r"coboundary $\Leftrightarrow$ all nine entries equal", fontsize=6.3, color=GREY,
            ha="left", va="center")


def panel_b(ax, d):
    ex = d["example_u11_Z_list0"]
    f, g = ex["hook_f"][0], ex["hook_g"][0]
    z1, z2 = ex["readers"]
    idx = {(e["x"], e["z"]): e for e in ex["edges"]}
    ax.set_xlim(-0.2, 6.2)
    ax.set_ylim(-1.75, 5.2)
    ax.set_aspect("equal")
    ax.axis("off")
    # strip: the ten columns of the extended logical
    xs = [0.35 + 0.6 * k for k in range(10)]
    for k, c in enumerate(ex["columns"]):
        x = xs[k]
        if c["data_qubits"]:
            ax.plot([x], [4.0], "o", ms=3.6, color=GREY, mec="white", mew=0.4)
        else:
            ch, ln = c["hooks"][0]
            hot = ch in (f, g)
            ax.add_patch(Rectangle((x - 0.08, 4.0 - 0.09 * ln), 0.16, 0.18 * ln,
                                   fc=VERMILION if hot else GREY, ec="none"))
            ax.text(x, 4.0 - 0.09 * ln - 0.12, f"$X_{{{ch}}}$", ha="center", va="top", fontsize=5.6,
                    color=INK if hot else GREY)
    ax.text(3.0, 4.55, "weight-10 extended logical: 6 data columns, 4 hooks", ha="center", va="bottom",
            fontsize=6.3, color=GREY)
    # the 4-cycle
    P = {f: (1.0, 1.0), g: (5.0, 1.0), z1: (3.0, 2.3), z2: (3.0, -0.3)}
    for (x, z), e in idx.items():
        (xa, ya), (xb, yb) = P[x], P[z]
        ax.plot([xa, xb], [ya, yb], color=INK, lw=0.9, zorder=1)
        mx, my = (xa + xb) / 2, (ya + yb) / 2
        lab = f"{e['index']:d}".replace("-", "−")
        ax.text(mx, my, lab, ha="center", va="center", fontsize=7, color=INK,
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none"))
        ti, tj = e["term_pair"]
        ax.text(mx + (0.0 if True else 0), my + (0.33 if my > 1 else -0.33),
                f"$({ti[0]}_{ti[1]},{tj[0]}_{tj[1]})$", ha="center", va="center", fontsize=5.2, color=GREY)
    for x in (f, g):
        ax.add_patch(FancyBboxPatch((P[x][0] - 0.42, P[x][1] - 0.28), 0.84, 0.56, boxstyle="round,pad=0.02",
                                    fc=VERMILION, ec="none", zorder=2))
        ax.text(*P[x], f"$X_{{{x}}}$", ha="center", va="center", fontsize=7, color="white", zorder=3)
    for z in (z1, z2):
        ax.add_patch(plt.Circle(P[z], 0.33, fc=BLUE, ec="none", zorder=2))
        ax.text(*P[z], f"$Z_{{{z}}}$", ha="center", va="center", fontsize=6.3, color="white", zorder=3)
    # pairing at a private reader z: x_f + o_f(z) = x_g + o_g(z)
    rel = {z: idx[(g, z)]["index"] - idx[(f, z)]["index"] for z in (z1, z2)}
    hol = abs(rel[z1] - rel[z2])
    check(hol == ex["holonomy"], "holonomy mismatch")
    s = lambda v: f"{v:+d}".replace("-", "−")
    ax.text(3.0, -1.0, f"$Z_{{{z1}}}$: $x_{{{f}}}-x_{{{g}}}={s(rel[z1])}$    "
                       f"$Z_{{{z2}}}$: $x_{{{f}}}-x_{{{g}}}={s(rel[z2])}$",
            ha="center", va="center", fontsize=6.3, color=INK)
    ax.text(3.0, -1.55, f"holonomy {hol}: no relative round fixes both", ha="center", va="center", fontsize=6.3,
            color=GREY)


def panel_c(ax):
    ax.set_xlim(0, 6.4)
    ax.set_ylim(-1.75, 5.2)
    ax.set_aspect("equal")
    ax.axis("off")
    # check order q1..q6, hook after the 4th CNOT leaves q5 q6
    for k in range(6):
        hot = k >= 4
        ax.add_patch(Rectangle((1.6 + 0.55 * k, 3.4), 0.48, 0.48, fc=VERMILION if hot else LIGHT, ec="none"))
        ax.text(1.6 + 0.55 * k + 0.24, 3.64, f"$q_{k + 1}$", ha="center", va="center", fontsize=6.3,
                color="white" if hot else INK)
    ax.text(1.45, 3.64, "check $c$:", ha="right", va="center", fontsize=6.5, color=INK)
    ax.annotate("", xy=(4.06, 3.3), xytext=(4.06, 2.25),
                arrowprops=dict(arrowstyle="<-", color=INK, lw=0.7))
    ax.text(4.2, 2.8, "one hook\nfault", ha="left", va="center", fontsize=6.0, color=INK)
    # weight-d logical: d data qubits, two of them = {q5, q6}
    dd = 12
    for k in range(dd):
        x = 0.45 + 0.5 * k
        hot = k in (7, 8)
        ax.plot([x], [1.7], "o", ms=5.0, color=VERMILION if hot else GREY, mec="white", mew=0.5)
    ax.add_patch(FancyBboxPatch((0.45 + 0.5 * 7 - 0.22, 1.45), 0.94, 0.5, boxstyle="round,pad=0.02", fc="none",
                                ec=VERMILION, lw=0.8))
    ax.text(3.2, 1.05, r"weight-$d$ logical $\supset\{q_5,q_6\}$", ha="center", va="center", fontsize=6.3,
            color=INK)
    ax.text(3.2, 0.2, r"flat hook: $G$ constant on the checks it meets oddly", ha="center", va="center",
            fontsize=6.3, color=GREY)
    ax.text(3.2, -0.55, r"$\Rightarrow$ $(d-2)$ data faults $+\,1$ hook", ha="center", va="center", fontsize=6.8,
            color=INK)
    ax.text(3.2, -1.2, r"$d_{\rm circ}\leq d-1$", ha="center", va="center", fontsize=7.5, color=INK)


def main():
    style()
    d = load("paper/figures/fig1_P_data.json")
    fig = plt.figure(figsize=(7.05, 2.45))
    axa = fig.add_axes([0.0, 0.0, 0.36, 1.0])
    axb = fig.add_axes([0.37, 0.0, 0.32, 1.0])
    axc = fig.add_axes([0.70, 0.0, 0.30, 1.0])
    panel_a(axa, d)
    panel_b(axb, d)
    panel_c(axc)
    for ax, t in ((axa, "(a)"), (axb, "(b)"), (axc, "(c)")):
        ax.text(0.0, 1.0, t, transform=ax.transAxes, ha="left", va="top", fontsize=8, fontweight="bold")
    save(fig, "fig1_P")


if __name__ == "__main__":
    main()
