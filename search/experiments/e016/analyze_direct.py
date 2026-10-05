"""E-016：直接采样汇总。每个 (p, 电路, 解码器)：shot 数、Z / X / 任一失败数、P_any、每轮每逻辑比特 LER，
两电路比值（IBM / 两色）及按批 bootstrap 95% 区间。CPU 秒合计。

    PYTHONPATH=. uv run python -m search.experiments.e016.analyze_direct
"""
from __future__ import annotations

import json
import re

import numpy as np

from search.experiments.e016.common import CIRCS, OUT, per_round_per_logical

DECS = ("bposd", "relay_s", "relay_j")


def load(pdir):
    data = {}
    cpu = 0.0
    for c in CIRCS:
        files = sorted(pdir.glob(f"{c}_b*.npz"))
        batches = []
        for f in files:
            z = np.load(f)
            cpu += float(z["cpu"])
            batches.append({k: z[k] for k in z.files})
        data[c] = batches
    return data, cpu


def summarize(pdir, nboot=2000, seed=0):
    data, cpu = load(pdir)
    rng = np.random.default_rng(seed)
    res = {"cpu_s": round(cpu)}
    nb = min(len(data[c]) for c in CIRCS)
    for c in CIRCS:
        pass
    for d in DECS:
        if not all(f"{d}_fZ" in b for c in CIRCS for b in data[c]):
            continue
        row = {}
        per_batch = {}
        for c in CIRCS:
            fz = np.array([b[f"{d}_fZ"].sum() for b in data[c]])
            fx = np.array([b[f"{d}_fX"].sum() for b in data[c]])
            fa = np.array([(b[f"{d}_fZ"] | b[f"{d}_fX"]).sum() for b in data[c]])
            n = np.array([len(b[f"{d}_fZ"]) for b in data[c]])
            nc = np.array([(~b[f"{d}_conv"]).sum() for b in data[c]])
            per_batch[c] = (fa, n)
            P = fa.sum() / n.sum()
            row[c] = {"shots": int(n.sum()), "fail_Z": int(fz.sum()), "fail_X": int(fx.sum()),
                      "fail_any": int(fa.sum()), "nonconv": int(nc.sum()), "P_any": P,
                      "B_per_round_per_logical": per_round_per_logical(P)}
        bt = []
        for _ in range(nboot):
            vals = {}
            for c in CIRCS:
                fa, n = per_batch[c]
                idx = rng.integers(0, len(fa), len(fa))
                vals[c] = per_round_per_logical(fa[idx].sum() / n[idx].sum())
            bt.append(vals["ibm"] / vals["twocolour"] if vals["twocolour"] > 0 else np.inf)
        r = row["ibm"]["B_per_round_per_logical"] / row["twocolour"]["B_per_round_per_logical"] \
            if row["twocolour"]["fail_any"] else float("inf")
        row["ratio_ibm_over_twocolour"] = r
        row["ratio_ci95"] = [float(np.percentile(bt, 2.5)), float(np.percentile(bt, 97.5))]
        res[d] = row
    return res


def main():
    out = {}
    for pdir in sorted((OUT / "direct").glob("p*")):
        p = float(re.sub("^p", "", pdir.name))
        out[p] = summarize(pdir)
        print(f"== p = {p}  (cpu {out[p]['cpu_s']} s)")
        for d in DECS:
            if d not in out[p]:
                continue
            r = out[p][d]
            print(f"  {d:8s}", "  ".join(
                f"{c}: n={r[c]['shots']} fZ={r[c]['fail_Z']} fX={r[c]['fail_X']} any={r[c]['fail_any']} "
                f"B={r[c]['B_per_round_per_logical']:.3e}" for c in CIRCS),
                f" ratio={r['ratio_ibm_over_twocolour']:.2f} [{r['ratio_ci95'][0]:.2f}, {r['ratio_ci95'][1]:.2f}]")
    (OUT / "direct_summary.json").write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
