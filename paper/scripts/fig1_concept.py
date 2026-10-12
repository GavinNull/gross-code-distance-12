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

from fig_common import BLUE, GREEN, GREY, INK, ORANGE, PURPLE, ROOT, VERMILION, check, load, save, style

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


FS = 8.0          # every text element is 8 pt (two-column figure*, 7.0 in wide)
W_IN, H_IN = 7.0, 4.75


def inch_axes(fig, x, y, w, h):
    """Axes whose data coordinates are inches inside the box (x, y, w, h in figure inches)."""
    ax = fig.add_axes([x / W_IN, y / H_IN, w / W_IN, h / H_IN])
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    return ax


def draw_a(ax, orders):
    h = ax.get_ylim()[1]
    ax.text(0, h, "(a)", fontsize=FS + 1, va="top", fontweight="bold")
    x0, dx, y = 0.62, 0.36, h - 0.42
    ax.add_patch(plt.Circle((x0 - 0.33, y), 0.12, fc="white", ec=INK, lw=0.9))
    ax.text(x0 - 0.33, y, "a", ha="center", va="center", fontsize=FS)
    for i in range(6):
        ax.add_patch(Rectangle((x0 + i * dx - 0.14, y - 0.13), 0.28, 0.26, fc="white", ec=INK, lw=0.9))
        ax.text(x0 + i * dx, y, f"$q_{i + 1}$", ha="center", va="center", fontsize=FS)
    ax.annotate("", xy=(x0 + 5 * dx + 0.2, y + 0.24), xytext=(x0 - 0.15, y + 0.24),
                arrowprops=dict(arrowstyle="-|>", lw=0.9, color=GREY))
    ax.text(x0 + 5 * dx + 0.3, y + 0.24, "CNOT order", ha="left", va="center", fontsize=FS, color=GREY)
    res = [(2, r"$\equiv\{q_1,q_2\}$", BLUE), (3, r"$\equiv\{q_1,q_2,q_3\}$", GREEN), (4, r"$=\{q_5,q_6\}$", ORANGE)]
    for j, (k, lab, col) in enumerate(res):
        yy = y - 0.32 - 0.18 * j
        xa, xb = x0 + k * dx - 0.14, x0 + 5 * dx + 0.14
        ax.plot([xa, xb], [yy, yy], color=col, lw=3.5, solid_capstyle="butt")
        ax.plot([x0 + (k - 1) * dx + dx / 2] * 2, [yy - 0.07, yy + 0.07], color=INK, lw=1.0)
        ax.text(xb + 0.06, yy, lab, fontsize=FS, va="center", ha="left")
    ax.text(0.0, y - 0.92, "fault after CNOT $k$ spreads the suffix;  $\\equiv$: same extended-code column",
            fontsize=FS, va="center", ha="left", color=GREY)
    ax.text(0.0, y - 1.15, r"$\langle$rev$, s_{12}, s_{56}\rangle$: 8 orders, same three sets $\Rightarrow$ "
            "one extended code", fontsize=FS, va="center", ha="left")
    colmap = {frozenset({1, 2}): BLUE, frozenset({5, 6}): ORANGE}
    dd = 0.105
    for n, (k, o) in enumerate(orders.items()):
        cx, cy = 0.08 + (n % 4) * 0.76, y - 1.5 - (n // 4) * 0.5
        lab = k.replace("·", " ").replace("s12s56", "$s_{12}s_{56}$").replace("s12", "$s_{12}$") \
            .replace("s56", "$s_{56}$")
        ax.text(cx + 2.5 * dd, cy + 0.2, lab, fontsize=FS, ha="center", va="center", color=GREY)
        for i, q in enumerate(o):
            ax.text(cx + i * dd, cy, str(q), fontsize=FS, ha="center", va="center")
        for a, b in ((0, 2), (4, 6)):
            ax.plot([cx + a * dd - 0.045, cx + (b - 1) * dd + 0.045], [cy - 0.09] * 2,
                    color=colmap[frozenset(o[a:b])], lw=2.2, solid_capstyle="butt")
        ax.plot([cx - 0.045, cx + 2 * dd + 0.045], [cy + 0.085] * 2, color=GREEN, lw=1.4)


def draw_b(axs, seq, rows, hk, start, end, d):
    names = ["Fig. 12: undetected", "period 18: detected"]
    ccol = {seq[0][0]: BLUE, seq[1][0]: ORANGE, seq[2][0]: GREEN, seq[3][0]: PURPLE}
    labels = ["hook"] + [f"data {r['q']}" for r in rows] + ["hook"]
    wt = {int(k): v for k, v in d["fig12"]["data_fault_ticks"].items()}
    for w, ax in enumerate(axs):
        h = hk["fig12" if w == 0 else "p18"]["hook"]
        xmax = 12.8 if w == 0 else 19.8
        ax.set_xlim(-0.6, xmax)
        ax.set_ylim(-4.55, 0.55)
        ax.set_yticks([0, -1, -2, -3, -4], labels if w == 0 else [""] * 5)
        ax.tick_params(axis="y", length=0, labelsize=FS)
        ax.set_xticks(range(0, int(xmax) + 1, 4 if w == 0 else 6))
        ax.tick_params(axis="x", labelsize=FS, length=3, width=0.9)
        ax.spines["bottom"].set_linewidth(0.9)
        for sp in ("top", "right", "left"):
            ax.spines[sp].set_visible(False)
        ax.set_title(names[w], fontsize=FS + 0.5, pad=4, color=INK if w == 0 else VERMILION)
        # late region on each data row: after both of its cycle checks' reads
        for i, row in enumerate(rows):
            t0 = max(row["t_in"][w], row["t_out"][w])
            if w == 0:
                check(wt[row["q"]] >= t0, "Fig. 12 witness inside the late region")
            ax.add_patch(Rectangle((t0 + 0.15, -(i + 1) - 0.22), xmax - t0, 0.44, fc=GREY if w == 0 else VERMILION,
                                   alpha=0.22, ec="none"))
        chain = [(start, 0, h[start]["read"], 1, rows[0]["t_in"][w])]
        for i, row in enumerate(rows):
            nxt = rows[i + 1]["t_in"][w] if i + 1 < len(rows) else h[end]["read"]
            chain.append((row["r_out"], i + 1, row["t_out"][w], i + 2, nxt))
        for r, ya, ta, yb, tb in chain:
            col = ccol[r]
            for yy, tt in ((-ya, ta), (-yb, tb)):
                ax.plot([tt, tt], [yy - 0.3, yy + 0.3], color=col, lw=2.8, solid_capstyle="butt")
            ax.plot([ta, tb], [-ya - 0.3, -yb + 0.3], color=col, lw=1.0, ls=(0, (2.5, 1.5)))
            xm = (ta + tb) / 2
            ax.text(xm + (0.35 if w == 0 else 0.5), -(ya + yb) / 2, f"$Z_{{{r}}}$", fontsize=FS, color=col,
                    va="center", ha="left")
        for yy, r in ((0, start), (-4, end)):
            late = h[r]["dep"] > h[r]["read"]
            col = INK if late else VERMILION
            ax.plot([h[r]["dep"] + 0.3], [yy], marker="*", ms=9, color=col, mec="none")
            ax.text(h[r]["dep"] + 0.3, yy - 0.42, "late" if late else "early", fontsize=FS, ha="center",
                    va="center", color=col)
    axs[0].set_xlabel("tick ($R=1$)", fontsize=FS, labelpad=2)
    axs[1].set_xlabel("tick ($R=1$)", fontsize=FS, labelpad=2)


def draw_c(ax, c):
    h = ax.get_ylim()[1]
    ax.text(0, h, "(c)", fontsize=FS + 1, va="top", fontweight="bold")
    steps = [
        r"$d_{\rm ext}=11$ $\Rightarrow$ no undetected error of weight $\leq 10$",
        f"lift of all {c['n']} weight-11 logicals, $R\\leq{c['Rmax']}$: none",
        f"gap argument ($D={c['D']}$, $G={c['G']}$): any $R$ $\\to$ $R\\leq{c['Rp']}$",
        r"weight-12 logical undetected $\Rightarrow$ $d_{\rm circ}=12$",
    ]
    for i, s_ in enumerate(steps):
        y = h - 0.32 - 0.31 * i
        ax.add_patch(FancyBboxPatch((0.25, y - 0.11), 2.75, 0.22, boxstyle="round,pad=0.01,rounding_size=0.05",
                                    fc="#f2f2f2", ec=INK, lw=0.8))
        ax.text(0.1, y, f"{i + 1}", fontsize=FS, ha="center", va="center", fontweight="bold")
        ax.text(0.33, y, s_, fontsize=FS, ha="left", va="center")
        if i < 3:
            ax.add_patch(FancyArrowPatch((1.6, y - 0.115), (1.6, y - 0.195), arrowstyle="-|>", mutation_scale=6,
                                         lw=0.8, color=INK))
    ax.text(0.0, h - 1.6, "non-interleaved: $d_{\\rm circ}\\leq d_{\\rm ext}=11$ (SBB Cor. 1, Prop. 4)",
            fontsize=FS, va="center")
    ax.text(0.0, h - 1.82, "interleaved: not bound by $d_{\\rm ext}$; the lift (step 2) decides", fontsize=FS,
            va="center")


def main():
    orders = check_a()
    c = check_c()
    d, seq, rows, hk, start, end = check_b()
    print("cycle", seq, "rows", rows, "hook", hk, "start", start, "end", end)
    style()
    plt.rcParams.update({"axes.linewidth": 0.9})
    fig = plt.figure(figsize=(W_IN, H_IN))
    axa = inch_axes(fig, 0.05, 2.08, 3.15, 2.64)
    axc = inch_axes(fig, 0.05, 0.02, 3.15, 1.95)
    fig.text(3.38 / W_IN, 4.72 / H_IN, "(b)", fontsize=FS + 1, fontweight="bold", va="top")
    axb1 = fig.add_axes([3.98 / W_IN, 0.42 / H_IN, 1.22 / W_IN, 3.9 / H_IN])
    axb2 = fig.add_axes([5.35 / W_IN, 0.42 / H_IN, 1.6 / W_IN, 3.9 / H_IN])
    draw_a(axa, orders)
    draw_b([axb1, axb2], seq, rows, hk, start, end, d)
    draw_c(axc, c)
    fig.savefig(ROOT / "paper/figures/fig1_concept.pdf")
    fig.savefig(ROOT / "paper/figures/fig1_concept.png", dpi=300)
    print("wrote fig1_concept.pdf / .png", W_IN, "x", H_IN, "in")


if __name__ == "__main__":
    main()
