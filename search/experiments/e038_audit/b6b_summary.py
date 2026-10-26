"""E-038 audit: per-round block error eps (same saturation correction as E-036 / its audit, k = 4) and N8/Kunlun ratios
with conservative Jeffreys-combined intervals, from results/E-038-audit/b6_ler.jsonl."""
import json

from scipy.stats import beta


def eps(P, k=4, R=6):
    Pr = 1 - 2 ** -k
    return Pr * (1 - (1 - min(P, Pr * 0.999999) / Pr) ** (1 / R))


def ci(f, n):
    return beta.ppf(0.025, f + .5, n - f + .5), beta.ppf(0.975, f + .5, n - f + .5)


rows = [json.loads(l) for l in open("results/E-038-audit/b6_ler.jsonl")]
D = {}
for r in rows:
    D.setdefault((r["scale"], r["basis"], r["seed"]), {})[r["circuit"]] = r
for key in sorted(D):
    d = D[key]
    if "kunlun" not in d or "n8" not in d:
        continue
    a, o = d["kunlun"], d["n8"]
    ea, eo = eps(a["fails"] / a["shots"]), eps(o["fails"] / o["shots"])
    la, ha = [eps(x) for x in ci(a["fails"], a["shots"])]
    lo, ho = [eps(x) for x in ci(o["fails"], o["shots"])]
    print(f"scale={key[0]} {key[1]} seed={key[2]} shots={a['shots']}: Kunlun eps={ea:.4g} ({a['fails']})  N8 eps={eo:.4g} "
          f"({o['fails']})  ratio={eo / ea:.3f} [{lo / ha:.3f}, {ho / la:.3f}]")
