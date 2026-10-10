"""Fig. 3: the 80 two-round morphing circuits -- end-cycle distance vs exact circuit distance.

  uv run python paper/scripts/fig3_morphing.py [--allow-draft-table-mismatch]

Data (read-only, data archive):
  results/E-019-morphing-family/summary.json   160 records = 80 circuits x 2 bases (experimenter)
  results/E-019-audit/jobs2.out                auditor DFS on the 56 small-mother circuits, full T=4, both bases
  results/E-019-audit/dfs/*.txt                auditor exhaustive runs on 3 [[288]] circuits
  results/E-019-audit/ec288.txt                auditor end-cycle distances of the 24 [[288]] circuits
Auditor labels IV/VIII(sa,sb) -> experimenter keys as stated in research/audits/2026-10-08-E-019.md sec. 1
(f_x, f_y: IV00=paper, IV01=std10, IV10=std01, IV11=repo, VIII00..11=swap2,sw01,sw10,sw11; f_xy: both bits flipped).
Asserted against claims_map.md: C5 (80 circuits, 72 = d_end, 8 < d_end, 112/112 small-mother agreement),
C6 ([[54,8,8]]: 6,6,7,7 for the four Table IV orders; b3=x^2 -> 6), C7 ([[72,12,8]] f_x rev -> 6),
C9 (24 [[288]] preserve d_end in {12,10}; 3 independently reproduced).
The script also compares the per-row counts with Table tab:morph of paper/draft.tex and stops on a mismatch
unless --allow-draft-table-mismatch is given (then it prints the mismatch and still draws the data).
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict

from fig_common import BLUE, COLW, GREEN, GREY, INK, PURPLE, ROOT, VERMILION, check, load, save, style

import matplotlib.pyplot as plt

STD = {"repo", "paper", "std01", "std10"}
REV = {"swap2", "sw01", "sw10", "sw11"}
MAP_XY = {"IV00": "paper", "IV01": "std10", "IV10": "std01", "IV11": "repo",
          "VIII00": "swap2", "VIII01": "sw01", "VIII10": "sw10", "VIII11": "sw11"}


def aud2key(hom, lab):
    kind, bits = lab[:-2], lab[-2:]
    if hom == "xy":
        bits = "".join("1" if b == "0" else "0" for b in bits)
    return MAP_XY[kind + bits]


MOTHER = {"bb72": r"$[[72,12,6]]$", "bb108": r"$[[108,8,10]]$", "bb144": r"$[[144,12,12]]$",
          "bb288": r"$[[288,12,18]]$"}
MARK = {"bb72": ("o", BLUE), "bb108": ("s", VERMILION), "bb144": ("^", GREEN), "bb288": ("D", PURPLE)}

# Table tab:morph of paper/draft.tex (revision c), per row: (mother, d_end, d_circ, std/rev filter, count)
DRAFT_TABLE = [("bb72", 3, 3, None, 18), ("bb72", 4, 4, None, 6),
               ("bb108", 8, 6, "std", 2), ("bb108", 8, 7, "std", 2), ("bb108", 8, 7, "rev", 2),
               ("bb108", 7, 7, "rev", 2),
               ("bb144", 6, 6, None, 18), ("bb144", 5, 5, None, 2), ("bb144", 7, 7, None, 2), ("bb144", 8, 6, None, 2),
               ("bb288", 12, 12, None, 16), ("bb288", 10, 10, None, 8)]


def main(allow_mismatch: bool):
    recs = load("results/E-019-morphing-family/summary.json")
    check(len(recs) == 160, "C5: 160 records = 80 circuits x 2 bases")
    by = defaultdict(dict)
    for r in recs:
        check(r["all_checks"] and all(r["checks"].values()), f"C9: flags {r['key']} {r['basis']}")
        check(r["witness_ok"] is True or (r["key"].startswith("bb288") and r["ec_inject_ok"] is True),
              f"upper-bound witness {r['key']} {r['basis']}")
        by[r["key"]][r["basis"]] = r
    check(len(by) == 80 and all(set(v) == {"X", "Z"} for v in by.values()), "C5: 80 circuits, both bases")
    circ = {}
    for k, v in by.items():
        check(v["X"]["d_circ"] == v["Z"]["d_circ"] and v["X"]["d_end"] == v["Z"]["d_end"], f"bases differ {k}")
        m, hom, var = k.split("_")
        circ[k] = dict(mother=m, hom=hom, var=var, kind="std" if var in STD else "rev",
                       d_end=v["Z"]["d_end"], d=v["Z"]["d_circ"], n_end=v["Z"]["n_end"], kk=v["Z"]["k"])
    eq = sum(c["d"] == c["d_end"] for c in circ.values())
    below = [k for k, c in circ.items() if c["d"] < c["d_end"]]
    check(eq == 72 and len(below) == 8 and all(c["d"] <= c["d_end"] for c in circ.values()), "C5: 72 equal, 8 below")
    sub = lambda m, de, d: {c["var"] for c in circ.values() if (c["mother"], c["d_end"], c["d"]) == (m, de, d)}  # noqa
    check(sub("bb108", 8, 6) == {"paper", "std01"}, "C6: b3=x^2 orders (paper, std01) give 6")
    check(sub("bb108", 8, 7) == {"repo", "std10", "swap2", "sw10"}, "C6: repo/std10 and rev give 7")
    check(sorted(circ[f"bb108_y_{v}"]["d"] for v in STD) == [6, 6, 7, 7], "C6: four Table IV orders 6,6,7,7")
    check({k for k in below if k.startswith("bb144")} == {"bb144_x_sw01", "bb144_x_sw10"}
          and all(circ[k]["d_end"] == 8 and circ[k]["d"] == 6 and circ[k]["n_end"] == 72 for k in below
                  if k.startswith("bb144")), "C7: [[72,12,8]] f_x rev -> 6")
    b288 = [c for c in circ.values() if c["mother"] == "bb288"]
    check(len(b288) == 24 and all(c["d"] == c["d_end"] and c["d_end"] in (10, 12) for c in b288),
          "C9: 24 [[288]] circuits preserve d_end in {12,10}")

    # auditor agreement: small mothers (jobs2.out), d = first W with a solution
    aud = {}
    for line in (ROOT / "results/E-019-audit/jobs2.out").read_text().splitlines():
        if not line.startswith("{"):
            continue
        r = json.loads(line)
        m, hom, lab, basis = r["tag"].split("_")[:4]
        d = min(run["W"] for run in r["runs"] if run["found"])
        check(all(not run["found"] for run in r["runs"] if run["W"] < d), "jobs2 W order")
        aud[(f"{m}_{hom}_{aud2key(hom, lab)}", basis)] = d
    check(len(aud) == 112, f"C5: 112 auditor small-mother instances, got {len(aud)}")
    for (k, b), d in aud.items():
        check(circ[k]["d"] == d, f"C5: auditor disagrees on {k} {b}: {d} vs {circ[k]['d']}")
    repro = {k for k, _ in aud}
    check(len(repro) == 56, "C5: 56 small-mother circuits reproduced")
    # [[288]]: exhaustive W = d-1 with 0 solutions in both bases
    w_found = defaultdict(dict)
    for f in sorted((ROOT / "results/E-019-audit/dfs").glob("bb288_*_W*.txt")):
        m, hom, lab, basis, w = f.stem.split("_")
        mm = re.search(r"SUMMARY W=(\d+) found=(\d+)", f.read_text())
        if mm:
            w_found[(f"bb288_{hom}_{aud2key(hom, lab)}")][(basis, int(mm.group(1)))] = int(mm.group(2))
    rep288 = {k for k, v in w_found.items() if all(v.get((b, circ[k]["d"] - 1)) == 0 for b in "XZ")}
    check(rep288 == {"bb288_x_sw11", "bb288_y_paper", "bb288_xy_sw11"}, f"C9: 3 reproduced, got {rep288}")
    repro |= rep288
    # auditor end-cycle distances for all 24 [[288]]
    for line in (ROOT / "results/E-019-audit/ec288.txt").read_text().splitlines():
        hom, kind, bits, ds = re.match(r"(\w+) (IV|VIII) (\d\d): \[(.*)\]", line).groups()
        dd = {int(x) for x in ds.split(",")}
        check(dd == {circ[f"bb288_{hom}_{aud2key(hom, kind + bits)}"]["d_end"]}, f"ec288 {line}")

    # draft Table tab:morph cross-check
    mism = []
    for m, de, d, kind, n in DRAFT_TABLE:
        got = sum(1 for c in circ.values() if (c["mother"], c["d_end"], c["d"]) == (m, de, d)
                  and (kind is None or c["kind"] == kind))
        if got != n:
            mism.append(f"{m} d_end={de} d_circ={d} {kind or ''}: draft {n}, data {got}")
    check(sum(n for *_, n in DRAFT_TABLE) == 80, "draft table sums to 80")
    if mism:
        msg = "DRAFT TABLE tab:morph MISMATCH vs summary.json:\n  " + "\n  ".join(mism)
        if not allow_mismatch:
            raise SystemExit(msg)
        print("WARNING " + msg)

    # ---- plot
    style()
    fig, ax = plt.subplots(figsize=(COLW, 2.55))
    ax.plot([2.3, 12.7], [2.3, 12.7], color=GREY, lw=0.6, ls=(0, (3, 2)), zorder=1)
    ax.text(10.2, 10.95, r"$d_{\rm circ}=\tilde d$", rotation=45, rotation_mode="anchor", fontsize=6.3,
            color=GREY, ha="center", va="bottom")
    groups = Counter((c["d_end"], c["d"], c["mother"], k in repro) for k, c in circ.items())
    cells = defaultdict(list)
    for (de, d, m, rp), n in sorted(groups.items(), key=lambda t: (list(MARK).index(t[0][2]), not t[0][3])):
        cells[(de, d)].append((m, rp, n))
    for (de, d), lst in cells.items():
        w = 0.36
        x0 = de - w * (len(lst) - 1) / 2
        for i, (m, rp, n) in enumerate(lst):
            mk, col = MARK[m]
            x = x0 + i * w
            ax.scatter([x], [d], marker=mk, s=17, facecolor=col if rp else "white", edgecolor=col, lw=0.9, zorder=3)
            ax.text(x, d - 0.42, f"{n}", ha="center", va="top", fontsize=5.4, color=INK)
    # labels for the sub-d_end circuits
    ax.annotate(r"$[[54,8,8]]$ std, $b_3=x^2$" "\n" r"$[[72,12,8]]$ rev, $f_x$", xy=(8.38, 6), xytext=(9.2, 5.95),
                fontsize=5.8, arrowprops=dict(arrowstyle="-", lw=0.5, color=GREY, shrinkA=1, shrinkB=2), va="center", ha="left", color=INK)
    ax.annotate(r"$[[54,8,8]]$ std, $b_3=x$; rev", xy=(8.2, 7), xytext=(9.2, 7.05),
                fontsize=5.8, arrowprops=dict(arrowstyle="-", lw=0.5, color=GREY, shrinkA=1, shrinkB=2), va="center", ha="left", color=INK)
    handles = [ax.scatter([], [], marker=MARK[m][0], s=17, facecolor=MARK[m][1], edgecolor=MARK[m][1], lw=0.9,
                          label=MOTHER[m]) for m in MARK]
    handles.append(ax.scatter([], [], marker="o", s=17, facecolor="white", edgecolor=GREY, lw=0.9,
                              label="experimenter only"))
    ax.legend(handles=handles, loc="upper left", frameon=False, handletextpad=0.2, borderaxespad=0.2,
              labelspacing=0.3, title="mother code (filled: auditor-reproduced)", title_fontsize=5.8,
              alignment="left")
    ax.set_xlim(2.3, 12.9)
    ax.set_ylim(2.0, 12.9)
    ax.set_xticks(range(3, 13))
    ax.set_yticks(range(3, 13))
    ax.set_xlabel(r"end-cycle code distance $\tilde d$")
    ax.set_ylabel(r"exact circuit distance $d_{\rm circ}$")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    save(fig, "fig3_morphing")


if __name__ == "__main__":
    main("--allow-draft-table-mismatch" in sys.argv[1:])
