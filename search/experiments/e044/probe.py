"""E-044 structural probe (no failure counts looked at): DEM size, prior mass, p-independence of the conditional
law, and BP-OSD decode time per shot vs fault count k.
  uv run python -m search.experiments.e044.probe"""
import time

import numpy as np

from search.experiments.e044.common import ROUNDS, CODEFAM, noisy, sinter_dem, jdump
from search.experiments.e044.strat import Stratum, mechanisms

for circ in ("ibm", "g10", "u11", "ibm90", "c11"):
    for model in ("lam1", "lam0"):
        for basis in ("Z", "X"):
            rec = dict(circ=circ, model=model, basis=basis, R=ROUNDS[CODEFAM[circ]])
            q1, d1, _ = mechanisms(sinter_dem(noisy(circ, basis, 1e-3, model)))
            c = noisy(circ, basis, 1e-3, model)
            try:
                c.detector_error_model(decompose_errors=True, approximate_disjoint_errors=True)
                rec["sinter_dem"] = "decomposed"
            except ValueError:
                rec["sinter_dem"] = "flat"
            rec.update(M=len(q1), D=c.num_detectors, mass_1e3=float(q1.sum()))
            for p in (2e-3, 5e-4, 3e-4):
                qp, dp, _ = mechanisms(sinter_dem(noisy(circ, basis, p, model)))
                assert dp == d1
                wr = (qp / (1 - qp)) / (q1 / (1 - q1)) / (p / 1e-3)
                rec[f"wdev_{p:g}"] = float(np.max(np.abs(wr - 1)))
            if basis == "Z":
                st = Stratum(circ, basis, model)
                rng = np.random.default_rng(1)
                for k in (6, 12, 24, 40):
                    S = st.sample(k, 15, rng)
                    t0 = time.process_time()
                    for s in S:
                        st.decode_fail(s)
                    rec[f"sec_k{k}"] = round((time.process_time() - t0) / 15, 4)
            jdump(rec, "probe.jsonl")
