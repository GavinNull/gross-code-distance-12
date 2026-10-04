"""搜索阶段汇总：最好分数随评估次数的曲线、逐候选 CPU 比、与基线的差（含置信区间）。"""
import json
import math
from pathlib import Path

from search.experiments.e007 import common as C

RUNS = {"bb72-restricted": "sa-restricted-bb72-s0", "bb90-restricted": "sa-restricted-bb90-s0",
        "bb72-unrestricted": "sa-unrestricted-bb72-s0", "bb90-unrestricted": "sa-unrestricted-bb90-s0"}


def fails(m):
    c = m["counts"]
    return c.get("fail_any", c.get("any"))


def ratio(m):
    sp = m["speed"]
    return sp.get("ratio_to_reference", sp.get("ratio_to_paper_params"))


def rel_ci(base, x):
    """相对变化 x/base-1 的近似 95% 区间（把两个失败数当独立泊松，对成对数据偏保守）。"""
    r = x / base
    se = r * math.sqrt(1 / max(x, 1) + 1 / base)
    return r - 1, r - 1 - 1.96 * se, r - 1 + 1.96 * se


out = {}
for name, d in RUNS.items():
    ev = C.load_evals(C.RESULTS / d)
    base = fails(ev[0]["metrics"])
    n = ev[0]["metrics"]["counts"].get("shots", ev[0]["metrics"]["counts"].get("n"))
    best = 10**9
    curve, rows = [], []
    for r in ev:
        f = fails(r["metrics"])
        best = min(best, f)
        curve.append([r["eval_index"], best])
        rows.append({"i": r["eval_index"], "fail_any": f, "P_any": f / n, "cpu_ratio": ratio(r["metrics"])})
    out[name] = {"shots": n, "baseline_fail": base, "baseline_P_any": base / n, "best_so_far_fail": curve, "evals": rows,
                 "best_fail": best, "best_rel": rel_ci(base, best)}
    inb = [r for r in rows if r["cpu_ratio"] <= 2.0]
    mb = min(inb, key=lambda r: r["fail_any"])
    out[name]["best_within_2x"] = {**mb, "rel": rel_ci(base, mb["fail_any"])}
    print(name, "n", n, "base", base, "best", best, "rel(%.3f,[%.3f,%.3f])" % out[name]["best_rel"],
          "| best within 2x: eval", mb["i"], mb["fail_any"], "ratio %.2f" % mb["cpu_ratio"])
    marks = [1, 5, 10, 15, 20, 30, 40]
    print("   best-so-far fail count at evals", {k: curve[k - 1][1] for k in marks if k <= len(curve)})
json.dump(out, open(str(C.RESULTS / "search_summary.json"), "w"), indent=1)
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.6))
    for ax, task in zip(axs, ("bb72", "bb90")):
        for kind, st in (("restricted", "-"), ("unrestricted", "--")):
            o = out[f"{task}-{kind}"]
            ax.step([c[0] for c in o["best_so_far_fail"]], [c[1] / o["shots"] for c in o["best_so_far_fail"]], st,
                    where="post", label=kind)
        ax.set_title(f"{task}: best-so-far P_any (search set)")
        ax.set_xlabel("evaluations")
        ax.legend()
    fig.tight_layout()
    fig.savefig(str(C.RESULTS / "curves.png"), dpi=130)
except Exception as e:  # noqa: BLE001
    print("no plot:", e)
