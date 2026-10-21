"""A2 summary: per-round eps (Z+X), Jeffreys MC (seed 778), ratio c11/ibm; optional pooling with the experimenter.
    uv run python research/audits/2026-10-22-E-030-scripts/a2_summary.py"""
import json, collections
import numpy as np
a = collections.defaultdict(lambda: [0, 0, 0.0])
for l in open("results/E-030-audit/a2_sample.jsonl"):
    d = json.loads(l); k = (d["lam"], d["p"], d["circ"], d["basis"]); a[k][0] += d["shots"]; a[k][1] += d["fails"]; a[k][2] += d["cpu"]
rng = np.random.default_rng(778); R = 10; NS = 200000
def eps(c, extra=None):
    t, pt = 0, 0
    for b in "ZX":
        n, k, _ = a[(0.0, 0.003, c, b)]
        if extra: n += extra[c][b][0]; k += extra[c][b][1]
        t = t + 1 - (1 - rng.beta(k + .5, n - k + .5, NS)) ** (1 / R); pt += 1 - (1 - k / n) ** (1 / R)
    return t, pt
out = {"counts": {f"{k[2]}_{k[3]}": a[k][:2] for k in a}, "cpu_h": sum(v[2] for v in a.values()) / 3600}
for nm, ex in (("mine", None), ("pooled_with_experimenter", {"c11": {"Z": (60000, 42), "X": (60000, 43)}, "ibm": {"Z": (30341, 50), "X": (32033, 50)}})):
    tc, pc = eps("c11", ex); ti, pi = eps("ibm", ex)
    r = tc / ti
    out[nm] = {"eps_c11": [pc, *map(float, np.quantile(tc, [.025, .975]))], "eps_ibm": [pi, *map(float, np.quantile(ti, [.025, .975]))],
               "ratio": [pc / pi, *map(float, np.quantile(r, [.025, .975]))]}
print(json.dumps(out, indent=1))
json.dump(out, open("results/E-030-audit/a2_summary.json", "w"), indent=1)
