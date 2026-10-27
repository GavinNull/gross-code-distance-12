"""E-039 audit a0: sanity of my own finite-R core.
(1) code: ranks of the 14 measured checks vs all 18; k; whether the 4 unmeasured checks are in the span of the measured
    ones (if yes, final-readout detectors of the unmeasured checks add no detection power).
(2) controls: Kunlun Fig. S3 schedule (E-036 parse) and E-038's N8 d4 schedule: my min weight at R = 1, 2, 3 both bases,
    reset / no-reset (expected Kunlun 3, N8 none <= 3); noiseless determinism; evaluator template min weight agrees.
usage: uv run python -m search.experiments.e039_audit.a0_sanity"""
import json

import numpy as np

from search.experiments.e036_audit.core import HX_FULL, HZ_FULL
from search.experiments.e039_audit import fcore as F


def tau_from_spec(path):
    d = json.load(open(path))
    tau = {}
    for nm, typ in (("x_checks", "X"), ("z_checks", "Z")):
        for row in d[nm]:
            qs = sorted(q for q, _ in row["cnots"])
            ks = [k for k in F.KS if k[0] == typ and sorted(F.SUPP[k]) == qs]
            assert len(ks) == 1
            k = ks[0]
            for q, t in row["cnots"]:
                tau[(k, F.SUPP[k].index(q))] = t - row["prep"]
    return tau, d["period"] - 2


if __name__ == "__main__":
    for t, Hf in (("X", HX_FULL), ("Z", HZ_FULL)):
        Hm = F.hmat(t)
        print(t, "rank measured", F.rank(Hm), "rank full", F.rank(Hf), "full rows in span:",
              F.rank(np.vstack([Hm, Hf])) == F.rank(Hm))
    print("k =", 18 - F.rank(F.hmat("X")) - F.rank(F.hmat("Z")), "logicals", len(F.logicals("Z")), len(F.logicals("X")))
    for nm, path in (("N8", "search/experiments/e038/bb18_n8_d4_spec.json"),):
        tau, S = tau_from_spec(path)
        print(nm, "S", S, "legal", F.legal(tau, S))
        for R in (1, 2, 3):
            for b in "ZX":
                c, _ = F.circuit(tau, S, b, R)
                d, o = F.fires(c)
                print(nm, R, b, "noiseless fired", d, o, "w(reset)", F.dist(tau, S, b, R), "w(noreset)",
                      F.dist(tau, S, b, R, reset=False), flush=True)
