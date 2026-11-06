"""Item 8: per-round rates at p=2e-3, lambda=1, BP-OSD (R=12, Z+X) and ratios to IBM, with Jeffreys MC intervals.
Counts: g10/u11 from research/audits/2026-10-30-E-040-circuits.md sec. 7 (15,000 shots per basis);
IBM: E-044 audit recommended 1.6e-4 per Z shot (1.4-1.8), X pooled direct 19/171,745 and stratified 1.43e-4
(results/E-044-crossover/validate.json)."""
import numpy as np
rng = np.random.default_rng(1); N = 200000
pr = lambda f: 1 - (1 - f) ** (1 / 12)
jb = lambda k, n: rng.beta(k + .5, n - k + .5, N)
g10 = pr(jb(13, 15000)) + pr(jb(13, 15000)); u11 = pr(jb(32, 15000)) + pr(jb(29, 15000))
for lab, z, x in (("IBM Z=1.6e-4, X direct", 1.6e-4, None), ("IBM Z=1.6e-4, X strat 1.43e-4", 1.6e-4, 1.43e-4),
                  ("IBM Z=1.4e-4", 1.4e-4, None), ("IBM Z=1.8e-4", 1.8e-4, None)):
    ibm = pr(z) + (pr(x) if x else pr(jb(19, 171745)))
    q = lambda a: "%.1f [%.1f, %.1f]" % (np.median(a), *np.percentile(a, [2.5, 97.5]))
    print(f"{lab}: IBM per round {np.median(ibm):.2e}; g10/IBM {q(g10/ibm)}; u11/IBM {q(u11/ibm)}")
print("g10 %.3g, u11 %.3g per round (point)" % (2 * pr(13 / 15000), pr(32 / 15000) + pr(29 / 15000)))
