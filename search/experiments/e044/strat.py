"""E-044 fixed-fault-count (stratified, "subset") sampling of BP-OSD failure on the SD6 DEM.

For a circuit/basis/noise model the DEM (exactly the one sinter builds: approximate_disjoint_errors, no
decomposition possible for these codes) has independent mechanisms i with probabilities q_i(p).  With K = number of
mechanisms that fire,
    P_L(p) = sum_k P_p(K = k) f_k(p),   f_k = P(decoder fails | K = k).
Given K = k the fired set S has probability prop. to prod_{i in S} w_i, w_i = q_i / (1 - q_i).  Under SD6 every
q_i is (to O(p)) a fixed multiple of p, so this conditional law is p-independent up to O(p) corrections (checked
in probe: max_i |w_i(p) / w_i(p_ref) / (p/p_ref) - 1|).  f_k is therefore estimated once per stratum and reused for
every p; P_p(K = k) is the exact Poisson-binomial law of the DEM at p (analysis.py).
Exact conditional sampling: Bernoulli(t w_i / (1 + t w_i)) with t tuned so the mean count is k, accept iff the
count is exactly k (prod (t w_i) = t^k prod w_i, so the accepted law is exactly the conditional one).
The decoder is stimbposd.BPOSD(dem(p_dec), **IBM_BPOSD) -- the object sinter's SinterDecoder_BPOSD compiles.

  uv run python -m search.experiments.e044.strat run --circ ibm --basis Z --model lam1 --ks 6:40 --n 200 \
      --seed 1 --tag pilot [--pdec 0.001] [--sec 600]
Output: results/E-044-crossover/strat/<circ>_<basis>_<model>_pdec<pdec>.jsonl, one line per (k, batch).
"""
from __future__ import annotations

import argparse
import json
import time
import zlib

import numpy as np
import stim

from search.experiments.e044.common import IBM_BPOSD, OUT, noisy, sinter_dem

P_REF = 1e-3


def mechanisms(dem: stim.DetectorErrorModel):
    q, dets, obs = [], [], []
    for e in dem.flattened():
        if e.type != "error":
            continue
        d, o = set(), set()
        for t in e.targets_copy():
            if t.is_relative_detector_id():
                d ^= {t.val}
            elif t.is_logical_observable_id():
                o ^= {t.val}
        q.append(e.args_copy()[0])
        dets.append(sorted(d))
        obs.append(sorted(o))
    return np.array(q), dets, obs


class Stratum:
    def __init__(self, circ, basis, model, p_ref=P_REF, p_dec=P_REF):
        from scipy.sparse import csc_matrix
        from stimbposd import BPOSD
        c_ref = noisy(circ, basis, p_ref, model)
        dem_ref = sinter_dem(c_ref)
        self.q, self.dets, self.obs = mechanisms(dem_ref)
        self.w = self.q / (1 - self.q)
        self.nd, self.no = dem_ref.num_detectors, dem_ref.num_observables
        M = len(self.q)
        rows, cols = [], []
        for i, d in enumerate(self.dets):
            rows += d
            cols += [i] * len(d)
        self.H = csc_matrix((np.ones(len(rows), np.uint8), (rows, cols)), shape=(self.nd, M))
        rows, cols = [], []
        for i, o in enumerate(self.obs):
            rows += o
            cols += [i] * len(o)
        self.L = csc_matrix((np.ones(len(rows), np.uint8), (rows, cols)), shape=(self.no, M))
        dem_dec = sinter_dem(noisy(circ, basis, p_dec, model))
        qd, dd, od = mechanisms(dem_dec)
        assert dd == self.dets and od == self.obs, "DEM structure differs between p_ref and p_dec"
        self.dec = BPOSD(dem_dec, **IBM_BPOSD)

    def tilt(self, k):
        lo, hi = 1e-12, 1e12
        for _ in range(200):
            t = np.sqrt(lo * hi)
            m = np.sum(t * self.w / (1 + t * self.w))
            lo, hi = (t, hi) if m < k else (lo, t)
        return np.sqrt(lo * hi)

    def sample(self, k, n, rng):
        pt = (lambda t: t * self.w / (1 + t * self.w))(self.tilt(k))
        out = []
        while len(out) < n:
            B = 256
            u = rng.random((B, len(pt))) < pt
            cnt = u.sum(1)
            for r in np.flatnonzero(cnt == k):
                out.append(np.flatnonzero(u[r]))
                if len(out) == n:
                    break
        return out

    def outcome(self, S):
        x = np.zeros(self.H.shape[1], np.uint8)
        x[S] = 1
        syn = (self.H @ x) % 2
        lo = (self.L @ x) % 2
        return syn.astype(np.uint8), lo.astype(np.uint8)

    def decode_fail(self, S):
        syn, lo = self.outcome(S)
        pred = self.dec.decode(syn)
        return bool(np.any(pred.astype(np.uint8) != lo)), bool(syn.any())


def run(a):
    st = Stratum(a.circ, a.basis, a.model, P_REF, a.pdec)
    d = OUT / "strat"
    d.mkdir(exist_ok=True)
    f = d / f"{a.circ}_{a.basis}_{a.model}_pdec{a.pdec:g}.jsonl"
    lo, hi = map(int, a.ks.split(":"))
    ks = list(range(lo, hi + 1, a.kstep))
    alloc = {k: a.n for k in ks}
    if a.alloc:
        alloc = {int(k): int(v) for k, v in json.loads(open(a.alloc).read()).items()}
        ks = sorted(alloc)
    rng = np.random.default_rng([a.seed, zlib.crc32(f"{a.circ}|{a.basis}|{a.model}|{a.tag}".encode())])
    t_all = time.process_time()
    for k in ks:
        n_todo = alloc[k]
        while n_todo > 0:
            b = min(a.batch, n_todo)
            t0 = time.process_time()
            samples = st.sample(k, b, rng)
            ts = time.process_time() - t0
            fails, undet = 0, 0
            for S in samples:
                fl, nz = st.decode_fail(S)
                fails += fl
                undet += (not nz) and fl
            rec = dict(circ=a.circ, basis=a.basis, model=a.model, pdec=a.pdec, k=k, n=b, fail=fails,
                       undetected_fail=undet, sec_dec=round(time.process_time() - t0 - ts, 3),
                       sec_samp=round(ts, 3), tag=a.tag, seed=a.seed)
            with open(f, "a") as fh:
                fh.write(json.dumps(rec) + "\n")
            n_todo -= b
            if a.sec and time.process_time() - t_all > a.sec:
                print("SEC LIMIT", flush=True)
                return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("--circ")
    ap.add_argument("--basis")
    ap.add_argument("--model", default="lam1")
    ap.add_argument("--ks", default="6:40")
    ap.add_argument("--kstep", type=int, default=1)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--batch", type=int, default=200)
    ap.add_argument("--alloc")
    ap.add_argument("--pdec", type=float, default=P_REF)
    ap.add_argument("--seed", type=int, default=20261031)
    ap.add_argument("--tag", default="")
    ap.add_argument("--sec", type=float, default=0)
    a = ap.parse_args()
    if a.cmd == "run":
        run(a)


if __name__ == "__main__":
    main()
