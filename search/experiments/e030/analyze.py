"""E-030: summarize direct sampling: per-basis counts, per-round eps = eps_Z + eps_X (each eps_b = 1-(1-P_b)^(1/R)) with
95% Jeffreys intervals (beta posterior MC, seed 1), ratios new/ibm (and c13/c11, c16/c11) from the same draws, and the
per unit-duration layer ratio (= per-round ratio x P_ibm / P_new; assumes every layer has the same duration, which is
NOT per unit time: measurement/reset layers are usually much longer than CX layers -- E-026b audit).
  uv run python -m search.experiments.e030.analyze"""
import glob
import json
from collections import defaultdict

import numpy as np
import sinter

from search.experiments.e030.common import OUT, PERIOD

R = 10
agg = defaultdict(lambda: [0, 0, 0.0])
for f in glob.glob(str(OUT / "direct" / "*.csv")):
    if f.endswith("timing.csv"):
        continue
    for s in sinter.read_stats_from_csv_files(f):
        m = s.json_metadata
        if m["R"] != R:
            continue
        k = (m["noise"], m["circ"], m["p"], s.decoder, m["basis"])
        agg[k][0] += s.shots; agg[k][1] += s.errors; agg[k][2] += s.seconds
rng = np.random.default_rng(1)
NS = 40000
rows = {}
for (nz, c, p, dec) in sorted({k[:4] for k in agg}):
    if not all((nz, c, p, dec, b) in agg for b in "ZX"):
        continue
    draws = 0; row = {"noise": nz, "circ": c, "p": p, "dec": dec}
    for b in "ZX":
        n, k, sec = agg[(nz, c, p, dec, b)]
        P = rng.beta(k + 0.5, n - k + 0.5, NS)
        draws = draws + (1 - (1 - P) ** (1 / R))
        row[b] = dict(shots=n, errors=k, eps=1 - (1 - k / n) ** (1 / R), sinter_s=round(sec))
    pt = row["Z"]["eps"] + row["X"]["eps"]
    lo, hi = np.quantile(draws, [0.025, 0.975])
    row.update(eps=pt, lo=float(lo), hi=float(hi), per_layer=pt / PERIOD[c], draws=draws)
    rows[(nz, c, p, dec)] = row
out = []
for key, r in sorted(rows.items(), key=lambda x: (x[0][0], x[0][3], -x[0][2], x[0][1])):
    nz, c, p, dec = key
    for nm in ("ibm", "c11"):
        ref = rows.get((nz, nm, p, dec))
        if ref is None or nm == c or c == "ibm":
            continue
        rr = r["draws"] / ref["draws"]
        pt = r["eps"] / ref["eps"] if ref["eps"] > 0 else None
        r[f"ratio_vs_{nm}"] = [pt, float(np.quantile(rr, 0.025)), float(np.quantile(rr, 0.975))]
        f = PERIOD[nm] / PERIOD[c]
        r[f"ratio_per_layer_vs_{nm}"] = [pt * f if pt is not None else None, float(np.quantile(rr * f, 0.025)),
                                         float(np.quantile(rr * f, 0.975))]
    out.append({k: v for k, v in r.items() if k != "draws"})
    rat = " ".join(f'{k[9:]}={v[0]:.3g}[{v[1]:.3g},{v[2]:.3g}]' for k, v in r.items()
                   if k.startswith("ratio_vs") and v[0] is not None)
    print(f'{nz:7s} {dec:6s} p={p:.4f} {c:4s} Z {r["Z"]["errors"]:4d}/{r["Z"]["shots"]:8d} X {r["X"]["errors"]:4d}/'
          f'{r["X"]["shots"]:8d} eps={r["eps"]:.3e} [{r["lo"]:.2e},{r["hi"]:.2e}] {rat}')
cpu = sum(v[2] for v in agg.values())
print(f"sinter seconds total {cpu:.0f} ({cpu / 3600:.2f} h)")
(OUT / "direct_summary_R10.json").write_text(json.dumps({"rows": out, "sinter_seconds": cpu}, indent=1))
