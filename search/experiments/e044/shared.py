"""E-044: lam0 gross g10 vs ibm with too few failures for separate fits.  Under lam0 the two DEMs have the same
mechanism-probability multiset (mass 9.836 at 1e-3 for both, probe.jsonl), so P_p(K = k) is the same for both
circuits and the per-round ratio is sum_k P(k) f_k^g / sum_k P(k) f_k^I.  Model: f_k = exp(a_c) k^b with a COMMON
exponent b (binomial MLE over all strata with fhat <= 0.02, both bases pooled per circuit with separate amplitudes
per basis); the ratio is then exp(a_g - a_I) per basis, p-independent.  Profile-likelihood 95% interval on
delta = a_g - a_I (chi2_1 = 3.84).  Also reported: plain pooled counts at matched k.
  uv run python -m search.experiments.e044.shared g10 ibm lam0"""
import json
import sys

import numpy as np
from scipy.optimize import minimize

from search.experiments.e044.analysis import counts
from search.experiments.e044.common import jdump


def data(c, b, m):
    cnt = counts(c, b, m)
    ks = np.array([k for k in sorted(cnt) if (cnt[k][1] + .5) / (cnt[k][0] + 1) <= 0.02])
    return ks, np.array([cnt[k][0] for k in ks], float), np.array([cnt[k][1] for k in ks], float)


def main(g, i, m):
    D = {(c, b): data(c, b, m) for c in (g, i) for b in "ZX"}

    def nll(th, delta=None):
        aZ, aX, b = th[:3]
        d = th[3] if delta is None else delta
        s = 0.0
        for (c, bb), (ks, n, f) in D.items():
            a = (aZ if bb == "Z" else aX) + (d if c == g else 0.0)
            lphi = np.minimum(a + b * np.log(ks), -1e-9)
            s -= np.sum(f * lphi + (n - f) * np.log1p(-np.exp(lphi)))
        return s
    x0 = [-30.0, -30.0, 6.0, 0.0]
    r = minimize(nll, x0, method="Nelder-Mead", options=dict(maxiter=40000, xatol=1e-9, fatol=1e-10))
    best = r.fun
    prof = []
    for d in np.linspace(-6, 4, 201):
        rr = minimize(lambda t: nll(t, d), r.x[:3], method="Nelder-Mead", options=dict(maxiter=20000))
        prof.append((d, rr.fun - best))
    inside = [d for d, v in prof if 2 * v <= 3.84]
    tot = {f"{c}{b}": [int(D[(c, b)][1].sum()), int(D[(c, b)][2].sum())] for c in (g, i) for b in "ZX"}
    rec = dict(pair=f"{g}/{i}", model=m, b=float(r.x[2]), ratio=float(np.exp(r.x[3])),
               ratio_95=[float(np.exp(min(inside))) if inside else None, float(np.exp(max(inside))) if inside else None],
               edge_hit=bool(inside and (min(inside) <= -6 or max(inside) >= 4)), shots_fails=tot)
    jdump(rec, "shared.jsonl")


if __name__ == "__main__":
    main(*sys.argv[1:4])
