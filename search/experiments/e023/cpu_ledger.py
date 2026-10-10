"""E-023: CPU ledger from the self-recorded cpu fields (fw/direct npz, splits summaries, lowweight runs + closure)."""
import glob
import json

import numpy as np

from search.experiments.e023.common import OUT

tot = {}
for f in glob.glob(str(OUT / "fw" / "*.npz")) + glob.glob(str(OUT / "direct" / "*.npz")):
    z = np.load(f)
    k = ("direct" if "/direct/" in f else "fw") + ":" + f.split("/")[-1].split("_")[0] + "_" + f.split("/")[-1].split("_")[1]
    tot[k] = tot.get(k, 0) + float(z["cpu"])
for f in glob.glob(str(OUT / "splits" / "*summary*.json")):
    d = json.load(open(f))
    k = "splits:" + f.split("/")[-1].split("_summary")[0]
    tot[k] = tot.get(k, 0) + float(d.get("cpu", 0))
for f in glob.glob(str(OUT / "lowweight" / "*.json")):
    d = json.load(open(f))
    k = "lowweight:" + f.split("/")[-1][:-5]
    tot[k] = sum(r.get("cpu", 0) for r in d.get("runs", [])) + sum(d.get("closure_cpu", []))
for k in sorted(tot):
    print(f"{k:40s} {tot[k] / 3600:7.2f} h")
print(f"{'TOTAL recorded':40s} {sum(tot.values()) / 3600:7.2f} h")
