"""E-036: LER summary.  Block failure P at R rounds (Z or X memory, all k observables jointly), Jeffreys 95%.
Per-round block error (saturation-corrected, k logical qubits, P_rand = 1 - 2^-k):
    eps = P_rand * (1 - (1 - P / P_rand)^(1/R))       (monotone in P, so the CI maps through)
Ratios ours/theirs of eps with a 95% interval from the two independent Jeffreys intervals (conservative:
lo = eps_lo(ours)/eps_hi(theirs), hi = eps_hi(ours)/eps_lo(theirs))."""
import json
from collections import defaultdict

from search.experiments.e036.common import OUT

K = {"bb18": 4, "q1863": 6}
NAME = {"kunlun": "Kunlun (P9, 7 CNOT layers)",
        "search/experiments/e036/q1863_p8_spec.json": "ours q1863_p8 (P8, 6 CNOT layers)",
        "search/experiments/e036/bb18_p8_d3_spec.json": "ours bb18_p8_d3 (P8, 6 CNOT layers)"}


def eps(P, k, R):
    Pr = 1 - 2.0 ** -k
    x = min(P / Pr, 0.999999)
    return Pr * (1 - (1 - x) ** (1 / R))


rows = [json.loads(l) for l in open(OUT / "ler.jsonl")]
seen = {}
for r in rows:
    seen[(r["variant"], r["circuit"], r["basis"], r["scale"], r["R"])] = r
tab = defaultdict(dict)
lines = []
for (v, c, b, s, R), r in sorted(seen.items()):
    k = K[v]
    e, lo, hi = eps(r["P"], k, R), eps(r["lo"], k, R), eps(r["hi"], k, R)
    tab[(v, b, s)][c] = (e, lo, hi, r)
    lines.append(f"{v:6s} {b} scale={s:<4} {NAME.get(c, c):40s} P={r['P']:.4f} [{r['lo']:.4f},{r['hi']:.4f}] "
                 f"({r['fails']}/{r['shots']})  eps/round={e:.4f} [{lo:.4f},{hi:.4f}]")
lines.append("")
for (v, b, s), d in sorted(tab.items()):
    if "kunlun" not in d:
        continue
    for c, (e, lo, hi, r) in d.items():
        if c == "kunlun":
            continue
        e0, lo0, hi0, _ = d["kunlun"]
        lines.append(f"ratio ours/kunlun {v} {b} scale={s}: {e / e0:.3f} [{lo / hi0:.3f}, {hi / lo0:.3f}]  ({NAME.get(c, c)})")
txt = "\n".join(lines)
print(txt)
(OUT / "ler_summary.txt").write_text(txt + "\n")
