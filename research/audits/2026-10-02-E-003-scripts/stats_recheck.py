"""Recompute E-003 per-point ratios, Fisher tests and the CMH test from raw counts (stats.csv of E-003 / E-002)."""
import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[3]
import sinter  # noqa: E402


def agg(csv, sched_filter=None):
    out = {}
    for s in sinter.read_stats_from_csv_files(str(csv)):
        m = s.json_metadata
        k = (m["basis"], m["p"])
        out[k] = out[k] + s if k in out else s
    return {k: (v.errors, v.shots) for k, v in out.items()}


S = agg(ROOT / "results/E-003-strikis-gross/stats.csv")
I = agg(ROOT / "results/E-002-gross-baseline/stats.csv")
pr = lambda P, n=12: 1 - (1 - P) ** (1 / n)  # noqa: E731
rows, tables = [], []
for k in sorted(S):
    if k not in I:
        continue
    es, ns = S[k]; ei, ni = I[k]
    ratio = pr(es / ns) / pr(ei / ni)
    odds, pf = stats.fisher_exact([[es, ns - es], [ei, ni - ei]])
    rows.append({"basis": k[0], "p": k[1], "strikis": [es, ns], "ibm": [ei, ni], "ratio_per_round": round(ratio, 3),
                 "fisher_p": round(pf, 4)})
    tables.append(np.array([[es, ns - es], [ei, ni - ei]]))
for r in rows:
    print(r)
st = stats.contingency.odds_ratio  # noqa: F841

def cmh(tabs):
    num=den=dev=var=0.0
    for t in tabs:
        a,b=t[0]; c,d=t[1]; n=a+b+c+d
        num+=a*d/n; den+=b*c/n
        r1=a+b; r0=c+d; c1=a+c; c0=b+d
        dev+=a-r1*c1/n; var+=r1*r0*c1*c0/(n*n*(n-1))
    chi=dev**2/var
    return {"MH_OR":num/den,"chi2":chi,"p":float(stats.chi2.sf(chi,1))}
print("CMH all 6:",cmh(tables))
print("CMH p>=0.004:",cmh([t for t,r in zip(tables,rows) if r["p"]>=0.004]))
print("CMH p=0.005:",cmh([t for t,r in zip(tables,rows) if r["p"]==0.005]))
