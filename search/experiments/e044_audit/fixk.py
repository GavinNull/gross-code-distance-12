"""E-044 audit (items 2 and 5): own exact fixed-k sampler (sequential sampling from elementary-symmetric-polynomial
suffix tables, a different algorithm from strat.py's tilted-Bernoulli + rejection) on the unmerged flat DEM at
p_ref = 1e-3; decode with BP-OSD IBM parameters (prior 1e-3, as strat.py).  Gives f_k for comparison with the E-044
strata.  For each failure: prior log-likelihood of the true error E vs the BP-OSD correction C (decoder's merged
columns and priors) and a re-decode with stronger OSD (osd_cs order 40 and osd_e order 10, same BP) -- does a
better approximation to MLE recover the right logical class?
  PYTHONPATH=.:tests uv run python -m search.experiments.e044_audit.fixk c11 Z lam1 16 30000 seed"""
import json
import sys
import time

import numpy as np
from ldpc import BpOsdDecoder
from scipy.sparse import csc_matrix
from scipy.special import logsumexp
from stimbposd import BPOSD

from search.experiments.e044.common import IBM_BPOSD, ROOT, noisy

OUT = ROOT / "results" / "E-044-audit"


def sampler(w, k):
    """log suffix table: L[i, j] = log e_j(w_i..w_{M-1})"""
    M = len(w); lw = np.log(w)
    L = np.full((M + 1, k + 1), -np.inf); L[M, 0] = 0.0
    for i in range(M - 1, -1, -1):
        L[i, 0] = 0.0
        L[i, 1:] = np.logaddexp(L[i + 1, 1:], lw[i] + L[i + 1, :-1])
    lw_ = lw

    def draw(rng):
        S, j = [], k
        u = rng.random(M)
        for i in range(M):
            if j == 0:
                break
            pr = np.exp(lw_[i] + L[i + 1, j - 1] - L[i, j])
            if u[i] < pr:
                S.append(i); j -= 1
        assert j == 0
        return np.array(S)
    return draw


def main(circ, basis, model, k, n, seed):
    k, n, seed = int(k), int(n), int(seed)
    dem = noisy(circ, basis, 1e-3, model).detector_error_model(approximate_disjoint_errors=True)
    q, rows, cols, orows, ocols, sig = [], [], [], [], [], []
    for i, e in enumerate(e for e in dem.flattened() if e.type == "error"):
        q.append(e.args_copy()[0]); d = []
        for t in e.targets_copy():
            if t.is_relative_detector_id():
                rows.append(t.val); cols.append(i); d.append(t.val)
            elif t.is_logical_observable_id():
                orows.append(t.val); ocols.append(i)
        sig.append(tuple(sorted(d)))
    q = np.array(q); M = len(q)
    H = csc_matrix((np.ones(len(rows), np.uint8), (rows, cols)), shape=(dem.num_detectors, M))
    L = csc_matrix((np.ones(len(orows), np.uint8), (orows, ocols)), shape=(dem.num_observables, M))
    dec = BPOSD(dem, **IBM_BPOSD)
    m = dec._matrices
    Hd = m.check_matrix.tocsc()
    colmap = {tuple(sorted(Hd.indices[Hd.indptr[j]:Hd.indptr[j + 1]])): j for j in range(Hd.shape[1])}
    mech2col = np.array([colmap[s] for s in sig])
    llr = np.log((1 - m.priors) / m.priors)
    strong = {
        "osd_cs40": BpOsdDecoder(m.check_matrix, error_channel=list(m.priors), max_iter=10000, bp_method="min_sum",
                                 ms_scaling_factor=0, osd_method="osd_cs", osd_order=40),
        "osd_e10": BpOsdDecoder(m.check_matrix, error_channel=list(m.priors), max_iter=10000, bp_method="min_sum",
                                ms_scaling_factor=0, osd_method="osd_e", osd_order=10),
    }
    draw = sampler(q / (1 - q), k)
    rng = np.random.default_rng([seed, k, 4404])
    t0 = time.time(); fails = 0; rows_ = []
    for _ in range(n):
        S = draw(rng)
        x = np.zeros(M, np.uint8); x[S] = 1
        syn = (H @ x % 2).astype(np.uint8); lo = (L @ x % 2).astype(np.uint8)
        c = dec._bposd.decode(syn)
        if not np.any((m.observables_matrix @ c % 2).astype(np.uint8) != lo):
            continue
        fails += 1
        e = np.zeros(Hd.shape[1], np.uint8); np.add.at(e, mech2col[S], 1); e %= 2
        row = dict(wE=int(e.sum()), wC=int(c.sum()), llrE=round(float(llr[e == 1].sum()), 2), llrC=round(float(llr[c == 1].sum()), 2),
                   bp_converged=bool(dec._bposd.converge), C_satisfies=bool(np.all((Hd @ c % 2) == syn)))
        for nm, sd in strong.items():
            c2 = sd.decode(syn)
            row[nm] = dict(ok=bool(np.all((m.observables_matrix @ c2 % 2).astype(np.uint8) == lo)), llr=round(float(llr[c2 == 1].sum()), 2))
        rows_.append(row)
    rec = dict(circ=circ, basis=basis, model=model, k=k, n=n, seed=seed, fails=fails, sec=round(time.time() - t0),
               C_less_likely_than_E=sum(r["llrC"] > r["llrE"] for r in rows_),
               strong_ok={nm: sum(r[nm]["ok"] for r in rows_) for nm in strong}, rows=rows_)
    with open(OUT / "fixk.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps({kk: v for kk, v in rec.items() if kk != "rows"}), flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:7])
