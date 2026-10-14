"""E-026b: summarize direct sampling per noise model: per-basis counts, per-round eps = eps_Z + eps_X with 95% Jeffreys
intervals (beta posterior MC, seed 1), per layer, ratios p18/fig12 and p18/ibm (+ fig12/ibm) with intervals from the
same draws, and the lam1 validation (stage V vs E-026 csv).  lam1 rows = E-026 data (noise "sd6") + stage V.
  uv run python -m search.experiments.e026b.analyze"""
import glob, json
from collections import defaultdict
import numpy as np
import sinter
from search.experiments.e026b.common import OUT, PERIOD

E26 = OUT.parent / "E-026-gross-ler" / "direct"
R = 12
agg = defaultdict(lambda: [0, 0, 0.0])
src = defaultdict(lambda: defaultdict(lambda: [0, 0]))
for f in glob.glob(str(E26 / "*.csv")) + glob.glob(str(OUT / "direct" / "*.csv")):
    tag = "E026" if "E-026-gross" in f else "E026b"
    for s in sinter.read_stats_from_csv_files(f):
        m = s.json_metadata
        if m["R"] != R:
            continue
        nz = m.get("noise", "sd6")
        nz = "lam1" if nz == "sd6" else nz
        if nz == "noidle":
            continue
        k = (nz, m["circ"], m["p"], s.decoder, m["basis"])
        agg[k][0] += s.shots; agg[k][1] += s.errors; agg[k][2] += s.seconds
        src[k][tag][0] += s.shots; src[k][tag][1] += s.errors
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
    for nm in ("fig12", "ibm"):
        ref = rows.get((nz, nm, p, dec))
        if ref is None or nm == c or (c == "ibm"):
            continue
        rr = r["draws"] / ref["draws"]
        r[f"ratio_vs_{nm}"] = [r["eps"] / ref["eps"] if ref["eps"] > 0 else None,
                               float(np.quantile(rr, 0.025)), float(np.quantile(rr, 0.975))]
        # per layer = per round / period  ->  (eps_c / P_c) / (eps_nm / P_nm) = ratio * P_nm / P_c
        rl = rr * PERIOD[nm] / PERIOD[c]
        r[f"ratio_per_layer_vs_{nm}"] = [r[f"ratio_vs_{nm}"][0] * PERIOD[nm] / PERIOD[c] if ref["eps"] > 0 else None,
                                         float(np.quantile(rl, 0.025)), float(np.quantile(rl, 0.975))]
    out.append({k: v for k, v in r.items() if k != "draws"})
    rat = " ".join(f'{k[9:]}={v[0]:.3g}[{v[1]:.3g},{v[2]:.3g}]' for k, v in r.items()
                   if k.startswith("ratio_vs") and v[0] is not None)
    print(f'{nz:8s} {dec:6s} p={p:.5f} {c:5s} Z {r["Z"]["errors"]:4d}/{r["Z"]["shots"]:7d} X {r["X"]["errors"]:4d}/{r["X"]["shots"]:7d} '
          f'eps={r["eps"]:.3e} [{r["lo"]:.2e},{r["hi"]:.2e}] {rat}')
# validation: stage V (E026b, lam1) vs E-026 at the same (circ, p, dec, basis)
val = []
for k, d in src.items():
    if "E026" in d and "E026b" in d and k[0] == "lam1":
        (n1, e1), (n2, e2) = d["E026"], d["E026b"]
        a = rng.beta(e1 + .5, n1 - e1 + .5, NS); b2 = rng.beta(e2 + .5, n2 - e2 + .5, NS)
        q = np.quantile(b2 / a, [0.025, 0.975])
        val.append(dict(key=list(k), E026=[e1, n1], E026b=[e2, n2], ratio=(e2 / n2) / (e1 / n1),
                        ratio_ci=[float(q[0]), float(q[1])]))
        print("VALIDATION", k, f"E-026 {e1}/{n1}  E-026b {e2}/{n2}  ratio {(e2/n2)/(e1/n1):.3f} [{q[0]:.3f},{q[1]:.3f}]")
cpu = sum(v[2] for k, v in agg.items())
(OUT / "direct_summary_R12.json").write_text(json.dumps({"rows": out, "validation": val}, indent=1))
