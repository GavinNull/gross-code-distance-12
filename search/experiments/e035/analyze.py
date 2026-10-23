"""E-035 analysis: per-round eps = eps_Z + eps_X (eps_b = 1 - (1 - P_b)^(1/R)), 95% Jeffreys intervals by beta-posterior
MC (seed 1, 40000 draws), ratios from the same draws, failure counts.  Only E-035 csvs (direct/main.csv, sens.csv).
  uv run python -m search.experiments.e035.analyze"""
import glob
import json
from collections import defaultdict

import numpy as np
import sinter

from search.experiments.e035.common import OUT

PAIRS = {"gross": (("u11", "ibm"), ("u11", "fig12"), ("fig12", "ibm")), "bb90": (("c11", "ibm90"),)}
ORDER = ("cur", "curx0.5", "proj", "cur_cz", "cur_par", "cur_slow", "proj_t2par", "cur_par_unp")


def main():
    agg = defaultdict(lambda: [0, 0, 0.0])
    meta = {}
    for f in glob.glob(str(OUT / "direct" / "main.csv")) + glob.glob(str(OUT / "direct" / "sens.csv")):
        for s in sinter.read_stats_from_csv_files(f):
            m = s.json_metadata
            k = (m["fam"], m["model"], s.decoder, m["circ"], m["basis"])
            agg[k][0] += s.shots; agg[k][1] += s.errors; agg[k][2] += s.seconds
            meta[k[:4]] = m["R"]
    rng = np.random.default_rng(1)
    NS = 40000
    rows = {}
    for key, R in sorted(meta.items()):
        if not all(key + (b,) in agg for b in "ZX"):
            continue
        draws = 0.0
        r = {"R": R}
        for b in "ZX":
            n, k, sec = agg[key + (b,)]
            P = rng.beta(k + 0.5, n - k + 0.5, NS)
            draws = draws + (1 - (1 - P) ** (1 / R))
            r[b] = dict(shots=n, errors=k, cpu_s=sec)
        r["eps"] = sum(1 - (1 - r[b]["errors"] / r[b]["shots"]) ** (1 / R) for b in "ZX")
        r["lo"], r["hi"] = map(float, np.quantile(draws, [0.025, 0.975]))
        r["_d"] = draws
        rows[key] = r
    out = {"eps": [], "ratios": []}
    lines = ["| family | model | decoder | circuit | Z fail/shots | X fail/shots | eps per round [95%] |",
             "|---|---|---|---|---|---|---|"]
    for key in sorted(rows, key=lambda k: (k[0], ORDER.index(k[1]), k[2], k[3])):
        r = rows[key]
        out["eps"].append(dict(fam=key[0], model=key[1], dec=key[2], circ=key[3], eps=r["eps"], lo=r["lo"],
                               hi=r["hi"], Z=r["Z"], X=r["X"]))
        lines.append(f"| {key[0]} | {key[1]} | {key[2]} | {key[3]} | {r['Z']['errors']}/{r['Z']['shots']} | "
                     f"{r['X']['errors']}/{r['X']['shots']} | {r['eps']:.3g} [{r['lo']:.3g}, {r['hi']:.3g}] |")
    lines += ["", "| family | model | decoder | ratio | point [95%] | P(ratio<1) | fails num / den (Z+X) |",
              "|---|---|---|---|---|---|---|"]
    for fam, pairs in PAIRS.items():
        for model in ORDER:
            for dec in ("bposd", "relay5"):
                for a, b in pairs:
                    ka, kb = (fam, model, dec, a), (fam, model, dec, b)
                    if ka not in rows or kb not in rows:
                        continue
                    ra, rb = rows[ka], rows[kb]
                    q = ra["_d"] / rb["_d"]
                    lo, hi = np.quantile(q, [0.025, 0.975])
                    pt = ra["eps"] / rb["eps"] if rb["eps"] > 0 else float("nan")
                    fa = ra["Z"]["errors"] + ra["X"]["errors"]; fb = rb["Z"]["errors"] + rb["X"]["errors"]
                    out["ratios"].append(dict(fam=fam, model=model, dec=dec, num=a, den=b, ratio=pt, lo=float(lo),
                                              hi=float(hi), p_lt1=float((q < 1).mean()), fails=[fa, fb]))
                    lines.append(f"| {fam} | {model} | {dec} | {a}/{b} | {pt:.3g} [{lo:.3g}, {hi:.3g}] | "
                                 f"{(q < 1).mean():.3f} | {fa} / {fb} |")
    (OUT / "summary.json").write_text(json.dumps(out, indent=1))
    (OUT / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
