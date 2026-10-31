"""E-041 LER summary: per-round block error eps (same formula and conservative ratio interval as e038/analyze_ler.py,
K = 4 logical qubits, R = 6) for w9 (kl and klmix mappings), n8 and Kunlun; ratios vs Kunlun (fresh samples, seed
20261031).  usage: uv run python -m search.experiments.e041.analyze_ler"""
import json

K, R = 4, 6
W9 = "search/experiments/e041/bb18_w9_d4_spec.json"
N8 = "search/experiments/e038/bb18_n8_d4_spec.json"


def eps(P):
    Pr = 1 - 2.0 ** -K
    return Pr * (1 - (1 - min(P / Pr, 0.999999)) ** (1 / R))


rows = {}
for l in open("results/E-041-bb18-p9/ler.jsonl"):
    r = json.loads(l)
    rows[(r["circuit"], r["basis"], r["scale"], r["mapping"])] = r
out = []
for s in (1.0, 0.1):
    for b in ("Z", "X"):
        k = rows.get(("kunlun", b, s, "kl"))
        if not k:
            continue
        ek, lo_k, hi_k = eps(k["P"]), eps(k["lo"]), eps(k["hi"])
        line = [f"scale={s} {b}: Kunlun eps={ek:.4g} [{lo_k:.4g},{hi_k:.4g}]"]
        for nm, key in (("w9/kl", (W9, b, s, "kl")), ("w9/klmix", (W9, b, s, "klmix")), ("n8/kl", (N8, b, s, "kl"))):
            a = rows.get(key)
            if not a:
                continue
            ea, lo_a, hi_a = eps(a["P"]), eps(a["lo"]), eps(a["hi"])
            line.append(f"{nm} eps={ea:.4g} ratio {ea / ek:.3f} [{lo_a / hi_k:.3f}, {hi_a / lo_k:.3f}]")
        out.append("; ".join(line))
print("\n".join(out))
open("results/E-041-bb18-p9/ler_summary.txt", "w").write("\n".join(out) + "\n")
