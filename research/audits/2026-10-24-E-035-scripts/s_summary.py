"""Auditor E-035: summary of s_sample.jsonl (Jeffreys 95% per basis, eps = eps_Z + eps_X, ratio from the same draws,
MC seed 11, 200000 draws) and comparison with the experimenter's counts (r1_recheck.json).
    uv run python research/audits/2026-10-24-E-035-scripts/s_summary.py"""
import json
from collections import defaultdict
import numpy as np

ROOT = "/Users/ephemeral/Desktop/qec-ai-search/"
agg = defaultdict(lambda: [0, 0, 0.0])
for l in open(ROOT + "results/E-035-audit/s_sample.jsonl"):
    r = json.loads(l)
    a = agg[(r["model"], r["circ"], r["basis"])]
    a[0] += r["shots"]; a[1] += r["fails"]; a[2] += r["cpu"]
R = {"c11": 10, "ibm90": 10, "u11": 12, "ibm": 12}
rng = np.random.default_rng(11)
NS = 200000


def d(model, circ):
    out, pt, info = 0.0, 0.0, []
    for b in "ZX":
        n, k, _ = agg[(model, circ, b)]
        P = rng.beta(k + 0.5, n - k + 0.5, NS)
        out = out + 1 - (1 - P) ** (1 / R[circ]); pt += 1 - (1 - k / n) ** (1 / R[circ]); info.append(f"{k}/{n}")
    return out, pt, info


res = []
for model, a, b in (("cur_par_unp", "c11", "ibm90"), ("proj", "c11", "ibm90"), ("curx0.5", "u11", "ibm")):
    if not all((model, c, x) in agg for c in (a, b) for x in "ZX"):
        continue
    da, pa, ia = d(model, a); db, pb, ib = d(model, b)
    q = da / db
    lo, hi = np.quantile(q, [0.025, 0.975])
    ea = np.quantile(da, [0.025, 0.975]); eb = np.quantile(db, [0.025, 0.975])
    row = dict(model=model, pair=f"{a}/{b}", ratio=pa / pb, lo=lo, hi=hi, num=ia, den=ib, eps_a=[pa, *ea],
               eps_b=[pb, *eb])
    res.append(row)
    print(f"{model:11s} {a}/{b}: {pa/pb:.3f} [{lo:.3f}, {hi:.3f}]  {a} {ia} eps {pa:.3g} [{ea[0]:.3g},{ea[1]:.3g}]"
          f"  {b} {ib} eps {pb:.3g} [{eb[0]:.3g},{eb[1]:.3g}]")
print("CPU h", round(sum(v[2] for v in agg.values()) / 3600, 2))
json.dump(res, open(ROOT + "results/E-035-audit/s_summary.json", "w"), indent=1, default=float)
