"""Item 4: how many distinct low-weight undetectable logical errors does each circuit have?

Same randomized BP-OSD search as E-002/E-003 stage_distance (arXiv:2603.05481 Eq. 12; error_rate 0.01, min-sum,
100 iters, OSD-CS order 10), but every solution is kept (as a frozenset of DEM columns). Two independent batches
(different seeds) per (circuit, basis); distinct solutions of each weight are counted and a Chapman
capture-recapture estimate N = (n1+1)(n2+1)/(m+1) - 1 is formed per weight. Capture probabilities are heterogeneous
(the search is biased), so N is a LOWER-biased proxy; it is applied identically to both circuits.
Also records sum over found logicals of prod(priors at p=0.001) as a crude leading-order weight.

uv run python lowweight_count.py --rounds 2 --trials 3000 --workers 3
"""
import argparse
import json
import time
from multiprocessing import get_context

import numpy as np
import scipy.sparse as sp

from common import code_and_scheds, memory, dem_matrices, OUT


def run(args):
    name, basis, rounds, trials, seed = args
    from ldpc import BpOsdDecoder
    code, S = code_and_scheds()
    c = memory(code, S[name], name, rounds, basis, 0.001)
    D, Lm, pri = dem_matrices(c)
    rng = np.random.default_rng(seed)
    sols = {}
    t0 = time.process_time()
    for _ in range(trials):
        a = rng.integers(0, 2, Lm.shape[0])
        if not a.any():
            a[rng.integers(Lm.shape[0])] = 1
        b = rng.integers(0, 2, D.shape[0])
        eta = ((a @ Lm) + (b @ D)) % 2
        H = sp.vstack([D, sp.csr_matrix(eta.astype(np.uint8))]).tocsr()
        syn = np.zeros(H.shape[0], dtype=np.uint8); syn[-1] = 1
        dec = BpOsdDecoder(H, error_rate=0.01, max_iter=100, bp_method="minimum_sum", osd_method="osd_cs", osd_order=10)
        xi = dec.decode(syn)
        cols = tuple(np.nonzero(xi)[0].tolist())
        assert not ((D @ xi) % 2).any() and ((Lm @ xi) % 2).any()
        if len(cols) <= 13:
            sols[cols] = sols.get(cols, 0) + 1
    return name, basis, seed, {"sols": [list(k) for k in sols], "hits": list(sols.values()),
                               "logp": [float(np.log(pri[list(k)]).sum()) for k in sols],
                               "cpu_s": time.process_time() - t0, "ncols": int(D.shape[1])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--trials", type=int, default=3000)
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    tasks = [(n, b, a.rounds, a.trials, s) for s in (101, 202) for n in ("strikis", "ibm") for b in "ZX"]
    raw = {}
    with get_context("spawn").Pool(a.workers) as pool:
        for name, basis, seed, r in pool.imap_unordered(run, tasks):
            raw[f"{name}_{basis}_{seed}"] = r
            print(name, basis, seed, "found<=13:", len(r["sols"]), f"{r['cpu_s']:.0f}s", flush=True)
    (OUT / f"lowweight_raw_r{a.rounds}.json").write_text(json.dumps(raw))
    summ = {}
    for name in ("strikis", "ibm"):
        for basis in "ZX":
            b1 = raw[f"{name}_{basis}_101"]; b2 = raw[f"{name}_{basis}_202"]
            s1 = {tuple(x) for x in b1["sols"]}; s2 = {tuple(x) for x in b2["sols"]}
            row = {}
            for w in (10, 11, 12, 13):
                n1 = {x for x in s1 if len(x) == w}; n2 = {x for x in s2 if len(x) == w}
                m = len(n1 & n2)
                row[w] = {"n1": len(n1), "n2": len(n2), "both": m, "union": len(n1 | n2),
                          "chapman_N": round((len(n1) + 1) * (len(n2) + 1) / (m + 1) - 1, 1)}
            summ[f"{name}_{basis}"] = row
            print(name, basis, row, flush=True)
    (OUT / f"lowweight_summary_r{a.rounds}.json").write_text(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
