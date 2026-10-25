"""Summarise audit LER (a5_ler.jsonl, 100k-shot rows) as per-round block error and ours/Kunlun ratios."""
import json
from scipy.stats import beta
K = {"bb18": 4, "q1863": 6}
rows = [json.loads(l) for l in open("results/E-036-audit/a5_ler.jsonl") if '"shots": 100000' in l and '"iters": 100,' in l]
def eps(P, k, R=6):
    Pr = 1 - 2 ** -k
    return Pr * (1 - (1 - min(P, Pr * 0.999999) / Pr) ** (1 / R))
def ci(f, n):
    return beta.ppf(0.025, f + .5, n - f + .5), beta.ppf(0.975, f + .5, n - f + .5)
D = {(r["variant"], r["circuit"], r["basis"], r["scale"]): r for r in rows}
out = []
for v, ours in (("bb18", "bb18_p8_d3"), ("q1863", "q1863_p8")):
    for sc in (1.0, 0.1):
        for b in ("Z", "X"):
            a, o = D[(v, "kunlun", b, sc)], D[(v, ours, b, sc)]
            k = K[v]
            ea, eo = eps(a["P"], k), eps(o["P"], k)
            la, ha = [eps(x, k) for x in ci(a["fails"], a["shots"])]
            lo, ho = [eps(x, k) for x in ci(o["fails"], o["shots"])]
            s = f"{v:6s} {b} scale={sc}: Kunlun P={a['P']:.4f} eps={ea:.4g}  ours P={o['P']:.4f} eps={eo:.4g}  ratio={eo/ea:.3f} [{lo/ha:.3f},{ho/la:.3f}]"
            print(s); out.append(s)
open("results/E-036-audit/a5_ler_summary.txt", "w").write("\n".join(out) + "\n")
