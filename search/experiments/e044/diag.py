"""E-044 diagnostic: are BP-OSD failures at fixed fault count k maximum-likelihood failures or decoder failures?
For each failing sample: E = fired mechanisms (mapped to stimbposd's merged columns), C = BP-OSD correction.
R = E xor C is undetected with a nontrivial observable (a logical).  'suboptimal' := prior weight of C is LOWER
than that of E (sum of log-odds), i.e. the true error itself was a more likely explanation of the syndrome than the
decoder's output -> a most-likely-error decoder would not have produced this C.  Also reports |E|, |C|, |R|.
  uv run python -m search.experiments.e044.diag c11 Z lam1 16 20000"""
import json
import sys
import time

import numpy as np

from search.experiments.e044.common import jdump
from search.experiments.e044.strat import Stratum


def main(circ, basis, model, k, n, seed=99):
    st = Stratum(circ, basis, model)
    m = st.dec._matrices
    H = m.check_matrix.tocsc()
    col = {}
    for j in range(H.shape[1]):
        col[tuple(sorted(H.indices[H.indptr[j]:H.indptr[j + 1]]))] = j
    mech2col = np.array([col[tuple(d)] for d in st.dets])
    llr = np.log((1 - m.priors) / m.priors)
    rng = np.random.default_rng([seed, k])
    t0 = time.process_time()
    rows = []
    nf = 0
    for S in st.sample(k, n, rng):
        syn, lo = st.outcome(S)
        c = st.dec._bposd.decode(syn)
        pred = (m.observables_matrix @ c) % 2
        if not np.any(pred.astype(np.uint8) != lo):
            continue
        nf += 1
        e = np.zeros(H.shape[1], np.uint8)
        np.add.at(e, mech2col[S], 1)
        e %= 2
        r = (e ^ c.astype(np.uint8))
        rows.append(dict(wE=int(e.sum()), wC=int(c.sum()), wR=int(r.sum()), llrE=float(llr[e == 1].sum()),
                         llrC=float(llr[c == 1].sum()), suboptimal=bool(llr[c == 1].sum() > llr[e == 1].sum()),
                         osd=bool(not st.dec._bposd.converge)))
    rec = dict(circ=circ, basis=basis, model=model, k=k, n=n, fails=nf,
               suboptimal=sum(r["suboptimal"] for r in rows), bp_not_converged=sum(r["osd"] for r in rows),
               wR=sorted(r["wR"] for r in rows), sec=round(time.process_time() - t0), rows=rows)
    jdump(rec, "diag.jsonl")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]))
