"""Combine the two trimmed-boundary batches; ratio with bootstrap CI; compare with untrimmed (same decoder A)."""
import json
import numpy as np
from scipy import stats
from common import OUT
pr = lambda P, n=12: 1 - (1 - P) ** (1 / n)
rng = np.random.default_rng(1)
f = {nm: np.concatenate([np.load(OUT / t / f"fails_{nm}_Z_A.npy") for t in ("trim_p0.005", "trim_p0.005_b")])
     for nm in ("strikisZ", "strikisX", "ibmZ", "ibmX")}
comb = lambda z, x: 1 - (1 - z.mean()) * (1 - x.mean())
def ratio(g): return pr(comb(g["strikisZ"], g["strikisX"])) / pr(comb(g["ibmZ"], g["ibmX"]))
rs = [ratio({k: v[rng.integers(0, len(v), len(v))] for k, v in f.items()}) for _ in range(4000)]
res = {"counts": {k: [int(v.sum()), len(v)] for k, v in f.items()}, "ratio_comb": ratio(f),
       "ratio_ci95_boot": np.percentile(rs, [2.5, 97.5]).tolist(),
       "ratio_Z": pr(f["strikisZ"].mean()) / pr(f["ibmZ"].mean()), "ratio_X": pr(f["strikisX"].mean()) / pr(f["ibmX"].mean())}
# untrimmed, decoder A, same metric: my joint resample (sector marginals) + E-003/E-002 originals
u = {"strikis": [138, 1000], "ibm": [101, 1000]}
orig = {"strikis": [64 + 71, 439 + 567], "ibm": [113 + 108, 997 + 1125]}
def lr(a, b):  # log ratio of failure probabilities and its SE (sector-pooled)
    pa, pb = a[0] / a[1], b[0] / b[1]
    return np.log(pr(pa) / pr(pb)), np.sqrt(1 / a[0] - 1 / a[1] + 1 / b[0] - 1 / b[1])
ts = [int(f["strikisZ"].sum() + f["strikisX"].sum()), 1200]; ti = [int(f["ibmZ"].sum() + f["ibmX"].sum()), 1200]
lt, st = lr(ts, ti)
pooled_u = [u["strikis"][0] + orig["strikis"][0], u["strikis"][1] + orig["strikis"][1]], \
           [u["ibm"][0] + orig["ibm"][0], u["ibm"][1] + orig["ibm"][1]]
lu, su = lr(*pooled_u)
z = (lu - lt) / np.hypot(su, st)
res.update({"trim_logratio": [lt, st], "untrimmed_pooled_counts": pooled_u, "untrimmed_pooled_ratio": float(np.exp(lu)),
            "untrimmed_logratio": [lu, su], "z_untrimmed_minus_trimmed": z, "p_two_sided": 2 * stats.norm.sf(abs(z)),
            "trim_vs_1_z": lt / st})
print(json.dumps(res, indent=1, default=float))
(OUT / "trim_combined.json").write_text(json.dumps(res, indent=1, default=float))
