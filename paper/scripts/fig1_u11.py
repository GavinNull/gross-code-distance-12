"""Fig. 1 (two-column): the period-11 gross circuit u11.
(a) non-segmentability: each data qubit does XXX then ZZZ per period, yet the instance precedence graph has the
    6-cycle X9 -> Z17 -> X12 -> Z20 -> X22 -> Z24 -> X9 (recomputed from the spec with the evaluator's unroll);
(b) one weight-10 extended logical: lifts (injection-verified) in the segmented control, blocked in u11 because one
    Z check reads a data qubit between the two hook deposits it receives;
(c) proof chains for u11 (gross) and c11 ([[90,8,10]]).

  uv run python paper/scripts/fig1_u11_data.py   # exact computation -> paper/figures/fig1_u11_data.json
  uv run python paper/scripts/fig1_u11.py        # re-checks, reads the proof-chain files, draws

(c) sources (all asserted): u11 d_ext / lists: results/E-032-audit/a2_lists_u11_{Z,X}.log; lifts R = 1..31:
results/E-032-audit/a3_lift_u11_spec_{Z,X}.jsonl; gap: results/E-032-audit/a6_anyr.log; weight-12 injection:
results/E-032-audit/a5_inject12.json.  c11: d_ext = 8 and lists 585 / 16830: results/E-028-audit/a4b_lists.jsonl
(c16 class; c11's column set asserted equal in the E-030 audit lift); lifts R = 1..25: results/E-030-audit/a3_lift.jsonl;
gap: results/E-030-audit/a4_gap.json; weight-10 injection: results/E-030-audit/a1_check.json (inject_c11).
"""
from __future__ import annotations

import json
import re

from fig_common import BLUE, GREEN, GREY, INK, ORANGE, ROOT, VERMILION, check, load, style

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

FS = 8.0
W_IN, H_IN = 7.0, 4.75
XC, ZC = BLUE, ORANGE


def jlog(path):
    s = (ROOT / path).read_text()
    return json.loads(s[s.index("{"):])


def jsonl(path):
    return [json.loads(x) for x in (ROOT / path).read_text().splitlines() if x.strip()]


def chain_numbers():
    g = {}
    for b in "ZX":
        a2 = jlog(f"results/E-032-audit/a2_lists_u11_{b}.log")
        check(a2["W9_decide"]["solutions"] == 0, f"u11 d_ext >= 10 ({b})")
        check(a2["W11_enum"]["expanded_by_weight"] == {"10": 144, "11": 7344}, f"u11 lists ({b})")
        check(a2["cmp_w10"]["only_mine"] == a2["cmp_w10"]["only_project"] == 0 and
              a2["cmp_w11"]["only_mine"] == a2["cmp_w11"]["only_project"] == 0, f"u11 lists two enumerations ({b})")
        L = jsonl(f"results/E-032-audit/a3_lift_u11_spec_{b}.jsonl")
        check(sorted({r["R"] for r in L}) == list(range(1, 32)), f"u11 lift R = 1..31 ({b})")
        check(all(r["w10"] == r["w10z"] == r["w11"] == 0 and r["telescoping_violations"] == 0 for r in L), "u11 lift 0")
    ar = jlog("results/E-032-audit/a6_anyr.log")
    check(ar["D"] == 11 and ar["G"] == 31 and ar["Rprime_w11_T21"] == 31, "u11 gap G = 31, R' = 31")
    inj = load("results/E-032-audit/a5_inject12.json")
    for b in "ZX":
        Rs = [int(k[1:]) for k in inj[b] if re.fullmatch(r"R\d+", k)]
        check(inj[b]["weight"] == 12 and sorted(Rs) == [1, 2, 3, 6, 10, 31] and
              all(inj[b][f"R{r}"]["detectors_fired"] == 0 and inj[b][f"R{r}"]["obs_flipped"] for r in Rs), "u11 inj")
    g = dict(dext=10, l1=144, l2=7344, R=31, G=ar["G"], Rp=ar["Rprime_w11_T21"], w=12, d=12)
    # [[90,8,10]] c11
    lists = [r for r in jsonl("results/E-028-audit/a4b_lists.jsonl") if r["spec"].endswith("c16_spec.json") and "w8" in r]
    check(len(lists) == 2 and all(all(r[f"w{w}"] == 0 for w in range(1, 8)) and r["w8"] == 585 and r["w9"] == 16830
                                  and r["cmp8"]["equal"] and r["cmp9"]["equal"] for r in lists), "c16/c11 class lists")
    L = [r for r in jsonl("results/E-030-audit/a3_lift.jsonl") if r["spec"].endswith("c11_spec.json")]
    for b in "ZX":
        check(set(range(1, 26)) <= {r["R"] for r in L if r["basis"] == b}, f"c11 lift R = 1..25 ({b})")
    check(all(r["w8"] == r["w8z"] == r["w9"] == 0 for r in L), "c11 lift 0")
    gap = load("results/E-030-audit/a4_gap.json")
    check((gap["D"], gap["G"], gap["w8"]["R_prime"], gap["w9"]["R_prime"]) == (11, 31, 22, 25), "c11 gap")
    a1 = load("results/E-030-audit/a1_check.json")
    ic = a1["inject_c11"]
    check(sorted(ic) == sorted(f"{b}{r}" for b in "ZX" for r in (1, 2, 5, 11)) and
          all(v[0] == 0 and v[1] > 0 for v in ic.values()) and all(a1["w10_supports_are_logicals"].values()), "c11 inj")
    c = dict(dext=8, l1=585, l2=16830, R=25, G=gap["G"], Rp=gap["w9"]["R_prime"], w=10, d=10)
    return g, c


def draw_a(fig, d):
    a = d["a"]
    P = a["period"]
    # (a1) cyclic sequences
    ax = fig.add_axes([0.42 / W_IN, 3.93 / H_IN, 2.9 / W_IN, 0.5 / H_IN])
    ax.set_xlim(-0.5, P - 0.5)
    ax.set_ylim(-1.6, 0.6)
    ax.axis("off")
    for r, sq in enumerate(sorted(a["data_sequences"], key=lambda s: s[0][0])):
        y = -r
        typ = {t: ty for t, ty in sq}
        for t in range(P):
            ty = typ.get(t)
            fc = XC if ty == "X" else ZC if ty == "Z" else "white"
            ax.add_patch(Rectangle((t - 0.45, y - 0.36), 0.9, 0.72, fc=fc, ec=GREY, lw=0.6))
            if ty:
                ax.text(t, y, ty, ha="center", va="center", fontsize=FS, color="white" if ty == "X" else INK)
        ax.text(-0.75, y, ["L qubit", "R qubit"][r], ha="right", va="center", fontsize=FS)
    for t in range(P):
        ax.text(t, 0.62, str(t), ha="center", va="bottom", fontsize=FS - 0.5, color=GREY)
    fig.text(0.02 / W_IN, 4.7 / H_IN, "(a)", fontsize=FS + 1, fontweight="bold", va="top")
    fig.text(0.42 / W_IN, 4.7 / H_IN, f"one period ({P} steps): every data qubit does XXX then ZZZ",
             fontsize=FS, va="top")
    # (a2) instance timeline of the 6-cycle
    ax = fig.add_axes([0.42 / W_IN, 2.08 / H_IN, 2.95 / W_IN, 1.6 / H_IN])
    inst, cyc = a["instances"], a["cycle"]
    t0 = min(v["reset"] for v in inst.values()) - 0.8
    t1 = max(v["meas"] for v in inst.values()) + 0.8
    ax.set_xlim(t0, t1)
    ax.set_ylim(-len(cyc) + 0.4, 0.9)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.set_yticks([-i for i in range(len(cyc))], [f"${c[0]}_{{{c[1:]}}}$" for c in cyc])
    ax.tick_params(axis="y", length=0, labelsize=FS)
    ax.tick_params(axis="x", labelsize=FS, length=3)
    ax.set_xlabel("tick (round 1 of $R=3$)", fontsize=FS, labelpad=1)
    xr = inst["X9"]["reset"]
    ax.axvline(xr - 0.5, color=INK, lw=0.8, ls=(0, (2, 1.5)))
    ax.text(xr - 0.4, 0.62, "period boundary", fontsize=FS, color=GREY, ha="left", va="center")
    row = {c: -i for i, c in enumerate(cyc)}
    for c in cyc:
        v = inst[c]
        col = XC if c[0] == "X" else ZC
        ax.add_patch(Rectangle((v["reset"], row[c] - 0.18), v["meas"] - v["reset"], 0.36, fc=col, alpha=0.25, ec="none"))
        ax.plot([v["reset"]], [row[c]], marker="|", ms=8, color=col, mew=1.5)
        ax.plot([v["meas"]], [row[c]], marker="s", ms=4.5, color=col)
        ax.plot([t for t, _ in v["cnots"]], [row[c]] * len(v["cnots"]), "o", ms=3.2, color=col)
    for e in a["edges"]:
        u, v = "".join(map(str, e["u"])), "".join(map(str, e["v"]))
        rad = 0.0 if abs(row[u] - row[v]) == 1 else -0.35
        ax.add_patch(FancyArrowPatch((e["t_u"], row[u]), (e["t_v"], row[v]), arrowstyle="-|>", mutation_scale=8,
                                     lw=1.1, color=INK, connectionstyle=f"arc3,rad={rad}", shrinkA=3, shrinkB=3))
        xm, ym = (e["t_u"] + e["t_v"]) / 2, (row[u] + row[v]) / 2
        if rad == 0.0:
            ax.text(xm + 0.25, ym, f"$q_{{{e['qubit']}}}$", fontsize=FS, ha="left", va="center", color=GREY)
        else:
            ax.text(min(e["t_u"], e["t_v"]) - 0.55, ym + 0.5, f"$q_{{{e['qubit']}}}$", fontsize=FS, ha="right",
                    va="center", color=GREY)


def tmax_of(v):
    return max(v["meas"], *v["deposits"].values()) + 1.2


def draw_b(fig, d):
    b = d["b"]
    m = b["mechanism"]
    check(m is not None, "single forced detector in u11")
    fig.text(3.72 / W_IN, 4.7 / H_IN, "(b)", fontsize=FS + 1, fontweight="bold", va="top")
    nd = sum(1 for c in b["columns"] if c["data"])
    nh = len(b["columns"]) - nd
    fig.text(4.02 / W_IN, 4.7 / H_IN, f"one weight-10 extended logical ({nd} data + {nh} hook columns)",
             fontsize=FS, va="top")
    xa, xb = m["xchecks"]
    q, r = m["qubit"], m["zcheck"]
    panels = [("seg", "segmented control (period 15): lifts", 3.33), ("u11", "period 11: blocked", 2.05)]
    for key, title, y0 in panels:
        v = m[key]
        ax = fig.add_axes([4.55 / W_IN, y0 / H_IN, 2.35 / W_IN, 0.88 / H_IN])
        ax.set_xticks(range(0, int(tmax_of(v)) + 1, 2))
        tmax = tmax_of(v)
        ax.set_xlim(-0.6, tmax)
        ax.set_ylim(-2.55, 0.6)
        for sp in ("top", "right", "left"):
            ax.spines[sp].set_visible(False)
        ax.set_yticks([0, -1, -2], [f"$X_{{{xa}}}$ anc.", f"$X_{{{xb}}}$ anc.", f"$q_{{{q}}}$"])
        ax.tick_params(axis="y", length=0, labelsize=FS)
        ax.tick_params(axis="x", labelsize=FS, length=3)
        ax.set_title(title, fontsize=FS, loc="left", pad=2, color=INK if key == "seg" else VERMILION)
        for i, x in enumerate((xa, xb)):
            ft, dep = v["faults"][str(x)], v["deposits"][str(x)]
            ax.plot([ft + 0.5], [-i], marker="x", ms=6, mew=1.5, color=INK)
            ax.add_patch(FancyArrowPatch((ft + 0.5, -i), (dep + 0.4, -2), arrowstyle="-|>", mutation_scale=7,
                                         lw=0.9, color=XC, shrinkA=4, shrinkB=4))
            ax.plot([dep + 0.4], [-2], marker="*", ms=9, color=XC, mec="none")
        ax.plot([v["read"], v["read"]], [-2.35, -1.65], color=ZC, lw=2.8, solid_capstyle="butt")
        ax.text(v["read"], -1.32, f"$Z_{{{r}}}$ reads", fontsize=FS, ha="center", va="center", color=ZC)
        before = sum(dd < v["read"] for dd in v["deposits"].values())
        msg = (f"$Z_{{{r}}}$ sees {before} flips: silent" if before % 2 == 0 else
               f"$Z_{{{r}}}$ sees 1 flip: its detectors fire")
        ax.text(tmax, 0.3, msg, fontsize=FS, ha="right", va="center", color=INK if before % 2 == 0 else VERMILION)
        if key == "seg":
            check(before == 2, "seg: both deposits before the read")
        else:
            check(before == 1, "u11: read between the deposits")
    ax.set_xlabel("tick ($R=1$, $Z$ memory)", fontsize=FS, labelpad=1)


def draw_c(fig, g, c):
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.72 / H_IN])
    ax.set_xlim(0, W_IN)
    ax.set_ylim(0, 1.72)
    ax.axis("off")
    ax.text(0.02, 1.68, "(c)", fontsize=FS + 1, fontweight="bold", va="top")
    lanes = [("gross [[144,12,12]]", g, 1.18), ("[[90,8,10]]", c, 0.5)]
    xs = [1.95, 3.0, 4.15, 5.25, 6.4]
    ws = [0.7, 1.15, 1.0, 1.05, 1.05]
    for name, v, y in lanes:
        ax.text(1.35, y, name + "\nperiod 11", fontsize=FS, ha="right", va="center")
        txt = [f"$d_{{\\rm ext}}={v['dext']}$", f"lists {v['l1']} / {v['l2']}\n(weights {v['dext']}, {v['dext'] + 1})",
               f"exact lift\n$R\\leq{v['R']}$: none", f"gap $G={v['G']}$:\nany $R\\to R\\leq{v['Rp']}$",
               f"weight {v['w']} injected\n$\\Rightarrow d_{{\\rm circ}}={v['d']}$"]
        for i, (x, w, t) in enumerate(zip(xs, ws, txt)):
            ax.add_patch(FancyBboxPatch((x - w / 2, y - 0.26), w, 0.52, boxstyle="round,pad=0.01,rounding_size=0.05",
                                        fc="#f2f2f2", ec=INK, lw=0.8))
            ax.text(x, y, t, fontsize=FS, ha="center", va="center")
            if i < 4:
                ax.add_patch(FancyArrowPatch((x + w / 2, y), (xs[i + 1] - ws[i + 1] / 2, y), arrowstyle="-|>",
                                             mutation_scale=7, lw=0.8, color=INK))
    ax.text(W_IN / 2, 0.08, "segmentable circuits have $d_{\\rm circ}\\leq d_{\\rm ext}$ (SBB Cor. 1); "
            "here $d_{\\rm circ}=d_{\\rm ext}+2$ for both codes", fontsize=FS, ha="center", va="center")


def main():
    d = load("paper/figures/fig1_u11_data.json")
    check(d["segctl_equals_audit"], "segctl")
    check(d["a"]["cycle"] == ["X9", "Z17", "X12", "Z20", "X22", "Z24"] and len(d["a"]["edges"]) == 6, "6-cycle")
    check(d["b"]["seg_injected_detectors"] == 0 and d["b"]["seg_injected_observables"], "seg injection")
    check(d["b"]["seg_lifts_w10_R1"] == 144, "seg lifts 144")
    g, c = chain_numbers()
    style()
    fig = plt.figure(figsize=(W_IN, H_IN))
    draw_a(fig, d)
    draw_b(fig, d)
    draw_c(fig, g, c)
    fig.savefig(ROOT / "paper/figures/fig1_u11.pdf")
    fig.savefig(ROOT / "paper/figures/fig1_u11.png", dpi=300)
    print("wrote fig1_u11.pdf / .png", W_IN, "x", H_IN, "in")


if __name__ == "__main__":
    main()
