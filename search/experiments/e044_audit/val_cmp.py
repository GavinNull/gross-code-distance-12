"""compare val_cond.jsonl (unconditional samples binned by K) with the E-044 strata at the same k."""
import json
import numpy as np
from scipy.stats import chi2
from search.experiments.e044_audit.robust import counts, OUT

for ln in open(OUT / "val_cond.jsonl"):
    r = json.loads(ln)
    C = counts(r["circ"], r["basis"], r["model"])
    pk = {int(k): v for k, v in r["per_k"].items()}
    n = sum(v[0] for v in pk.values())
    print(r["circ"], r["basis"], r["model"], r["p"], "shots", n, "fails pdec1e-3", r["fails_pdec1e3"], "pdec=p", r["fails_pdecp"], "sec", r["sec"])
    bins = [(0, 12), (13, 15), (16, 18), (19, 21), (22, 24), (25, 28), (29, 200)]
    X2 = 0; dof = 0
    for lo, hi in bins:
        nn = sum(pk[k][0] for k in pk if lo <= k <= hi); ff = sum(pk[k][1] for k in pk if lo <= k <= hi)
        # expected from E-044 strata per k (interpolate missing k by nearest sampled)
        exp = 0.0
        for k in pk:
            if lo <= k <= hi:
                kk = min(C, key=lambda x: abs(x - k)); a, b = C[kk]
                exp += pk[k][0] * (b + .5) / (a + 1)
        X2 += (ff - exp) ** 2 / max(exp, 1e-9); dof += 1
        print(f"  K {lo}-{hi}: shots {nn} fails {ff} expected-from-E044-f_k {exp:.1f}  (pdec=p fails {sum(pk[k][2] for k in pk if lo <= k <= hi)})")
    print("  chi2", round(X2, 2), "dof", dof, "p", round(float(chi2.sf(X2, dof)), 3))
    print("  P_L post-stratified %.2e (pdec 1e-3), %.2e (pdec=p)" % (r["fails_pdec1e3"] / n, r["fails_pdecp"] / n))
