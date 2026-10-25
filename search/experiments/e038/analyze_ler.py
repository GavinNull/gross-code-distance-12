"""E-038: LER summary (same per-round block-error formula and conservative ratio interval as e036/analyze_ler.py)."""
import json

K, R = 4, 6


def eps(P):
    Pr = 1 - 2.0 ** -K
    return Pr * (1 - (1 - min(P / Pr, 0.999999)) ** (1 / R))


rows = {}
for l in open("results/E-038-bb18-d4/ler.jsonl"):
    r = json.loads(l)
    rows[(r["circuit"], r["basis"], r["scale"])] = r
ours = "search/experiments/e038/bb18_n8_d4_spec.json"
out = []
for s in (1.0, 0.1):
    for b in ("Z", "X"):
        a, k = rows[(ours, b, s)], rows[("kunlun", b, s)]
        ea, lo_a, hi_a = eps(a["P"]), eps(a["lo"]), eps(a["hi"])
        ek, lo_k, hi_k = eps(k["P"]), eps(k["lo"]), eps(k["hi"])
        out.append(f"scale={s} {b}: Kunlun eps={ek:.4g} [{lo_k:.4g},{hi_k:.4g}] ({k['fails']}/{k['shots']}); "
                   f"n8 eps={ea:.4g} [{lo_a:.4g},{hi_a:.4g}] ({a['fails']}/{a['shots']}); "
                   f"ratio n8/Kunlun {ea / ek:.3f} [{lo_a / hi_k:.3f}, {hi_a / lo_k:.3f}]")
print("\n".join(out))
open("results/E-038-bb18-d4/ler_summary.txt", "w").write("\n".join(out) + "\n")
