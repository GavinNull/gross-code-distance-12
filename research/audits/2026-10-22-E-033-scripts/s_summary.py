"""Auditor E-033: summary of own sampling (s_sample.jsonl): per-round eps (Z+X) with Jeffreys MC (seed 3304),
ratios u11/ibm, u11/fig12, fig12/ibm; plus pooled with the experimenter's final counts (lam0 3e-3 BP-OSD)."""
import json, collections
import numpy as np
ROOT = "/Users/ephemeral/Desktop/qec-ai-search/"
a = collections.defaultdict(lambda: [0, 0, 0.0])
for l in open(ROOT + "results/E-033-audit/s_sample.jsonl"):
    d = json.loads(l)
    if (d["lam"], d["p"]) != (0.0, 0.003): continue
    k = (d["circ"], d["basis"]); a[k][0] += d["shots"]; a[k][1] += d["fails"]; a[k][2] += d["cpu"]
rng = np.random.default_rng(3304); R = 12; NS = 200000
EXP = {"u11": {"Z": (90000, 9), "X": (90000, 22)}, "ibm": {"Z": (89852, 27), "X": (78001, 27)},
       "fig12": {"Z": (31963, 19), "X": (34045, 21)}}
def eps(c, extra=None):
    t, pt = 0, 0
    for b in "ZX":
        n, k, _ = a[(c, b)]
        if extra: n += extra[c][b][0]; k += extra[c][b][1]
        t = t + 1 - (1 - rng.beta(k + .5, n - k + .5, NS)) ** (1 / R); pt += 1 - (1 - k / n) ** (1 / R)
    return t, pt
out = {"counts": {f"{c}_{b}": a[(c, b)][:2] for (c, b) in a}, "cpu_h": sum(v[2] for v in a.values()) / 3600}
for nm, ex in (("mine", None), ("pooled_with_experimenter", EXP)):
    E = {c: eps(c, ex) for c in ("u11", "ibm", "fig12")}
    o = {f"eps_{c}": [E[c][1], *map(float, np.quantile(E[c][0], [.025, .975]))] for c in E}
    for x, y in (("u11", "ibm"), ("u11", "fig12"), ("fig12", "ibm")):
        r = E[x][0] / E[y][0]; o[f"{x}/{y}"] = [E[x][1] / E[y][1], *map(float, np.quantile(r, [.025, .975]))]
        o[f"P({x}/{y}<1)"] = float((r < 1).mean())
    out[nm] = o
print(json.dumps(out, indent=1))
json.dump(out, open(ROOT + "results/E-033-audit/s_summary.json", "w"), indent=1)
