"""Fig. 2 (was Fig. 1): timing diagram of the period-18 gross circuit (cs_P18_H24) vs Fig. 12 of SBB (arXiv:2603.05481).

  uv run python paper/scripts/fig2_timing.py

Data (read-only):
  search/experiments/e024a/cs_P18_H24.json            (in git; headline circuit, STATE item 13)
  results/E-024b-audit/cs_P18/b1_legal.json, b2_ext.json  (auditor: prep/meas sets, switch histogram, orders)
  results/E-021-gross-new-orders/fig12_spec.json      (data archive)
  baselines.strikis.strikis_fig12(gross_code())       (Fig. 12 rebuilt by the baseline code; must equal the file)
Per-class orders/times use the labelling of paper/scripts/extract_class_orders.py (which asserts support
equality and class uniformity). Assertions against research/audits/2026-10-11-E-024b.md sec. A-a:
period 18; prep in {2,15,16,17}, meas in {0,14,15,16} (wrapping, pipelined); data-qubit X/Z switch histogram
equal to the auditor's (48 x 2, 96 x 4); 144/144 checks are reversal + in-pair swaps of the Fig. 12 order
(0 unchanged); evaluator validate_schedule and L0 passed in the audit file. Fig. 12: period 8, non-interleaved.
Each row is drawn as one round's window [prep, meas] unrolled from the reset; the start is taken in the
current or the previous period so that the drawn span is shortest. Light grey R/M: the neighbouring rounds
of the same check (shows the pipelining).
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

CAND = "search/experiments/e024a/cs_P18_H24.json"
AUD = "results/E-024b-audit/cs_P18/"
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
# "rev·k": reverse first, then apply k (same convention as extract_class_orders.transform_name, "rev*k")
GROUP.update({"rev·" + k: (lambda o, f=f: f(tuple(reversed(o)))) for k, f in list(GROUP.items())})
_T = {"id": "", "s12": r"s_{12}", "s56": r"s_{56}", "s12s56": r"s_{12}s_{56}"}
TEX = {k: ("id" if k == "id" else f"${v}$") for k, v in _T.items()}
TEX.update({"rev·" + k: ("rev" if k == "id" else "rev " + f"${v}$") for k, v in _T.items()})


def transform(src, dst):
    hits = [k for k, f in GROUP.items() if f(src) == dst]
    check(len(hits) == 1, f"order {dst} not uniquely in the 8-element class of {src}")
    if hasattr(eco, "transform_name"):  # cross-check with the writer's Table-I extractor
        w = eco.transform_name(list(src), list(dst))
        check(w is not None and w.replace("*", "·").replace("s12·s56", "s12s56") == hits[0].replace("rev·id", "rev"),
              f"transform naming differs from extract_class_orders: {w} vs {hits[0]}")
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


def best_starts(cls, rows, P):
    """Per row choose start = prep or prep - P so that the overall drawn span is shortest (ties: later)."""
    import itertools
    best = None
    for ch in itertools.product((0, 1), repeat=len(rows)):
        st = [cls[k][2] - P * c for k, c in zip(rows, ch)]
        lo = min(st)
        hi = max(s0 + ((cls[k][3] - cls[k][2]) % P) for s0, k in zip(st, rows))
        key = (hi - lo, -lo)
        if best is None or key < best[0]:
            best = (key, st)
    return best[1]


def main():
    cand, f12 = load(CAND), load(FIG12)
    b1, b2 = load(AUD + "b1_legal.json"), load(AUD + "b2_ext.json")
    check(norm(fig12_from_baseline()) == norm(f12), "fig12_spec.json differs from baselines.strikis Fig. 12")
    check(cand["period"] == 18 == b1["period"] and f12["period"] == 8, "periods (E-024b A-a: 18; Fig. 12: 8)")
    preps = {c["prep"] for c in cand["x_checks"] + cand["z_checks"]}
    meass = {c["meas"] for c in cand["x_checks"] + cand["z_checks"]}
    check(preps == {2, 15, 16, 17} == set(b1["preps"]) and meass == {0, 14, 15, 16} == set(b1["meas"]),
          f"A-a: prep/meas sets, got {preps} {meass}")
    check(not b1["own_spec_problems"] and not b1["evaluator_validate_problems"]
          and all(v["passed"] for v in b1["L0"].values())
          and not any(v["any_fire_noiseless"] for v in b1["determinism"].values()), "A-a: legal, L0, deterministic")
    ccls, cord = per_check(cand)
    fcls, ford = per_check(f12)
    tr = {k: transform(fcls[k][0], ccls[k][0]) for k in ccls}
    same = sum(cord[k] == ford[k] for k in cord)
    rev = sum(1 for k in cord if not any(f(ford[k]) == cord[k] for n, f in GROUP.items() if not n.startswith("rev")))
    check(same == b2["order_relation"]["same"] == 0 and rev == b2["order_relation"]["rev+swaps"] == 144,
          f"A-a: 144/144 reversal + in-pair swaps, got same={same} rev={rev}")
    check(all(v.startswith("rev") for v in tr.values()), "every class reversed")
    check(b2["ext_X"]["equal"] and b2["ext_X"]["N_cand"] == 360, "A-a: extended code = Fig. 12 (360 cols)")
    sw_c, sw_f = Counter(switches(cand).values()), Counter(switches(f12).values())
    aud_sw = {int(k): v for k, v in b1["switch_hist"].items()}
    check(dict(sw_c) == aud_sw == {2: 48, 4: 96}, f"A-a: switch histogram 48x2, 96x4, got {dict(sw_c)}")
    check(dict(sw_f) == {2: 144}, f"Fig. 12 non-interleaved (every data qubit 2 switches), got {dict(sw_f)}")
    print("switch histogram cs_P18_H24", dict(sw_c), "| Fig. 12", dict(sw_f))
    for k in sorted(ccls):
        print(k, "cand", " ".join(ccls[k][0]), ccls[k][1], ccls[k][2:], "| fig12", " ".join(fcls[k][0]),
              fcls[k][1], fcls[k][2:], "|", tr[k])

    style()
    rows = [("X", 0), ("X", 1), ("X", 2), ("Z", 0), ("Z", 1), ("Z", 2)]
    W = 0.84
    spans = {}
    for name, cls, P in (("a", ccls, 18), ("b", fcls, 8)):
        st = best_starts(cls, rows, P)
        spans[name] = (st, min(st), max(s0 + ((cls[k][3] - cls[k][2]) % P) for s0, k in zip(st, rows)))
        print(name, "starts", st, "span", spans[name][1:])
    lo = min(v[1] for v in spans.values()) - 0.7
    hi = max(v[2] for v in spans.values()) + 0.7
    fig, axes = plt.subplots(2, 1, figsize=(COLW, 2.75), sharex=True,
                             gridspec_kw={"hspace": 0.12, "height_ratios": [1, 1]})

    def box(ax, x, y, lab):
        fc, tc = (BLUE, "white") if lab[0] == "A" else (ORANGE, INK)
        ax.add_patch(Rectangle((x - W / 2, y - 0.36), W, 0.72, fc=fc, ec="white", lw=0.5, zorder=3))
        ax.text(x, y, f"${lab[0]}_{lab[1]}$", ha="center", va="center", fontsize=5.4, color=tc, zorder=4)

    def endpoint(ax, x, y, kind, ghost=False):
        if ghost:
            ax.add_patch(Rectangle((x - W / 2, y - 0.36), W, 0.72, fc="white", ec="#b0b0b0", lw=0.5,
                                   ls=(0, (1.5, 1)), zorder=3))
            ax.text(x, y, kind, ha="center", va="center", fontsize=5.4, color="#a0a0a0", zorder=4)
            return
        fc, tc = ("white", INK) if kind == "R" else (INK, "white")
        ax.add_patch(Rectangle((x - W / 2, y - 0.36), W, 0.72, fc=fc, ec=INK, lw=0.6, zorder=3))
        ax.text(x, y, kind, ha="center", va="center", fontsize=5.4, color=tc, zorder=4)

    for ax, key, cls, P, name in ((axes[0], "a", ccls, 18, "(a) period-18 circuit"),
                                  (axes[1], "b", fcls, 8, "(b) Fig. 12 of SBB")):
        st = spans[key][0]
        ax.axvspan(-0.5, P - 0.5, color="#ececec", zorder=0, lw=0)
        for xb in (-0.5, P - 0.5):
            ax.axvline(xb, color=INK, lw=0.6, ls=(0, (2, 1.5)), zorder=2)
        for r, k in enumerate(rows):
            y = -r
            order, times, prep, meas = cls[k]
            s0 = st[r]
            tm = s0 + (meas - prep) % P
            ax.plot([s0, tm], [y, y], color=GREY, lw=0.6, zorder=1)
            endpoint(ax, s0, y, "R")
            endpoint(ax, tm, y, "M")
            for lab, t in zip(order, times):
                box(ax, s0 + (t - prep) % P, y, lab)
            # neighbouring rounds of the same check, where they fall inside the drawn range
            if lo < tm - P < s0 - 0.5:
                endpoint(ax, tm - P, y, "M", ghost=True)
            if tm + 0.5 < s0 + P < hi:
                endpoint(ax, s0 + P, y, "R", ghost=True)
            if key == "a":
                ax.text(hi + 0.15, y, TEX[tr[k]], ha="left", va="center", fontsize=5.8)
        ax.text(-0.3, 1.0, "period", fontsize=5.6, color=GREY, ha="left", va="center")
        ax.set_yticks([-r for r in range(6)], [f"${t}_{c}$" for t, c in rows])
        ax.set_ylim(-5.6, 1.45)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.tick_params(axis="y", length=0)
    for ax, name in ((axes[0], "(a) period-18 circuit"), (axes[1], "(b) Fig. 12 of SBB")):
        ax.set_title(name, fontsize=7, loc="left", pad=1)
    axes[0].tick_params(axis="x", length=0)
    axes[1].set_xlim(lo, hi)
    axes[1].set_xticks([t for t in range(int(lo) - 1, int(hi) + 1) if t % 2 == 0 and lo < t < hi])
    axes[1].set_xlabel("time step (dotted: period boundaries; grey: neighbouring rounds)")
    axes[0].text(hi + 0.15, 1.0, "vs Fig. 12", fontsize=5.6, color=GREY, ha="left", va="center")
    save(fig, "fig2_timing")


if __name__ == "__main__":
    main()
