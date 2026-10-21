"""E-033 summary of direct sampling (R = 12).  Pools, per (noise, circ, p, decoder, basis), the new E-033 csvs with the
identical-task E-026 / E-026b csvs (same e026 specs, same evaluator template, noise lam1 == sd6 byte for byte (probe),
same decoders and parameters, R = 12; E-026 rows carry no 'noise' key = sd6 = lam1).  p18 rows are ignored.
Per round eps = eps_Z + eps_X, eps_b = 1 - (1 - P_b)^(1/R); 95% Jeffreys intervals by beta-posterior Monte Carlo
(seed 1); ratios u11/ibm, u11/fig12, fig12/ibm from the same draws; per unit-duration layer ratio = per-round ratio x
8/11 (assumes all layers equal duration -- NOT per unit time).
  uv run python -m search.experiments.e033.analyze [--new-only]"""
import glob
import json
import sys
from collections import defaultdict

import numpy as np
import sinter

from search.experiments.e033.common import OUT, PERIOD, ROOT

R = 12
NEW_ONLY = "--new-only" in sys.argv
src = {"new": glob.glob(str(OUT / "direct" / "*.csv"))}
if not NEW_ONLY:
    src["old"] = glob.glob(str(ROOT / "results/E-026-gross-ler/direct/*.csv")) + \
        glob.glob(str(ROOT / "results/E-026b-idle-sensitivity/direct/*.csv"))
agg = defaultdict(lambda: {"new": [0, 0], "old": [0, 0], "sec": 0.0})
for tag, files in src.items():
    for f in files:
        for s in sinter.read_stats_from_csv_files(f):
            m = s.json_metadata
            if m.get("R") != R or m["circ"] not in PERIOD:
                continue
            nz = m.get("noise", "lam1")
            nz = "lam1" if nz == "sd6" else nz
            k = (nz, m["circ"], m["p"], s.decoder, m["basis"])
            agg[k][tag][0] += s.shots; agg[k][tag][1] += s.errors
            if tag == "new":
                agg[k]["sec"] += s.seconds
rng = np.random.default_rng(1)
NS = 40000
rows = {}
for (nz, c, p, dec) in sorted({k[:4] for k in agg}):
    if not all((nz, c, p, dec, b) in agg for b in "ZX"):
        continue
    draws = 0; row = {"noise": nz, "circ": c, "p": p, "dec": dec}
    for b in "ZX":
        a = agg[(nz, c, p, dec, b)]
        n = a["new"][0] + a["old"][0]; k = a["new"][1] + a["old"][1]
        P = rng.beta(k + 0.5, n - k + 0.5, NS)
        draws = draws + (1 - (1 - P) ** (1 / R))
        row[b] = dict(shots=n, errors=k, new=a["new"], old=a["old"], eps=1 - (1 - k / n) ** (1 / R))
    pt = row["Z"]["eps"] + row["X"]["eps"]
    lo, hi = np.quantile(draws, [0.025, 0.975])
    row.update(eps=pt, lo=float(lo), hi=float(hi), draws=draws)
    rows[(nz, c, p, dec)] = row
out = []
for key, r in sorted(rows.items(), key=lambda x: (x[0][0], x[0][3], -x[0][2], x[0][1])):
    nz, c, p, dec = key
    for num, den in (("u11", "ibm"), ("u11", "fig12"), ("fig12", "ibm")):
        if c != num or (nz, den, p, dec) not in rows:
            continue
        ref = rows[(nz, den, p, dec)]
        rr = r["draws"] / ref["draws"]
        pt = r["eps"] / ref["eps"] if ref["eps"] > 0 else None
        r[f"ratio_vs_{den}"] = [pt, float(np.quantile(rr, 0.025)), float(np.quantile(rr, 0.975))]
        f = PERIOD[den] / PERIOD[num]
        r[f"ratio_per_layer_vs_{den}"] = [pt * f if pt is not None else None, float(np.quantile(rr, 0.025)) * f,
                                          float(np.quantile(rr, 0.975)) * f]
    out.append({k: v for k, v in r.items() if k != "draws"})
    rat = " ".join(f'{k[9:]}={v[0]:.3g}[{v[1]:.3g},{v[2]:.3g}]' for k, v in r.items()
                   if k.startswith("ratio_vs") and v[0] is not None)
    cnt = " ".join(f'{b} {r[b]["errors"]}/{r[b]["shots"]}(new {r[b]["new"][1]}/{r[b]["new"][0]})' for b in "ZX")
    print(f'{nz:6s} {dec:6s} p={p:.4f} {c:5s} {cnt} eps={r["eps"]:.3e} [{r["lo"]:.2e},{r["hi"]:.2e}] {rat}')
cpu = sum(v["sec"] for v in agg.values())
print(f"E-033 sinter seconds total {cpu:.0f} ({cpu / 3600:.2f} h)")
(OUT / ("direct_summary_newonly.json" if NEW_ONLY else "direct_summary.json")).write_text(
    json.dumps({"rows": out, "sinter_seconds_new": cpu}, indent=1))
