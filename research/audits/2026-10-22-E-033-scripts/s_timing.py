"""Auditor E-033: per-shot decode time of the own pipeline (lam 0, p 3e-3, R 12), 200 shots each, seed 33299999."""
import sys, time, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["OMP_NUM_THREADS"] = "1"
import numpy as np
import s_sample as S
for circ in ("u11", "ibm", "fig12"):
    for b in "ZX":
        dem, Lm, dec = S.setup(0.0, 0.003, circ, b)
        det, obs, _ = dem.compile_sampler(seed=33299999).sample(200)
        t0 = time.process_time(); f = 0
        for s in range(200):
            f += bool(((Lm @ dec.decode(det[s].astype(np.uint8))) % 2 != obs[s]).any())
        print(circ, b, "s/shot", round((time.process_time() - t0) / 200, 4), "fails", f, flush=True)
