"""E-044 audit (item 2): independent check of the fixed-k conditional sampler.  Unconditional Bernoulli sampling of
the unmerged flat DEM mechanisms at p (own code; conditioning on K = k of an unconditional sample is exactly the
conditional law, no tilting), every shot decoded by BP-OSD (IBM parameters) with prior p_dec = 1e-3 (as strat.py)
and with prior p (as sinter).  Output per-k (n, fails_pdec1e-3, fails_pdecp) for comparison with strat counts, and
the post-stratified P_L vs sinter direct counts.
  PYTHONPATH=.:tests uv run python -m search.experiments.e044_audit.val_cond c11 Z lam1 0.002 40000 seed"""
import json
import sys
import time
from collections import defaultdict

import numpy as np
from scipy.sparse import csc_matrix
from stimbposd import BPOSD

from search.experiments.e044.common import IBM_BPOSD, ROOT, noisy

OUT = ROOT / "results" / "E-044-audit"


def main(circ, basis, model, p, n, seed):
    p, n, seed = float(p), int(n), int(seed)
    dem = noisy(circ, basis, p, model).detector_error_model(approximate_disjoint_errors=True)
    q, rows, cols, orows, ocols = [], [], [], [], []
    for i, e in enumerate(e for e in dem.flattened() if e.type == "error"):
        q.append(e.args_copy()[0])
        for t in e.targets_copy():
            if t.is_relative_detector_id():
                rows.append(t.val); cols.append(i)
            elif t.is_logical_observable_id():
                orows.append(t.val); ocols.append(i)
    q = np.array(q); M = len(q)
    H = csc_matrix((np.ones(len(rows), np.uint8), (rows, cols)), shape=(dem.num_detectors, M))
    L = csc_matrix((np.ones(len(orows), np.uint8), (orows, ocols)), shape=(dem.num_observables, M))
    d1 = BPOSD(noisy(circ, basis, 1e-3, model).detector_error_model(approximate_disjoint_errors=True), **IBM_BPOSD)
    dp = BPOSD(dem, **IBM_BPOSD)
    rng = np.random.default_rng([seed, 44])
    acc = defaultdict(lambda: [0, 0, 0])
    t0 = time.time()
    done = 0
    while done < n:
        B = min(2000, n - done)
        X = (rng.random((B, M)) < q).astype(np.uint8)
        syn = (H @ X.T % 2).T.astype(np.uint8)
        lo = (L @ X.T % 2).T.astype(np.uint8)
        ks = X.sum(1)
        for i in range(B):
            a = acc[int(ks[i])]
            a[0] += 1
            a[1] += bool(np.any(d1.decode(syn[i]) != lo[i]))
            a[2] += bool(np.any(dp.decode(syn[i]) != lo[i]))
        done += B
    rec = dict(circ=circ, basis=basis, model=model, p=p, n=n, seed=seed, sec=round(time.time() - t0),
               per_k={k: v for k, v in sorted(acc.items())},
               fails_pdec1e3=sum(v[1] for v in acc.values()), fails_pdecp=sum(v[2] for v in acc.values()))
    with open(OUT / "val_cond.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps({k: v for k, v in rec.items() if k != "per_k"}))


if __name__ == "__main__":
    main(*sys.argv[1:7])
