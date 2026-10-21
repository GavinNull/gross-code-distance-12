"""A8: recompute the experimenter's lam0 BP-OSD/Relay ratios c11/ibm from the raw sinter csv (own parsing, own
Jeffreys MC, seed 777).   uv run python research/audits/2026-10-22-E-030-scripts/a8_recheck_csv.py"""
import csv, glob, json
from collections import defaultdict
import numpy as np
agg = defaultdict(lambda: [0, 0])
for f in glob.glob("results/E-030-bb90-period-ler/direct/*.csv"):
    if f.endswith("timing.csv"): continue
    for row in csv.DictReader(open(f), skipinitialspace=True):
        m = json.loads(row["json_metadata"])
        if m["R"] != 10: continue
        k = (m["noise"], m["circ"], m["p"], row["decoder"].strip(), m["basis"])
        agg[k][0] += int(row["shots"]); agg[k][1] += int(row["errors"])
rng = np.random.default_rng(777); R = 10; NS = 200000
def draws(nz, c, p, dec):
    t = 0
    for b in "ZX":
        n, k = agg[(nz, c, p, dec, b)]
        t = t + 1 - (1 - rng.beta(k + .5, n - k + .5, NS)) ** (1 / R)
    return t
out = {}
for nz in ("lam0", "lam0.1", "lam1"):
    for dec in ("bposd", "relay5"):
        for p in (0.005, 0.004, 0.003, 0.002, 0.0015):
            if not all((nz, c, p, dec, b) in agg for c in ("c11", "ibm") for b in "ZX"): continue
            r = draws(nz, "c11", p, dec) / draws(nz, "ibm", p, dec)
            cnt = {c: [agg[(nz, c, p, dec, b)] for b in "ZX"] for c in ("c11", "ibm")}
            out[f"{nz} {dec} {p}"] = [float(np.median(r)), *map(float, np.quantile(r, [.025, .975]))]
            print(nz, dec, p, cnt, [round(x, 3) for x in out[f"{nz} {dec} {p}"]])
json.dump(out, open("results/E-030-audit/a8_recheck_csv.json", "w"), indent=1)
