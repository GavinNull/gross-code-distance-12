"""Auditor (E-026b): recompute the journal's direct-sampling ratios from the raw sinter csv files with own code
(own aggregation, Jeffreys posterior MC with a different seed), plus per-layer ratios (x 8/18).
  uv run python research/audits/2026-10-15-E-026b-scripts/recheck_csv.py"""
import glob, json
from collections import defaultdict
from pathlib import Path
import numpy as np, sinter
ROOT = Path(__file__).resolve().parents[3]
agg = defaultdict(lambda: [0, 0])
for f in glob.glob(str(ROOT / "results/E-026b-idle-sensitivity/direct/*.csv")):
    for s in sinter.read_stats_from_csv_files(f):
        m = s.json_metadata
        if m["R"] != 12: continue
        k = (m["noise"], m["circ"], m["p"], s.decoder, m["basis"])
        agg[k][0] += s.shots; agg[k][1] += s.errors
rng = np.random.default_rng(777); NS = 100000
def eps(nz, c, p, dec):
    d = 0; pt = 0
    for b in "ZX":
        n, k = agg[(nz, c, p, dec, b)]
        if n == 0: return None
        d = d + 1 - (1 - rng.beta(k + .5, n - k + .5, NS)) ** (1 / 12); pt += 1 - (1 - k / n) ** (1 / 12)
    return pt, d, [agg[(nz, c, p, dec, b)] for b in "ZX"]
out = []
for nz in ("lam0", "lam0.1", "lam0.3", "si1000cx"):
    for p in (0.004, 0.003, 0.002, 0.001):
        for dec in ("bposd", "relay5"):
            a = eps(nz, "p18", p, dec)
            if a is None: continue
            for ref in ("fig12", "ibm"):
                b = eps(nz, ref, p, dec)
                if b is None or b[0] == 0 or a[0] == 0: continue
                r = a[1] / b[1]; q = np.quantile(r, [.025, .975])
                row = dict(noise=nz, p=p, dec=dec, ref=ref, p18=a[2], refc=b[2], ratio=a[0] / b[0], ci=q.tolist(),
                           per_layer=a[0] / b[0] * 8 / 18, per_layer_ci=(q * 8 / 18).tolist())
                out.append(row)
                print(f"{nz:8s} {p:.0e} {dec:6s} p18/{ref:5s} {row['ratio']:.3g} [{q[0]:.3g}, {q[1]:.3g}]  layer {row['per_layer']:.3g}  p18 {a[2]} ref {b[2]}")
(ROOT / "results/E-026b-audit/recheck_csv.json").write_text(json.dumps(out, indent=1))
