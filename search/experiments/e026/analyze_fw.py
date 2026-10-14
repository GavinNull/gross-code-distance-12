"""E-026: fixed-weight failure table f_w (Jeffreys 95% intervals), per circuit/basis/decoder.
  uv run python -m search.experiments.e026.analyze_fw [tag]"""
import glob, json, re, sys
from collections import defaultdict
import numpy as np
from scipy.stats import beta
from search.experiments.e026.common import OUT

tag = sys.argv[1] if len(sys.argv) > 1 else "fw"
agg = defaultdict(lambda: defaultdict(lambda: [0, 0])); cpu = 0.0
for f in glob.glob(str(OUT / tag / "*.npz")):
    m = re.match(r".*/(\w+?)_([ZX])_R(\d+)_w(\d+)_b\d+\.npz", f)
    d = np.load(f); cpu += float(d["cpu"])
    for dec in ("bposd", "relay5"):
        a = agg[(m.group(1), dec)][int(m.group(4))]
        a[0] += int(d["n"]); a[1] += int(d[f"fail_{dec}"].sum())
out = {}
for (c, dec), byw in sorted(agg.items()):
    row = {}
    for w in sorted(byw):
        n, k = byw[w]
        lo = beta.ppf(0.025, k + 0.5, n - k + 0.5) if k > 0 else 0.0
        hi = beta.ppf(0.975, k + 0.5, n - k + 0.5)
        row[w] = dict(n=n, fail=k, f=k / n, lo=float(lo), hi=float(hi))
    out[f"{c}_{dec}"] = row
    print(f"{c:5s} {dec:6s} " + "  ".join(f"w{w}:{v['fail']}/{v['n']}" for w, v in row.items()))
print("cpu", round(cpu))
(OUT / f"{tag}_table.json").write_text(json.dumps(out, indent=1))
