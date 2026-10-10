"""Audit E-023 (d): recount fixed-weight MC tables from the raw npz files."""
import glob, re, json, numpy as np
from collections import defaultdict
out = {}
for prob in ("m54_paper", "m54_repo", "bb108_ibm", "bb108_twocolour"):
    for region, pat in (("full", f"{prob}_sd6_w*_b*.npz"), ("bulk", f"{prob}_sd6_bulk_w*_b*.npz")):
        cnt = defaultdict(lambda: [0, 0])
        for f in glob.glob("results/E-023-ler-benefit/fw/" + pat):
            z = np.load(f); w = int(z["w"])
            for s in "ZX":
                for d in ("bposd", "relay"):
                    k = f"{s}_{d}_f"
                    if k in z:
                        c = cnt[(d, s, w)]; c[0] += int(z[k].sum()); c[1] += len(z[k])
        if cnt:
            out[f"{prob}_{region}"] = {f"{d}_{s}_w{w}": f"{k}/{n}" for (d, s, w), (k, n) in sorted(cnt.items())}
            print(prob, region, out[f"{prob}_{region}"])
json.dump(out, open("results/E-023-audit/a5_counts.json", "w"), indent=1)
