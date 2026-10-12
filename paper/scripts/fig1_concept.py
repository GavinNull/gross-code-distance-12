"""Fig. 1 (concept figure): (a) residuals and the order class sharing one extended code; (b) one real
"10 data + 1 hook" weight-11 extended logical: undetected under Fig. 12 timing, detected under the period-18
circuit; (c) the proof chain.

  uv run python paper/scripts/fig1_concept_data.py      # exact computation -> paper/figures/fig1_concept_data.json
  uv run python paper/scripts/fig1_concept.py           # this script: re-checks and draws

Numbers and where they are asserted:
  (a) the three unordered sets are invariant (as a collection; triple up to complement) under <rev, s12, s56>,
      8 distinct orders; on the real code, applying any of the 8 elements to every check of Fig. 12 leaves the
      extended-code column-key set of both sides unchanged (own computation with the E-021 audit's ext_keys);
      audit files: results/E-021-audit/cand_p21/b2_ext.json, results/E-024b-audit/cs_P18/b2_ext.json (equal).
  (b) from fig1_concept_data.json (exact DEM, CP-SAT, injection), re-checked here: the cycle of four Z checks,
      read/deposit ticks, Fig. 12 witness after both reads on every cycle qubit, and the forced chain in P = 18.
  (c) d_ext = 11: results/E-014-gross-dcirc11-proof/out_*_c*_s*.txt (W = 10: found = 0 for every case, both
      sides); 4224 per side: results/E-018-audit/a1_basics.json; lift R = 1..32, 0/4224 both bases:
      results/E-024b-audit/cs_P18/b3_cand_*.json; gap argument D = 18, G = 52, R' = 32:
      results/E-024a-gross12-period/anyr2_cs_P18_H24.json (audit 2026-10-11-E-024b A-a: R' = 32); weight-12
      injection R = 1, 3, 6, 10 both bases: results/E-024b-audit/cs_P18/b6_inject.json.
"""
from __future__ import annotations

import glob
import json
import re
import sys

from fig_common import BLUE, COLW, GREEN, GREY, INK, ORANGE, PURPLE, ROOT, VERMILION, check, load, save, style

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

sys.path[:0] = [str(ROOT), str(ROOT / "tests"), str(ROOT / "research/audits/2026-10-10-E-021-scripts")]

S12 = lambda o: (o[1], o[0]) + tuple(o[2:])  # noqa: E731
S56 = lambda o: tuple(o[:4]) + (o[5], o[4])  # noqa: E731
REV = lambda o: tuple(reversed(o))  # noqa: E731
GROUP = {"id": lambda o: tuple(o), "s12": S12, "s56": S56, "s12s56": lambda o: S56(S12(o))}
GROUP.update({"rev" + ("" if k == "id" else "·" + k): (lambda o, f=f: f(REV(o))) for k, f in list(GROUP.items())})


def three_sets(o):
    """{first two}, {first three} up to complement, {last two} -> the column-determining collection."""
    full = frozenset(o)
    tri = frozenset(o[:3])
    return frozenset([frozenset(o[:2]), frozenset(o[4:])]), frozenset([tri, full - tri])


def check_a():
    base = tuple(range(1, 7))
    orders = {k: f(base) for k, f in GROUP.items()}
    check(len(set(orders.values())) == 8, "8 distinct orders")
    check(len({three_sets(o) for o in orders.values()}) == 1, "three sets invariant under the group")
    # real code: uniform group action on all Fig. 12 orders leaves the extended code unchanged
    import os
    os.chdir(ROOT)
    from b_common import A1, ext_keys, orders as sorders, parse_schedule
    xo, zo = sorders(parse_schedule(A1.SPEC.to_dict()))
    for kind in "XZ":
        ref = set(ext_keys(kind, xo, zo))
        check(len(ref) == 360, f"360 extended columns ({kind})")
        for k, f in GROUP.items():
            got = set(ext_keys(kind, [list(f(o)) for o in xo], [list(f(o)) for o in zo]))
            check(got == ref, f"extended code changed under {k} ({kind})")
    for p in ("results/E-021-audit/cand_p21/b2_ext.json", "results/E-024b-audit/cs_P18/b2_ext.json"):
        d = load(p)
        check(all(v["equal"] for k, v in d.items() if k.startswith("ext_")), f"{p}: ext equal to Fig. 12")
    return orders


def check_c():
    outs = glob.glob(str(ROOT / "results/E-014-gross-dcirc11-proof/out_*_c*_s*.txt"))
    sides = {}
    for f in outs:
        m = re.search(r"SUMMARY W=(\d+) .*found=(\d+)", open(f).read())
        check(m is not None and m.group(1) == "10" and m.group(2) == "0", f"d_ext: W=10 no solution in {f}")
        sides.setdefault(re.search(r"out_([XZ])_", f).group(1), []).append(f)
    check(set(sides) == {"X", "Z"} and len(sides["X"]) == len(sides["Z"]) >= 15, "d_ext runs both sides, all cases")
    a1 = load("results/E-018-audit/a1_basics.json")
    check(all(a1[k]["n"] == 4224 and a1[k]["not_logical"] == 0 for k in "XZ" if k in a1) and "X" in a1,
          "4224 weight-11 per side")
    lift = []
    for f in glob.glob(str(ROOT / "results/E-024b-audit/cs_P18/b3_cand_*.json")):
        lift += json.load(open(f))
    for b in "XZ":
        check(sorted(r["R"] for r in lift if r["basis"] == b) == list(range(1, 33)), f"lift R=1..32 ({b})")
    check(all(r["lifting"] == 0 and r["of"] == 4224 for r in lift), "0/4224")
    ar = load("results/E-024a-gross12-period/anyr2_cs_P18_H24.json")
    check((ar["D"], ar["G"], ar["R_prime"]) == (18, 52, 32), f"gap argument D, G, R' = {ar['D'], ar['G'], ar['R_prime']}")
    inj = load("results/E-024b-audit/cs_P18/b6_inject.json")
    Rs = sorted(int(k[1:]) for k in inj["Z"] if re.fullmatch(r"R\d+", k))
    check(Rs == [1, 3, 6, 10] and all(inj[b]["weight"] == 12 and not inj[b][f"R{r}"]["any_detector"]
                                      and inj[b][f"R{r}"]["obs_flipped"] and inj[b][f"R{r}"]["minus_one_detected"]
                                      for b in "XZ" for r in Rs), "weight-12 injection")
    return dict(D=ar["D"], G=ar["G"], Rp=ar["R_prime"], Rmax=32, n=4224, inj=Rs)


def check_b():
    d = load("paper/figures/fig1_concept_data.json")
    check(d["n_r2"] == 360 and d["setting"]["R"] == 1 and d["setting"]["basis"] == "Z", "data file setting")
    f, p = d["fig12"], d["p18"]
    check(f["injected_detectors"] == 0 and f["injected_observables_flipped"], "Fig. 12 witness injection")
    core = [c["zcheck"] for c in p["core"]]
    check(all(c["kind"] == "final" for c in p["core"]) and len(core) == 4, "core = 4 final detectors")
    hook = tuple(d["hook"])
    cols = {tuple(c["support"]): c for c in p["columns"]}
    # cycle: hook - c_a - q - c_b - q' - ... - hook
    hook_checks = cols[hook]["checks"]
    check(len(hook_checks) == 2, "hook touches two core checks")

    def late_sig(sig):
        check(len(sig) == 1, "hook column has one DEM term")
        return dict(zip(core, sig[0][0]))
    hl_f, hl_p = late_sig(cols[hook]["sig_fig12"]), late_sig(cols[hook]["sig_p18"])
    start = [r for r in hook_checks if hl_p[r]][0]
    end = [r for r in hook_checks if r != start][0]
    seq, r, prev = [], start, hook
    while True:
        nxt = [q for q, c in cols.items() if q != prev and r in c["checks"]]
        check(len(nxt) == 1, "cycle structure")
        seq.append((r, nxt[0]))
        if nxt[0] == hook:
            break
        prev = nxt[0]
        r = [x for x in cols[nxt[0]]["checks"] if x != r][0]
    check(len(seq) == 4 and seq[-1][0] == end, "4-cycle through the hook")
    reads = {int(k): {int(q): v for q, v in m.items()} for k, m in p["reads_fig12_p18"].items()}

    def deposits(which):
        xorder = f["xorder"] if which == 0 else p["xorder"]
        ticks = f["hook_cnot_ticks"] if which == 0 else p["hook_cnot_ticks"]
        ft = [L["tick"] for L in f["witness"] if L["paulis"][0][1] >= 144][0] if which == 0 else p["hook_terms"][0]["tick"]
        return {q: ticks[str(q)][0] for q in xorder if ticks[str(q)][0] > ft}, ft
    out = {}
    for which, name, hl in ((0, "fig12", hl_f), (1, "p18", hl_p)):
        dep, ft = deposits(which)
        info = {}
        for r in (start, end):
            q = [x for x in reads[r] if x in dep]
            check(len(q) == 1, f"one hook deposit qubit per end check ({name}, Z{r})")
            q = q[0]
            rd, dt = reads[r][q][which][0], dep[q]
            check((dt > rd) == bool(hl[r]), f"hook lateness vs DEM signature ({name}, Z{r})")
            info[r] = dict(q=q, read=rd, dep=dt)
        out[name] = dict(hook=info, fault_tick=ft, deposit_set=dep)
    # data rows: read ticks of the two cycle checks
    rows = []
    for (r_in, q), (r_out, _) in zip(seq[:-1], seq[1:]):
        (qq,) = q
        rows.append(dict(q=qq, r_in=r_in, r_out=r_out, t_in=(reads[r_in][qq][0][0], reads[r_in][qq][1][0]),
                         t_out=(reads[r_out][qq][0][0], reads[r_out][qq][1][0])))
    # Fig. 12: witness data errors are after both reads on every cycle qubit (all late, consistent with the hook)
    wt = {int(k): v for k, v in f["data_fault_ticks"].items()}
    for row in rows:
        check(wt[row["q"]] >= max(row["t_in"][0], row["t_out"][0]), f"Fig. 12 witness late on q{row['q']}")
    check(all(hl_f[r] for r in (start, end)), "Fig. 12: hook late for both end checks")
    # P = 18: the forced chain. late for r_in forces late for r_out when r_out reads first.
    for row in rows:
        check(row["t_out"][1] < row["t_in"][1], f"P=18: Z{row['r_out']} reads q{row['q']} before Z{row['r_in']}")
    check(hl_p[start] and not hl_p[end], "P=18: hook late for one end check, early for the other")
    return d, seq, rows, out, start, end


def draw_a(ax, orders):
    ax.set_xlim(0, 10)
    ax.set_ylim(0.95, 4.35)
    ax.axis("off")
    ax.text(0, 4.2, "(a)", fontsize=7.5, va="top", fontweight="bold")
    # one check: ancilla + six CNOT targets in order
    x0, dx, y = 0.75, 0.62, 3.45
    ax.add_patch(plt.Circle((x0 - 0.45, y), 0.17, fc="white", ec=INK, lw=0.7))
    ax.text(x0 - 0.45, y, "a", ha="center", va="center", fontsize=6)
    for i in range(6):
        ax.add_patch(Rectangle((x0 + i * dx - 0.22, y - 0.2), 0.44, 0.4, fc="white", ec=INK, lw=0.6))
        ax.text(x0 + i * dx, y, f"$q_{i + 1}$", ha="center", va="center", fontsize=6)
    ax.annotate("", xy=(x0 + 5 * dx + 0.3, y + 0.33), xytext=(x0 - 0.2, y + 0.33),
                arrowprops=dict(arrowstyle="-|>", lw=0.5, color=GREY))
    ax.text(x0 + 2.5 * dx, y + 0.5, "CNOT order", ha="center", va="center", fontsize=5.6, color=GREY)
    # residual suffixes after a fault on the ancilla after the k-th CNOT
    res = [(2, "{q_1,q_2}", BLUE), (3, "{q_1,q_2,q_3}", GREEN), (4, "{q_5,q_6}", ORANGE)]
    for j, (k, lab, col) in enumerate(res):
        yy = y - 0.55 - 0.42 * j
        xa, xb = x0 + k * dx - 0.22, x0 + 5 * dx + 0.22
        ax.plot([xa, xb], [yy, yy], color=col, lw=2.2, solid_capstyle="butt")
        ax.plot([x0 + (k - 1) * dx + dx / 2] * 2, [yy - 0.12, yy + 0.12], color=INK, lw=0.6)
        eq = "=" if k == 4 else r"\equiv"
        ax.text(xb + 0.08, yy, f"${eq}{lab}$", fontsize=5.6, va="center", ha="left")
    ax.text(x0 - 0.55, y - 1.85, "residual of a fault after CNOT $k$ = suffix;\n"
            r"$\equiv$: same extended-code column", fontsize=5.4, va="center", ha="left", color=GREY)
    # the 8 orders: pair underlines coloured by set identity, triple bracket green
    ax.text(5.6, 4.2, r"$\langle$rev$, s_{12}, s_{56}\rangle$: 8 orders, same three sets", fontsize=5.6,
            va="center", ha="left")
    colmap = {frozenset({1, 2}): BLUE, frozenset({5, 6}): ORANGE}
    for n, (k, o) in enumerate(orders.items()):
        cx, cy = 6.55 + (n // 4) * 2.3, 3.55 - (n % 4) * 0.66
        for i, q in enumerate(o):
            ax.text(cx + i * 0.22, cy, str(q), fontsize=6, ha="center", va="center")
        for a, b in ((0, 2), (4, 6)):
            ax.plot([cx + a * 0.22 - 0.09, cx + (b - 1) * 0.22 + 0.09], [cy - 0.19] * 2,
                    color=colmap[frozenset(o[a:b])], lw=1.6, solid_capstyle="butt")
        ax.plot([cx - 0.09, cx + 2 * 0.22 + 0.09], [cy + 0.2] * 2, color=GREEN, lw=0.9)
        ax.text(cx - 0.2, cy, k.replace("·", " ").replace("s12s56", "$s_{12}s_{56}$").replace("s12", "$s_{12}$")
                .replace("s56", "$s_{56}$"), fontsize=4.6, ha="right", va="center", color=GREY)


def draw_b(axs, seq, rows, hk, start, end, d):
    names = ["Fig. 12 (undetected)", "period 18 (detected)"]
    ccol = {seq[0][0]: BLUE, seq[1][0]: ORANGE, seq[2][0]: GREEN, seq[3][0]: PURPLE}
    labels = ["hook"] + [f"data {r['q']}" for r in rows] + ["hook"]
    wt = {int(k): v for k, v in d["fig12"]["data_fault_ticks"].items()}
    for w, ax in enumerate(axs):
        h = hk["fig12" if w == 0 else "p18"]["hook"]
        xmax = 12.6 if w == 0 else 19.6
        ax.set_xlim(-0.5, xmax)
        ax.set_ylim(-4.6, 0.7)
        ax.set_yticks([0, -1, -2, -3, -4], labels if w == 0 else [""] * 5)
        ax.tick_params(axis="y", length=0, labelsize=6)
        ax.set_xticks(range(0, int(xmax) + 1, 2 if w == 0 else 3))
        ax.tick_params(axis="x", labelsize=5.6, length=2)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.set_title(names[w], fontsize=6.3, pad=2, color=INK)
        # checks: read marks on their two rows
        chain = [(start, 0, h[start]["read"], 1, rows[0]["t_in"][w])]
        for i, row in enumerate(rows):
            nxt = rows[i + 1]["t_in"][w] if i + 1 < len(rows) else h[end]["read"]
            chain.append((row["r_out"], i + 1, row["t_out"][w], i + 2, nxt))
        for r, ya, ta, yb, tb in chain:
            col = ccol[r]
            for yy, tt in ((-ya, ta), (-yb, tb)):
                ax.plot([tt, tt], [yy - 0.28, yy + 0.28], color=col, lw=1.6)
            ax.plot([ta, tb], [-ya - 0.28, -yb + 0.28], color=col, lw=0.5, ls=(0, (2, 1.5)))
            ax.text((ta + tb) / 2 + 0.25, -(ya + yb) / 2, f"$Z_{{{r}}}$", fontsize=5.2, color=col, va="center")
        # hook deposits
        for yy, r in ((0, start), (-4, end)):
            ax.plot([h[r]["dep"] + 0.4], [yy], marker="*", ms=6, color=VERMILION, mec="none")
            ax.text(h[r]["dep"] + 0.4, yy + (0.36 if yy == 0 else -0.42), f"on {h[r]['q']}", fontsize=4.6,
                    ha="center", va="center", color=GREY)
        if w == 0:
            for i, row in enumerate(rows):
                ax.plot([wt[row["q"]] + 0.4], [-(i + 1)], marker="X", ms=4.5, color=INK, mec="none")
            ax.text(xmax, 0.55, "all four checks silent", fontsize=5, ha="right", va="center", color=INK)
        else:
            for i, row in enumerate(rows):
                y = -(i + 1)
                ax.add_patch(Rectangle((row["t_in"][1] + 0.1, y - 0.16), xmax - row["t_in"][1], 0.32,
                                       fc=VERMILION, alpha=0.18, ec="none"))
            ax.text(xmax, 0.55, f"forced late (shaded) → $Z_{{{end}}}$ odd", fontsize=5, ha="right",
                    va="center", color=VERMILION)
    axs[0].set_xlabel("tick ($R=1$, $Z$ memory)", fontsize=6, labelpad=1)
    axs[1].set_xlabel("tick", fontsize=6, labelpad=1)


def draw_c(ax, c):
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5.4)
    ax.axis("off")
    ax.text(0, 5.35, "(c)", fontsize=7.5, va="top", fontweight="bold")
    steps = [
        r"$d_{\rm ext}=11$ (exhaustive search) $\Rightarrow$ no undetected error of weight $\leq 10$",
        f"weight 11: exact lift of all {c['n']} extended logicals, $R=1..{c['Rmax']}$: 0/{c['n']} lift",
        f"gap argument ($D={c['D']}$, $G={c['G']}$): any $R$ reduces to $R\\leq {c['Rp']}$",
        r"weight-12 logical injected, undetected $\Rightarrow$ $d_{\rm circ}=12$",
    ]
    for i, s in enumerate(steps):
        y = 4.55 - 0.95 * i
        ax.add_patch(FancyBboxPatch((0.6, y - 0.32), 9.3, 0.64, boxstyle="round,pad=0.02,rounding_size=0.12",
                                    fc="#f2f2f2", ec=INK, lw=0.5))
        ax.text(0.3, y, f"{i + 1}", fontsize=6, ha="center", va="center", fontweight="bold")
        ax.text(0.8, y, s, fontsize=5.6, ha="left", va="center")
        if i < 3:
            ax.add_patch(FancyArrowPatch((5.25, y - 0.33), (5.25, y - 0.62), arrowstyle="-|>", mutation_scale=5,
                                         lw=0.5, color=INK))
    ax.text(0.6, 0.55, "non-interleaved: $d_{\\rm circ}\\leq d_{\\rm ext}=11$ (SBB Cor. 1, Prop. 4); "
            "interleaved: not bound, the lift (2) decides", fontsize=5.3, va="center", color=INK)


def main():
    orders = check_a()
    c = check_c()
    d, seq, rows, hk, start, end = check_b()
    print("cycle", seq, "rows", rows, "hook", hk, "start", start, "end", end)
    style()
    fig = plt.figure(figsize=(COLW, 4.9))
    axa = fig.add_axes([0.02, 0.775, 0.96, 0.22])
    axb1 = fig.add_axes([0.11, 0.335, 0.33, 0.37])
    axb2 = fig.add_axes([0.47, 0.335, 0.51, 0.37])
    axc = fig.add_axes([0.02, 0.0, 0.96, 0.25])
    draw_a(axa, orders)
    fig.text(0.02, 0.745, "(b)", fontsize=7.5, fontweight="bold", va="center")
    draw_b([axb1, axb2], seq, rows, hk, start, end, d)
    draw_c(axc, c)
    save(fig, "fig1_concept")


if __name__ == "__main__":
    main()
