"""Auditor E-033 claims 1-2: re-aggregate the raw sinter csvs with the csv module (no sinter, no e033.analyze),
per-round eps_b = 1-(1-k/n)^(1/12), eps = eps_Z + eps_X, Jeffreys beta MC (seed 3303, 200k draws), ratios from the
same draws.  Also: (a) the 3e-3 lam0 BP-OSD u11/ibm ratio at the pre-specified cap (stage-2 counts, from stage2.log),
(b) the extension segment alone, (c) one lam=1 spot check printed with raw counts."""
import csv, glob, json
from collections import defaultdict
import numpy as np
ROOT = "/Users/ephemeral/Desktop/qec-ai-search/"
R = 12; NS = 200000
rng = np.random.default_rng(3303)
agg = defaultdict(lambda: [0, 0])
files = glob.glob(ROOT + "results/E-033-gross-u11-ler/direct/*.csv") + glob.glob(ROOT + "results/E-026-gross-ler/direct/*.csv") + glob.glob(ROOT + "results/E-026b-idle-sensitivity/direct/*.csv")
for f in files:
    for row in csv.DictReader(open(f), skipinitialspace=True):
        m = json.loads(row["json_metadata"])
        if m.get("R") != 12 or m["circ"] not in ("u11", "ibm", "fig12"): continue
        nz = m.get("noise", "lam1"); nz = "lam1" if nz == "sd6" else nz
        k = (nz, m["circ"], m["p"], row["decoder"].strip(), m["basis"])
        agg[k][0] += int(row["shots"]); agg[k][1] += int(row["errors"])

def draws(counts):
    t = 0; pt = 0
    for n, k in counts:
        t = t + 1 - (1 - rng.beta(k + .5, n - k + .5, NS)) ** (1 / R); pt += 1 - (1 - k / n) ** (1 / R)
    return t, pt

def q(x): return [float(v) for v in np.quantile(x, [.025, .975])]
def ratio(a, b):
    ta, pa = draws(a); tb, pb = draws(b)
    return [pa / pb if pb else None] + q(ta / tb)

out = {}
for nz, p, dec in [("lam0", .005, "bposd"), ("lam0", .005, "relay5"), ("lam0", .004, "bposd"), ("lam0", .004, "relay5"),
                   ("lam0", .003, "bposd"), ("lam0", .003, "relay5"), ("lam0.1", .004, "bposd"), ("lam0.1", .004, "relay5"),
                   ("lam0.1", .003, "bposd"), ("lam1", .003, "bposd"), ("lam1", .003, "relay5"), ("lam1", .002, "bposd"), ("lam1", .002, "relay5")]:
    g = lambda c: [tuple(agg[(nz, c, p, dec, b)]) for b in "ZX"]
    u, i, f = g("u11"), g("ibm"), g("fig12")
    r = dict(u11=u, ibm=i, fig12=f)
    if all(n for n, k in i): r["u11/ibm"] = ratio(u, i)
    if all(n for n, k in f): r["u11/fig12"] = ratio(u, f)
    out[f"{nz} {p} {dec}"] = r
    print(f"{nz:6s} {p} {dec:6s} u11 {u} ibm {i} fig12 {f}", {k: [round(x, 3) if x else x for x in v] for k, v in r.items() if "/" in k})
# (a) at the pre-specified cap: u11 Z 7/40000, X 10/40000 (stage2.log); ibm stage-2 Z 12/34852, X 12/23001 + E-026b 3/15000, 3/15000
old_ibm = [(15000, 3), (15000, 3)]
cap = ratio([(40000, 7), (40000, 10)], [(34852 + 15000, 15), (23001 + 15000, 15)])
ext = ratio([(50000, 2), (50000, 12)], [(40000, 12), (40000, 12)])
fin = ratio([(90000, 9), (90000, 22)], [(74852 + 15000, 27), (63001 + 15000, 27)])
print("3e-3 BP-OSD u11/ibm at cap", cap, "extension segment only", ext, "final", fin)
out["interim_cap"] = cap; out["extension_only"] = ext; out["final"] = fin
json.dump(out, open(ROOT + "results/E-033-audit/r1_recheck_csv.json", "w"), indent=1)
