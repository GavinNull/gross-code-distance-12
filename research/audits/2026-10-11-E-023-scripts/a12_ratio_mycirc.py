"""Audit E-023: per-round LER (T = 8 full circuit) and paper/repo ratio from a11 counts (natural detector basis)."""
import sys, json
import numpy as np
sys.path.insert(0, 'research/audits/2026-10-11-E-023-scripts')
from a9_ratio import build
rng = np.random.default_rng(7)
def curve(var, dec, mode, nb=400):
    tc, tb = 0, 0
    for b in "ZX":
        D = json.load(open(f"results/E-023-audit/a11_{var}_{b}.json"))
        import os
        fb = f"results/E-023-audit/a11_{var}_{b}_big.json"
        if os.path.exists(fb) and "nobig" not in sys.argv:
            for w, r in json.load(open(fb))["grid"].items():
                g = D["grid"].setdefault(w, {dd: dict(k=0, n=0) for dd in ("bposd", "relay")})
                for dd in ("bposd", "relay"):
                    g[dd]["k"] += r[dd]["k"]; g[dd]["n"] += r[dd]["n"]
        P = sorted(float(p) for p in D["pis"]); pis = [np.array(D["pis"][str(p)]) for p in P]
        ws = np.array(sorted(int(w) for w in D["grid"])); k = np.array([D["grid"][str(w)][dec]["k"] for w in ws])
        n = np.array([D["grid"][str(w)][dec]["n"] for w in ws])
        fc = build(ws, np.maximum(k / n, 1e-12), mode)
        tc = tc + np.array([(pi * fc).sum() for pi in pis])
        tb = tb + np.array([[(pi * build(ws, rng.beta(k + .5, n - k + .5), mode)).sum() for pi in pis] for _ in range(nb)])
    pr = lambda x: 1 - (1 - np.minimum(x, .999)) ** (1 / 8)
    return P, pr(tc), pr(tb)
out = {}
for dec in ("bposd", "relay"):
    for mode in ("loglog", "lin"):
        P, cl, bl = curve("paper", dec, mode); _, ch, bh = curve("repo", dec, mode); R = bl / bh
        lo, hi = np.percentile(R, 2.5, 0), np.percentile(R, 97.5, 0)
        out[f"{dec}|{mode}"] = dict(p=P, paper=cl.tolist(), repo=ch.tolist(), ratio=(cl / ch).tolist(), lo=lo.tolist(), hi=hi.tolist())
        print(dec, mode)
        for i, p in enumerate(P):
            print(f"   p={p:.0e} paper {cl[i]:.2e} repo {ch[i]:.2e} ratio {cl[i]/ch[i]:.2f} [{lo[i]:.2f}, {hi[i]:.2f}]")
json.dump(out, open("results/E-023-audit/a12_ratio_mycirc%s.json" % ("_small" if "nobig" in sys.argv else ""), "w"), indent=1)
