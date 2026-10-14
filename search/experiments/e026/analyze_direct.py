"""E-026: summarize direct-sampling CSVs: per-basis P(R), per-round eps, combined eps_Z + eps_X with 95% intervals
(Jeffreys beta posterior Monte Carlo), per-layer rate, ratios vs ibm.
  uv run python -m search.experiments.e026.analyze_direct [--noise sd6]"""
import argparse, glob, json
from collections import defaultdict
import numpy as np
import sinter
from search.experiments.e026.common import OUT, PERIOD

ap = argparse.ArgumentParser(); ap.add_argument("--noise", default="sd6"); ap.add_argument("--R", type=int, default=12)
a = ap.parse_args()
agg = defaultdict(lambda: [0, 0, 0.0])
for f in glob.glob(str(OUT / "direct" / "*.csv")):
    for s in sinter.read_stats_from_csv_files(f):
        m = s.json_metadata
        if m.get("noise", "sd6") != a.noise or m["R"] != a.R:
            continue
        k = (m["circ"], m["p"], s.decoder, m["basis"])
        agg[k][0] += s.shots; agg[k][1] += s.errors; agg[k][2] += s.seconds
rng = np.random.default_rng(1)
NS = 20000
rows = {}
cpu = sum(v[2] for v in agg.values())
for (c, p, dec) in sorted({k[:3] for k in agg}):
    if not all((c, p, dec, b) in agg for b in "ZX"):
        continue
    draws = 0; row = {"circ": c, "p": p, "dec": dec}
    for b in "ZX":
        n, k, sec = agg[(c, p, dec, b)]
        P = rng.beta(k + 0.5, n - k + 0.5, NS)
        e = 1 - (1 - P) ** (1 / a.R)
        draws = draws + e
        row[b] = dict(shots=n, errors=k, P=k / n, eps=1 - (1 - k / n) ** (1 / a.R), cpu_s=round(sec))
    pt = row["Z"]["eps"] + row["X"]["eps"]
    lo, hi = np.quantile(draws, [0.025, 0.975])
    row.update(eps=pt, lo=float(lo), hi=float(hi), per_layer=pt / PERIOD[c], draws=draws)
    rows[(c, p, dec)] = row
out = []
for (c, p, dec), r in sorted(rows.items(), key=lambda x: (x[0][2], x[0][1], x[0][0])):
    ib = rows.get(("ibm", p, dec)); fg = rows.get(("fig12", p, dec))
    for nm, ref in (("ibm", ib), ("fig12", fg)):
        if ref is not None and c != nm:
            rr = r["draws"] / ref["draws"]
            r[f"ratio_vs_{nm}"] = [r["eps"] / ref["eps"] if ref["eps"] > 0 else None,
                                   float(np.quantile(rr, 0.025)), float(np.quantile(rr, 0.975))]
    d = {k: v for k, v in r.items() if k != "draws"}
    out.append(d)
    print(f'{dec:6s} p={p:.4f} {c:5s} Z {r["Z"]["errors"]:4d}/{r["Z"]["shots"]:7d} X {r["X"]["errors"]:4d}/{r["X"]["shots"]:7d} '
          f'eps={r["eps"]:.3e} [{r["lo"]:.2e},{r["hi"]:.2e}] per_layer={r["per_layer"]:.2e} '
          + " ".join(f'{k}={v[0]:.3g}[{v[1]:.3g},{v[2]:.3g}]' for k, v in r.items() if k.startswith("ratio") and v[0]))
print("total sinter seconds", round(cpu), "=", round(cpu / 3600, 2), "h")
(OUT / f"direct_summary_{a.noise}_R{a.R}.json").write_text(json.dumps({"rows": out, "sinter_seconds": cpu}, indent=1))
