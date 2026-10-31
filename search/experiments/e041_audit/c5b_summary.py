"""c5b: per-round block error eps (K = 4, R = 6, same saturation formula as E-036/E-038/E-041) and ratios vs Kunlun
with the conservative interval [lo_a/hi_k, hi_a/lo_k].  usage: uv run python -m search.experiments.e041_audit.c5b_summary"""
import json

K, R = 4, 6


def eps(P):
    Pr = 1 - 2.0 ** -K
    return Pr * (1 - (1 - min(P / Pr, 0.999999)) ** (1 / R))


rows = {}
for l in open("results/E-041-audit/c5_ler.jsonl"):
    r = json.loads(l)
    rows[(r["circuit"], r["basis"], r["scale"], r["mapping"])] = r
for s in (1.0, 0.1):
    for b in "ZX":
        k = rows.get(("kunlun", b, s, "kl"))
        if not k:
            continue
        line = [f"x{s} {b}: kunlun eps={eps(k['P']):.4g} ({k['fails']}/{k['shots']})"]
        for m in ("kl", "mix"):
            a = rows.get(("w9", b, s, m))
            if a:
                line.append(f"w9/{m} eps={eps(a['P']):.4g} ratio {eps(a['P'])/eps(k['P']):.3f} "
                            f"[{eps(a['lo'])/eps(k['hi']):.3f}, {eps(a['hi'])/eps(k['lo']):.3f}]")
        print("; ".join(line))
