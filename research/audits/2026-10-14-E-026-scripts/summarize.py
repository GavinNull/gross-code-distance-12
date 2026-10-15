"""Auditor E-026: combine own samples, Jeffreys MC intervals, ratio p18/ibm and p18/fig12 at 2e-3, decoder-limited stats."""
import glob, json, statistics as st
import numpy as np
from pathlib import Path
OUT = Path(__file__).resolve().parents[3] / "results/E-026-audit"
rng = np.random.default_rng(0); N = 200000
S = {}
for f in glob.glob(str(OUT / "sample_*.json")):
    if "_timing" in f: continue
    d = json.load(open(f)); S[(d["circ"], d["basis"], d["p"])] = d
def draw(d):
    P = rng.beta(d["fails"] + .5, d["shots"] - d["fails"] + .5, N); return 1 - (1 - P) ** (1 / d["R"])
out = {}
for k, d in sorted(S.items()):
    r = [x for x in d["fail_records"] if "w_corr" in x]; g = [x["w_corr"] - x["w_true"] for x in r]
    e = draw(d)
    out["%s_%s_%g" % k] = dict(shots=d["shots"], fails=d["fails"], eps=d["per_round"], ci=list(np.percentile(e, [2.5, 97.5])),
        lam=d["lam"], decoder_limited=d["n_decoder_limited"], code_limited=d["n_code_limited"],
        gap_median=st.median(g) if g else None, cpu=d["cpu"])
    print(k, out["%s_%s_%g" % k])
p = 0.002
p18 = draw(S[("p18", "Z", p)]) + draw(S[("p18", "X", p)])
ibm = draw(S[("ibm", "Z", p)]) + draw(S[("ibm", "X", p)])
fz = draw(S[("fig12", "Z", p)])
pz = draw(S[("p18", "Z", p)]); iz = draw(S[("ibm", "Z", p)])
for nm, v in (("p18_ZX/ibm_ZX", p18 / ibm), ("p18_Z/fig12_Z", pz / fz), ("p18_Z/ibm_Z", pz / iz), ("fig12_Z/ibm_Z", fz / iz)):
    out[nm] = [float(np.median(v))] + list(np.percentile(v, [2.5, 97.5])); print(nm, out[nm])
out["p18_ZX_eps"] = float(np.median(p18)); out["ibm_ZX_eps"] = float(np.median(ibm))
(OUT / "summary.json").write_text(json.dumps(out, indent=1, default=float))
