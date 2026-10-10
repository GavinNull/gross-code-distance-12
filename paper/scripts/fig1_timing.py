"""Fig. 1: timing diagram of the period-21 gross circuit (cand_p21) vs Fig. 12 of SBB (arXiv:2603.05481).

  uv run python paper/scripts/fig1_timing.py

Data (read-only):
  search/experiments/e021/cand_p21_spec.json          (in git)
  results/E-021-gross-new-orders/fig12_spec.json      (data archive)
  baselines.strikis.strikis_fig12(gross_code())       (Fig. 12 rebuilt by the baseline code; must equal the file)
Per-class orders/times use the labelling of paper/scripts/extract_class_orders.py (which asserts support
equality and class uniformity). Assertions against claims_map.md: C31 (period 21, prep 0 / meas 20,
48 data qubits switch 4x), C32 (X1 identical to Fig. 12, 24 checks unchanged / 120 changed, in-pair swaps
only), Fig. 12 period 8 and non-interleaved.
"""
from __future__ import annotations

import importlib.util
import sys
from collections import Counter, defaultdict

from fig_common import BLUE, COLW, GREY, INK, ORANGE, ROOT, check, load, save, style

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("eco", ROOT / "paper/scripts/extract_class_orders.py")
eco = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eco)

CAND = "search/experiments/e021/cand_p21_spec.json"
FIG12 = "results/E-021-gross-new-orders/fig12_spec.json"


def fig12_from_baseline() -> dict:
    """Fig. 12 schedule from baselines.strikis, converted to the qec-schedule/v1 layout (data column = code column)."""
    from baselines.bb_code import gross_code
    from baselines.strikis import strikis_fig12
    sched, _ = strikis_fig12(gross_code())
    col = {q: j for j, q in enumerate(sched.data)}

    def one(q, is_x):
        tp = next(t for t, L in enumerate(sched.layers) if q in (L.prep_x if is_x else L.prep_z))
        tm = next(t for t, L in enumerate(sched.layers) if q in (L.meas_x if is_x else L.meas_z))
        cn = sorted([col[b], t] if q == a else [col[a], t]
                    for t, L in enumerate(sched.layers) for a, b in L.cnots if q in (a, b))
        return {"prep": tp, "meas": tm, "cnots": cn}

    return {"period": sched.depth, "x_checks": [one(q, True) for q in sched.x_checks],
            "z_checks": [one(q, False) for q in sched.z_checks]}


def norm(d):
    return (d["period"], [(c["prep"], c["meas"], sorted(map(tuple, c["cnots"]))) for c in d["x_checks"]],
            [(c["prep"], c["meas"], sorted(map(tuple, c["cnots"]))) for c in d["z_checks"]])


def per_check(d):
    """{(typ, colour): set of (labels-in-order, times-in-order, prep, meas)}; and per-check order lists."""
    P = d["period"]
    cls, orders = defaultdict(set), {}
    for typ, key in (("X", "x_checks"), ("Z", "z_checks")):
        for i, c in enumerate(d[key]):
            lab = eco.labels(i, typ)
            check({q for q, _ in c["cnots"]} == set(lab), f"support mismatch {typ}{i}")
            x, y = divmod(i, 6)
            seq = sorted(c["cnots"], key=lambda e: (e[1] - c["prep"]) % P)
            o = tuple(lab[q] for q, _ in seq)
            orders[(typ, i)] = o
            cls[(typ, (x + y) % 3)].add((o, tuple(t for _, t in seq), c["prep"], c["meas"]))
    for k, v in cls.items():
        check(len(v) == 1, f"class {k} not uniform")
    return {k: next(iter(v)) for k, v in cls.items()}, orders


def s(o, i, j):
    o = list(o); o[i], o[j] = o[j], o[i]; return tuple(o)


GROUP = {  # the 8-element class of SBB-extended-code-preserving orders (draft, Construction)
    "id": lambda o: o, "s12": lambda o: s(o, 0, 1), "s56": lambda o: s(o, 4, 5),
    "s12s56": lambda o: s(s(o, 0, 1), 4, 5),
}
GROUP.update({"rev·" + k: (lambda o, f=f: tuple(reversed(f(o)))) for k, f in list(GROUP.items())})
TEX = {"id": "id", "s12": r"$s_{12}$", "s56": r"$s_{56}$", "s12s56": r"$s_{12}s_{56}$"}


def transform(src, dst):
    hits = [k for k, f in GROUP.items() if f(src) == dst]
    check(len(hits) >= 1, f"order {dst} not in the 8-element class of {src}")
    return hits[0]


def switches(d):
    """Cyclic number of X/Z CNOT-type changes per data qubit over one period."""
    P = d["period"]
    ev = defaultdict(list)
    for typ, key in (("X", "x_checks"), ("Z", "z_checks")):
        for c in d[key]:
            for q, t in c["cnots"]:
                ev[q].append((t % P, typ))
    out = {}
    for q, e in ev.items():
        e.sort()
        check(len({t for t, _ in e}) == len(e), f"data qubit {q} used twice in one step")
        seq = [ty for _, ty in e]
        out[q] = sum(seq[i] != seq[i - 1] for i in range(len(seq)))
    return out


def main():
    cand, f12 = load(CAND), load(FIG12)
    check(norm(fig12_from_baseline()) == norm(f12), "fig12_spec.json differs from baselines.strikis Fig. 12")
    check(cand["period"] == 21 and f12["period"] == 8, "periods (C31: 21; Fig. 12: 8)")
    check(all(c["prep"] == 0 and c["meas"] == 20 for c in cand["x_checks"] + cand["z_checks"]),
          "C31: all ancillas reset at 0, measured at 20")
    ccls, cord = per_check(cand)
    fcls, ford = per_check(f12)
    tr = {k: transform(fcls[k][0], ccls[k][0]) for k in ccls}
    check(tr[("X", 1)] == "id", "C32: class X1 identical to Fig. 12")
    check(all(not v.startswith("rev") for v in tr.values()), "C32: only in-pair swaps")
    same = sum(cord[k] == ford[k] for k in cord)
    check((same, len(cord) - same) == (24, 120), f"C32: 24 unchanged / 120 changed checks, got {same}")
    sw_c, sw_f = Counter(switches(cand).values()), Counter(switches(f12).values())
    check(sw_c.get(4, 0) == 48 and max(sw_c) == 4, f"C31: 48 data qubits switch 4x, got {dict(sw_c)}")
    check(dict(sw_f) == {2: 144}, f"Fig. 12 non-interleaved (every data qubit 2 switches), got {dict(sw_f)}")
    print("switch histogram cand_p21", dict(sw_c), "| Fig. 12", dict(sw_f))
    for k in sorted(ccls):
        print(k, "cand", " ".join(ccls[k][0]), ccls[k][1], "| fig12", " ".join(fcls[k][0]), fcls[k][1], "|", tr[k])

    style()
    rows = [("X", 0), ("X", 1), ("X", 2), ("Z", 0), ("Z", 1), ("Z", 2)]
    fig, axes = plt.subplots(2, 1, figsize=(COLW, 2.6), sharex=True,
                             gridspec_kw={"hspace": 0.12, "height_ratios": [1, 1]})
    W = 0.84

    def box(ax, x, y, lab):
        fc, tc = (BLUE, "white") if lab[0] == "A" else (ORANGE, INK)
        ax.add_patch(Rectangle((x - W / 2, y - 0.36), W, 0.72, fc=fc, ec="white", lw=0.5, zorder=3))
        ax.text(x, y, f"${lab[0]}_{lab[1]}$", ha="center", va="center", fontsize=5.4, color=tc, zorder=4)

    def endpoint(ax, x, y, kind):
        fc, tc = ("white", INK) if kind == "R" else (INK, "white")
        ax.add_patch(Rectangle((x - W / 2, y - 0.36), W, 0.72, fc=fc, ec=INK, lw=0.6, zorder=3))
        ax.text(x, y, kind, ha="center", va="center", fontsize=5.4, color=tc, zorder=4)

    for ax, cls, P, name in ((axes[0], ccls, 21, "(a) period-21 circuit"), (axes[1], fcls, 8, "(b) Fig. 12 of SBB")):
        for r, k in enumerate(rows):
            y = -r
            order, times, prep, meas = cls[k]
            unroll = lambda t: prep + (t - prep) % P  # noqa: E731
            tm = unroll(meas) if meas != prep else prep + P
            ax.plot([prep, tm], [y, y], color=GREY, lw=0.6, zorder=1)
            endpoint(ax, prep, y, "R")
            endpoint(ax, tm, y, "M")
            for lab, t in zip(order, times):
                box(ax, unroll(t), y, lab)
            if P == 21:
                ax.text(21.75, y, TEX[tr[k]], ha="left", va="center", fontsize=6,
                        fontweight="bold" if tr[k] == "id" else "normal")
        ax.axvspan(-0.5, P - 0.5, color="#ececec", zorder=0, lw=0)
        if P == 8:
            ax.axvline(P - 0.5, color=INK, lw=0.6, ls=(0, (2, 1.5)), zorder=2)
            ax.text(P - 0.3, 0.75, "next period", fontsize=5.8, color=GREY, ha="left", va="center")
        ax.set_yticks([-r for r in range(6)], [f"${t}_{c}$" for t, c in rows])
        ax.set_ylim(-5.6, 1.15)
        ax.text(-0.5, 0.75, name, fontsize=7, ha="left", va="center")
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.tick_params(axis="y", length=0)
    axes[0].tick_params(axis="x", length=0)
    axes[1].set_xlim(-0.7, 21.6)
    axes[1].set_xticks(range(0, 21, 2))
    axes[1].set_xlabel("time step")
    axes[0].text(21.75, 0.75, "vs Fig. 12", fontsize=5.6, color=GREY, ha="left", va="center")
    save(fig, "fig1_timing")


if __name__ == "__main__":
    main()
