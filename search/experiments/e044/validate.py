"""E-044 validation: stratified P_L (per shot, per basis) vs direct sinter counts (BP-OSD IBM parameters, same circuit
text; strong_ids checked for the IBM gross task).  Direct counts (failures, shots), sources:
  E-026 results/E-026-gross-ler/direct/a5_2e-3.csv + a7_low_ub.csv; E-033 results/E-033-gross-u11-ler/direct/*.csv;
  E-040 audit results/E-040-audit-circ/ler.csv; E-044 results/E-044-crossover/anomaly_ibm_2e-3.csv;
  E-030 results/E-030-bb90-period-ler/direct/*.csv (R = 10; sinter max_errors stopping, as run there).
  uv run python -m search.experiments.e044.validate"""
import json

import numpy as np
from scipy.stats import beta

from search.experiments.e044.analysis import PL, q
from search.experiments.e044.common import OUT

DIRECT = {
    ("ibm", "Z", "lam1", 2e-3): {"E-026": (1, 11425), "E-033": (15, 45481), "E-040audit": (2, 60000), "E-044": (21, 100000)},
    ("ibm", "X", "lam1", 2e-3): {"E-026": (1, 11745), "E-033": (6, 50000), "E-040audit": (4, 60000), "E-044": (8, 50000)},
    ("g10", "Z", "lam1", 2e-3): {"E-040audit": (13, 15000)},
    ("g10", "X", "lam1", 2e-3): {"E-040audit": (13, 15000)},
    ("u11", "Z", "lam1", 2e-3): {"E-033": (20, 13964), "E-040audit": (32, 15000)},
    ("u11", "X", "lam1", 2e-3): {"E-033": (22, 14625), "E-040audit": (29, 15000)},
    ("u11", "Z", "lam0", 3e-3): {"E-033": (9, 90000)},
    ("u11", "X", "lam0", 3e-3): {"E-033": (22, 90000)},
    ("ibm", "Z", "lam0", 3e-3): {"E-033": (12, 40000), "E-026b": (3, 15000)},
    ("ibm", "X", "lam0", 3e-3): {"E-033": (12, 40000), "E-026b": (3, 15000)},
    ("ibm90", "Z", "lam1", 2e-3): {"E-030": (50, 89281)},
    ("ibm90", "X", "lam1", 2e-3): {"E-030": (50, 67433)},
    ("ibm90", "Z", "lam1", 1e-3): {"E-030": (21, 1064913)},
    ("ibm90", "X", "lam1", 1e-3): {"E-030": (20, 480849)},
    ("ibm90", "Z", "lam1", 1.5e-3): {"E-030": (43, 300000)},
    ("ibm90", "X", "lam1", 1.5e-3): {"E-030": (50, 280721)},
    ("c11", "Z", "lam1", 2e-3): {"E-030": (50, 10707)},
    ("c11", "X", "lam1", 2e-3): {"E-030": (50, 7029)},
    ("c11", "Z", "lam1", 1.5e-3): {"E-030": (50, 47273)},
    ("c11", "X", "lam1", 1.5e-3): {"E-030": (25, 26617)},
    ("c11", "Z", "lam0", 2e-3): {"E-030": (30, 307657)},
    ("c11", "X", "lam0", 2e-3): {"E-030": (21, 400000)},
    ("ibm90", "Z", "lam0", 2e-3): {"E-030": (30, 192337)},
    ("ibm90", "X", "lam0", 2e-3): {"E-030": (31, 126577)},
    ("c11", "Z", "lam0", 3e-3): {"E-030": (42, 60000)},
    ("c11", "X", "lam0", 3e-3): {"E-030": (43, 60000)},
    ("ibm90", "Z", "lam0", 3e-3): {"E-030": (50, 30341)},
    ("ibm90", "X", "lam0", 3e-3): {"E-030": (50, 32033)},
}


def main(tags=None):
    rows = []
    for (c, b, m, p), src in DIRECT.items():
        f = sum(x[0] for x in src.values()); n = sum(x[1] for x in src.values())
        try:
            s = PL(c, b, m, p, "lo", tags=tags)
            h = PL(c, b, m, p, "hi", tags=tags)
        except Exception as e:  # no stratified data yet
            continue
        r = dict(circ=c, basis=b, model=m, p=p, direct=[f, n, f / n, beta.ppf(.025, f + .5, n - f + .5),
                                                        beta.ppf(.975, f + .5, n - f + .5)],
                 strat_lo=q(s), strat_hi=q(h), ratio_direct_over_strat=f / n / np.median(s), sources=src)
        if len(src) > 1:   # heterogeneity of the direct runs (chi-square on Poisson counts)
            from scipy.stats import chi2
            rate = f / n
            X2 = sum((x[0] - rate * x[1]) ** 2 / (rate * x[1]) for x in src.values())
            r["het_chi2"] = [X2, len(src) - 1, float(chi2.sf(X2, len(src) - 1))]
        rows.append(r)
        print(json.dumps(r), flush=True)
    (OUT / "validate.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
