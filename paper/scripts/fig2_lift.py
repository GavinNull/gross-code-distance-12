"""Fig. 2: lift outcome across circuit families (why the CNOT orders had to change).

  uv run python paper/scripts/fig2_lift.py

Bar = fraction of the row's units that lift to a weight-11 undetected circuit error.
Units: rows "Fig. 12" and "period 21" count the 4224 weight-11 extended logicals per basis (one circuit);
the other rows count circuits (a circuit counts if at least one weight-11 extended logical lifts).
Data (read-only, data archive) and the claims_map.md counts asserted:
  C13/C34 Fig. 12 4224/4224: results/E-018-audit/a9_fig12.json, results/E-021-audit/b3_fig12_{Z_1,X_1-2}.json
  C14/C15 P=8 retimings 4/4 (72/72 injections, R=1..6, both bases): results/E-020-audit/b2_inject_*.json
  C38 944/944: results/E-021-audit/b9_p8.json
  C39 233/233 lift, 0 certified (experiment log, in STATE; not re-run by the auditor):
      results/E-021-gross-new-orders/randsat_summary.json
  C34 cand_p21 0/4224, R=1..14,16, both bases: results/E-021-audit/cand_p21/b3_cand_{X,Z}_*.json
The unaudited 39/39 reasoned-candidate count is deliberately not plotted (figures_plan rev. c).
"""
from __future__ import annotations

import glob
import re

from fig_common import BLUE, COLW, GREY, INK, ORANGE, ROOT, check, load, save, style

import matplotlib.pyplot as plt


def rng(Rs):
    Rs = sorted(set(Rs))
    out, i = [], 0
    while i < len(Rs):
        j = i
        while j + 1 < len(Rs) and Rs[j + 1] == Rs[j] + 1:
            j += 1
        out.append(f"{Rs[i]}" if i == j else f"{Rs[i]}–{Rs[j]}")
        i = j + 1
    return ", ".join(out)


def bases(recs):
    b = sorted({r["basis"] for r in recs})
    return " & ".join(b[::-1]) if len(b) == 2 else b[0]


def main():
    rows = []
    # 1. Fig. 12 itself (C13, C34 positive control)
    f12 = load("results/E-018-audit/a9_fig12.json") + load("results/E-021-audit/b3_fig12_Z_1.json") \
        + load("results/E-021-audit/b3_fig12_X_1-2.json")
    check(all(r["of"] == 4224 and r["lifting"] == 4224 for r in f12), "C13: Fig. 12 lifts 4224/4224")
    check({r["basis"] for r in f12} == {"X", "Z"}, "Fig. 12 both bases")
    rows.append(dict(name="Fig. 12 itself", det=f"R = {rng(r['R'] for r in f12)}; {bases(f12)}",
                     num=4224, den=4224, unit="logicals per basis", audited=True))
    # 2. period-8 retimings keeping Fig. 12 orders (C14, C15)
    inj = load("results/E-020-audit/b2_inject_1_3_6.json") + load("results/E-020-audit/b2_inject_2_4_5.json")
    check(len(inj) == 72 and all(r["ok"] for r in inj), "C15: 72/72 injections ok")
    check(all(re.search(r"0 detectors fire", r["msg"]) and "nfaults=11" in r["msg"] for r in inj),
          "C15: injected witnesses are weight 11 with 0 detectors")
    cands = sorted({r["cand"] for r in inj})
    check(len(cands) == 4, "C14: 4 circuits up to translation")
    need = {(c, R, b) for c in cands for R in range(1, 7) for b in "XZ"}
    check(need <= {(r["cand"], r["R"], r["basis"]) for r in inj}, "C15: every circuit, R=1..6, both bases")
    rows.append(dict(name="$P=8$ retimings of Fig. 12", det=f"R = {rng(r['R'] for r in inj)}; {bases(inj)}",
                     num=len(cands), den=len(cands), unit="circuits", audited=True))
    # 3. period-8 colour-symmetric circuits in the Fig. 12 class (C38)
    p8 = load("results/E-021-audit/b9_p8.json")
    check(p8["enumerated"] == p8["theirs"] == 944 and p8["equal"] and p8["legal"] == 944
          and p8["deterministic"] == 944 and p8["ext_equal"] == 944, "C38: 944 legal deterministic, two enumerations")
    check(p8["lifts"] == 944 and len(p8["no_lift"]) == 0, "C38: all 944 lift")
    rows.append(dict(name="$P=8$ colour-symm., Fig. 12 class", det="R = 1; Z",
                     num=p8["lifts"], den=p8["enumerated"], unit="circuits", audited=True))
    # 4. random legal circuits of the search family (C39; experiment log)
    rs = load("results/E-021-gross-new-orders/randsat_summary.json")
    ex = rs["exact"]
    check(rs["samples"] == 2277 and len(ex) == 233, "C39: 2277 sampled, 233 exact-lifted")
    nl = sum(e["status"] == "lifts" for e in ex)
    check(nl == 233 and rs["certified"] == 0, "C39: 233/233 lift, 0 certified")
    rows.append(dict(name="random legal circuits, same family", det=f"R = {rng(e['R'] for e in ex)}; {bases(ex)}",
                     num=nl, den=len(ex), unit="circuits", audited=False))
    # 5. cand_p21 (C34)
    cp = []
    for f in sorted(glob.glob(str(ROOT / "results/E-021-audit/cand_p21/b3_cand_*.json"))):
        cp += load(str(f).replace(str(ROOT) + "/", ""))
    check(len(cp) > 0, "cand_p21 lift files present")
    check(all(r["of"] == 4224 and r["lifting"] == 0 for r in cp), "C34: cand_p21 0/4224")
    check(all(r["telescoping_bad"] == 0 and r["bad_obs"] == 0 and r["keys"] == 360 for r in cp), "C33 checks")
    for b in "XZ":
        check(sorted(r["R"] for r in cp if r["basis"] == b) == list(range(1, 15)) + [16], f"C34: R=1..14,16 ({b})")
    rows.append(dict(name="period-21 circuit (Table I)", det=f"R = {rng(r['R'] for r in cp)}; {bases(cp)}",
                     num=0, den=4224, unit="logicals per basis", audited=True))
    for r in rows:
        print(r)

    style()
    fig = plt.figure(figsize=(COLW, 1.95))
    ax = fig.add_axes([0.415, 0.2, 0.565, 0.78])
    n = len(rows)
    for i, r in enumerate(rows):
        y = n - 1 - i
        frac = r["num"] / r["den"]
        col = BLUE if i == n - 1 else ORANGE
        ax.barh(y, frac, height=0.56, color=col if r["audited"] else "white", edgecolor=col,
                hatch=None if r["audited"] else "////", lw=0.8)
        ax.text(0.025, y, f"{r['num']}/{r['den']} {r['unit']}", va="center", ha="left", fontsize=6.0,
                color=INK, bbox=None if r["audited"] else dict(fc="white", ec="none", pad=0.6))
        ax.text(-0.03, y + 0.13, r["name"], ha="right", va="center", fontsize=6.5, color=INK)
        ax.text(-0.03, y - 0.22, r["det"] + ("" if r["audited"] else "; experiment log"),
                ha="right", va="center", fontsize=5.6, color=GREY)
    ax.set_xlim(0, 1.0)
    ax.set_ylim(-0.6, n - 0.4)
    ax.set_xticks([0, 0.5, 1])
    ax.set_yticks([])
    ax.set_xlabel("fraction lifting to a weight-11 undetected error")
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.axhline(0.5, color=GREY, lw=0.4, ls=(0, (2, 2)))
    save(fig, "fig2_lift")


if __name__ == "__main__":
    main()
