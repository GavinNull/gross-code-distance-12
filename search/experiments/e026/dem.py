"""E-026 DEM utilities: merged per-basis check matrices (stimbposd merge), detector (check i, round j) coordinates,
spatial (Z12 x Z6) and time translations of columns, exact fixed-weight column sampler."""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import scipy.sparse as sp
from stimbposd import detector_error_model_to_check_matrices

from search.experiments.e026.common import noisy

L_, M_ = 12, 6


class Dem:
    def __init__(self, circ, basis, R, p):
        self.circ, self.basis, self.R, self.p = circ, basis, R, p
        c = noisy(circ, basis, R, p)
        dem = c.detector_error_model()
        m = detector_error_model_to_check_matrices(dem, allow_undecomposed_hyperedges=True)
        self.H = sp.csc_matrix(m.check_matrix).astype(np.uint8)
        self.L = sp.csc_matrix(m.observables_matrix).astype(np.uint8)
        self.q = np.asarray(m.priors, float)
        self.ndet, self.ncol = self.H.shape
        co = dem.get_detector_coordinates()
        self.ij = np.array([[int(co[d][0]), int(co[d][1])] for d in range(self.ndet)])
        self.did = {(int(i), int(j)): d for d, (i, j) in enumerate(self.ij)}
        self.keys = [tuple(self.H.indices[self.H.indptr[k]:self.H.indptr[k + 1]].tolist()) for k in range(self.ncol)]
        self.kidx = {k: c for c, k in enumerate(self.keys)}
        self.Hr = self.H.tocsr()
        self.Lr = self.L.tocsr()
        self.colround = np.array([min(self.ij[d][1] for d in k) for k in self.keys])
        self.colround_max = np.array([max(self.ij[d][1] for d in k) for k in self.keys])

    def is_logical(self, cols):
        e = np.zeros(self.ncol, np.uint8)
        e[list(cols)] = 1
        return not ((self.Hr @ e) % 2).any() and bool(((self.Lr @ e) % 2).any())

    def translate(self, cols, a, b, dt):
        out = []
        for k in cols:
            nd = []
            for d in self.keys[k]:
                i, j = self.ij[d]
                i2 = ((i // M_ + a) % L_) * M_ + (i % M_ + b) % M_
                d2 = self.did.get((i2, j + dt))
                if d2 is None:
                    return None
                nd.append(d2)
            c2 = self.kidx.get(tuple(sorted(nd)))
            if c2 is None:
                return None
            out.append(c2)
        if len(set(out)) != len(out):
            return None
        return tuple(sorted(out))

    def symmetry(self):
        """spatial translations under which >= 90% of bulk columns map to columns (dt = 0)."""
        good = []
        bulk = [k for k in range(self.ncol) if 1 <= self.colround[k] and self.colround_max[k] <= self.R - 1]
        for a in range(L_):
            for b in range(M_):
                ok = sum(self.translate([k], a, b, 0) is not None for k in bulk)
                if ok >= 0.9 * len(bulk):
                    good.append((a, b))
        return good


@lru_cache(maxsize=None)
def get(circ, basis, R, p):
    return Dem(circ, basis, R, p)


def sample_fixed_weight(q, w, n, rng):
    """n column sets of size exactly w with P(S) ∝ prod_{i in S} q_i/(1-q_i) (exact: scaled Bernoulli + rejection)."""
    r = q / (1 - q)
    # choose scale s so that sum r s/(1+r s) = w
    lo, hi = 1e-9, 1e9
    for _ in range(200):
        s = np.sqrt(lo * hi)
        if (r * s / (1 + r * s)).sum() < w:
            lo = s
        else:
            hi = s
    pr = r * s / (1 + r * s)
    out = []
    while len(out) < n:
        x = rng.random((256, len(q))) < pr
        cnt = x.sum(1)
        for row in x[cnt == w]:
            out.append(np.nonzero(row)[0])
            if len(out) == n:
                break
    return out
