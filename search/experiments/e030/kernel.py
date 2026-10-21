"""E-030 structural kernel: practical decoders on t-subsets of the exactly enumerated minimum-weight logicals
(lead.py / ccsearch enum, expanded by the 45 DEM translations).  Inject S (t columns of a weight-W logical L): syndrome
= XOR of their detector sets, true flip = XOR of observables; decode on the full R-round DEM (priors at P_DEC, model
lam).  For t < W - t the most-likely-error decoder is correct (complement heavier), so any failure is the decoder's
own ("masking distance"; E-026 method).  Also reports the prior-weighted failure fraction (weight prod q_S).

  PYTHONPATH=.:tests uv run python -m search.experiments.e030.kernel --circ c11 --W 10 --R 4 --t 4,5 --n 2000
"""
import argparse
import json
import time
from multiprocessing import get_context

import numpy as np
import scipy.sparse as sp
from stimbposd import detector_error_model_to_check_matrices

from search.experiments.e026.fw import decoders
from search.experiments.e029.export import dem_columns, translations_dem
from search.experiments.e030.common import OUT, noisy

P_DEC = 2e-3


class D_:
    pass


def setup(circ, basis, R, W, model):
    c = noisy(circ, basis, R, P_DEC, model)
    dem = c.detector_error_model(decompose_errors=False)
    m = detector_error_model_to_check_matrices(dem, allow_undecomposed_hyperedges=True)
    D = D_()
    D.H = sp.csc_matrix(m.check_matrix).astype(np.uint8); D.Hr = D.H.tocsr()
    D.L = sp.csc_matrix(m.observables_matrix).astype(np.uint8); D.Lr = D.L.tocsr()
    D.q = np.asarray(m.priors, float)
    keys = {}
    for k in range(D.H.shape[1]):
        dk = tuple(D.H.indices[D.H.indptr[k]:D.H.indptr[k + 1]].tolist())
        ok = tuple(D.L.indices[D.L.indptr[k]:D.L.indptr[k + 1]].tolist())
        keys[(dk, ok)] = k
    # logicals in export column ids (lam1, p=1e-3 DEM, same as ccsearch instance) -> check-matrix columns
    dem1, cols = dem_columns(noisy(circ, basis, R, 1e-3, "lam1"))
    cols = [x for x in cols if x[0] or x[1]]
    group, _ = translations_dem(dem1, cols, 15, 3)
    sols = [tuple(int(x) for x in ln.split(":")[1].split())
            for ln in (OUT / "runs" / f"{circ}_{basis}_R{R}_enum{W}.txt").read_text().splitlines() if ln.startswith("SOL")]
    full = set()
    for S in sols:
        for _, perm in group:
            full.add(tuple(sorted(perm[j] for j in S)))
    logs = np.array([[keys[cols[j]] for j in S] for S in sorted(full)])
    return D, logs


_C = {}


def run(args):
    circ, basis, R, W, model, t, n, seed = args
    key = (circ, basis, R, W, model)
    if key not in _C:
        _C.clear(); D, logs = setup(circ, basis, R, W, model); _C[key] = (D, logs, decoders(D))
    D, logs, decs = _C[key]
    rng = np.random.default_rng([seed, t, "ZX".index(basis), R])
    lq = np.log(D.q)
    fails = {nm: 0 for nm in decs}; wf = {nm: 0.0 for nm in decs}; wsum = 0.0; ideal = 0.0; t0 = time.process_time()
    ex = {nm: [] for nm in decs}
    for _ in range(n):
        L = logs[rng.integers(len(logs))]
        S = rng.choice(L, t, replace=False); C = np.setdiff1d(L, S)
        e = np.zeros(D.H.shape[1], np.uint8); e[S] = 1
        syn = (D.Hr @ e) % 2; tr = (D.Lr @ e) % 2
        sS, sC = lq[S].sum(), lq[C].sum()
        ideal += 1 if sC > sS + 1e-12 else (0.5 if abs(sC - sS) <= 1e-12 else 0)
        w = float(np.exp(sS)); wsum += w
        for nm, f in decs.items():
            if ((D.Lr @ f(syn.astype(np.uint8))) % 2 != tr).any():
                fails[nm] += 1; wf[nm] += w
                if len(ex[nm]) < 10:
                    ex[nm].append([int(x) for x in S])
    return dict(circ=circ, basis=basis, R=R, W=W, model=model, t=t, n=n, nlog=int(len(logs)), fails=fails,
                wfrac={k: v / wsum for k, v in wf.items()}, ideal_fail=ideal, examples=ex, cpu=time.process_time() - t0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--circ", required=True); ap.add_argument("--W", type=int, required=True)
    ap.add_argument("--R", type=int, default=4); ap.add_argument("--bases", default="Z,X")
    ap.add_argument("--t", default="4,5"); ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--model", default="lam1"); ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--seed", type=int, default=20261021)
    a = ap.parse_args(); assert a.workers <= 4
    jobs = [(a.circ, b, a.R, a.W, a.model, int(t), a.n, a.seed) for b in a.bases.split(",") for t in a.t.split(",")]
    od = OUT / "kernel"; od.mkdir(parents=True, exist_ok=True)
    with get_context("spawn").Pool(a.workers) as pool:
        for r in pool.imap_unordered(run, jobs):
            (od / f"{r['circ']}_{r['basis']}_R{r['R']}_{r['model']}_t{r['t']}.json").write_text(json.dumps(r))
            print(r["circ"], r["basis"], r["model"], "W", r["W"], "t", r["t"], "fails", r["fails"], "wfrac",
                  {k: round(v, 4) for k, v in r["wfrac"].items()}, "ideal", r["ideal_fail"], "/", r["n"], "nlog",
                  r["nlog"], "cpu", round(r["cpu"]), flush=True)


if __name__ == "__main__":
    main()
