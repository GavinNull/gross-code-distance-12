"""E-023 stage F: fixed-weight fault sampling per sector, and direct (Bernoulli) sampling.  experimenter.

f_w = P(decoder fails | exactly w sector columns fired), the w columns drawn from the DEM conditioned on |E| = w
(P(S) ∝ prod r_i, r = q/(1-q), exact rejection sampler; columns = independent merged mechanisms of the sector, so this
is the exact sector marginal).  The conditional law is computed from the DEM at P_DEC; since q_i ∝ p to O(p) it is
p-independent to that order.  Decoders use fixed priors = DEM at P_DEC (same decoder object for every w and p).
LER_sector(p) = Σ_w π_w(p) f_w with π_w the exact Poisson-binomial of the sector DEM at p.

Direct mode (--direct p): every column fires independently with q_i(p) (exact sector marginal; equals stim sampling
of the sector -- checked once against stim in validate.py); same decoders.

    PYTHONPATH=. uv run python -m search.experiments.e023.fixedweight --prob m54_paper --model sd6 --w 3:12 --n 2000
"""
from __future__ import annotations

import argparse
import time
from multiprocessing import get_context

import numpy as np

from search.experiments.e023.common import OUT, P_DEC, PROBLEMS, make_decoder, sample_fixed_weight, sectors

_D = {}


def _decs(prob, model, names):
    key = (prob, model, names)
    if key not in _D:
        _D.clear()
        secs = sectors(prob, model, P_DEC)
        _D[key] = (secs, [{nm: make_decoder(s, nm) for nm in names} for s in secs])
    return _D[key]


def decode_one(sec, dec, syn, nm):
    if not syn.any():
        return np.zeros(sec.nobs, np.uint8)
    if nm == "pymatching":
        return np.asarray(dec[1].decode(syn), np.uint8)
    e = dec(syn)
    return (sec.L @ e) % 2


def run_batch(args):
    prob, model, w, b, n, names, seed, outdir, direct_p, region = args
    tag = f"w{w:03d}" if direct_p is None else f"p{direct_p:.2e}"
    if region == "bulk":
        tag = "bulk_" + tag
    out = outdir / f"{prob}_{model}_{tag}_b{b:04d}.npz"
    if out.exists():
        return prob, tag, b, None
    t0 = time.process_time()
    secs, decs = _decs(prob, model, names)
    rng = np.random.default_rng([seed, list(PROBLEMS).index(prob), 0 if model == "sd6" else 1,
                                 w if direct_p is None else int(round(direct_p * 1e7)), b] + ([7] if region == "bulk" else []))
    rec = {}
    for si, sec in enumerate(secs):
        qs = sec.q
        if region == "bulk":
            from search.experiments.e023.common import bulk_mask
            qs = np.where(bulk_mask(prob, sectors(prob, "sd6", P_DEC)[si])[0], sec.q, 0.0)
        if direct_p is None:
            sets = sample_fixed_weight(qs, w, n, rng)
        else:
            qp = sectors(prob, model, direct_p)[si].q
            B = rng.random((n, sec.ncol)) < qp[None, :]
            sets = [np.flatnonzero(r) for r in B]
            rec[f"{sec.label}_nfault"] = np.array([len(s) for s in sets], np.int32)
        Hc = sec.H.tocsc()
        for nm in names:
            rec[f"{sec.label}_{nm}_f"] = np.zeros(n, bool)
        if direct_p is None:
            rec[f"{sec.label}_sets"] = sets.astype(np.int32)
        for i in range(n):
            S = sets[i]
            e = np.zeros(sec.ncol, np.uint8)
            e[S] = 1
            syn = (Hc @ e) % 2
            tr = (sec.L @ e) % 2
            for nm in names:
                pred = decode_one(sec, decs[si][nm], syn.astype(np.uint8), nm)
                rec[f"{sec.label}_{nm}_f"][i] = bool((pred != tr).any())
    cpu = time.process_time() - t0
    np.savez_compressed(out, **rec, cpu=cpu, n=n, w=-1 if w is None else w,
                        p=-1.0 if direct_p is None else direct_p)
    return prob, tag, b, cpu


def parse_w(s):
    out = []
    for part in s.split(","):
        if ":" in part:
            a = list(map(int, part.split(":")))
            out += list(range(a[0], a[1] + 1, a[2] if len(a) > 2 else 1))
        else:
            out.append(int(part))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--prob", required=True, help="comma list")
    ap.add_argument("--model", default="sd6")
    ap.add_argument("--w", default=None)
    ap.add_argument("--direct", default=None, help="comma list of p for direct sampling")
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--batch", type=int, default=500)
    ap.add_argument("--b0", type=int, default=0)
    ap.add_argument("--decoders", default="bposd,relay")
    ap.add_argument("--seed", type=int, default=23100)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--region", default="full", choices=["full", "bulk"])
    a = ap.parse_args(argv)
    assert a.workers <= 3
    assert a.region == "full" or a.direct is None
    names = tuple(a.decoders.split(","))
    outdir = OUT / ("fw" if a.direct is None else "direct")
    outdir.mkdir(parents=True, exist_ok=True)
    jobs = []
    points = [(w, None) for w in parse_w(a.w)] if a.direct is None else [(None, float(p)) for p in a.direct.split(",")]
    for (w, dp) in points:
        for b in range(a.b0, a.b0 + max(1, a.n // a.batch)):
            for prob in a.prob.split(","):
                jobs.append((prob, a.model, w, b, min(a.batch, a.n), names, a.seed, outdir, dp, a.region))
    t0 = time.time()
    tot = 0.0
    with get_context("spawn").Pool(a.workers) as pool:
        for prob, tag, b, cpu in pool.imap_unordered(run_batch, jobs):
            tot += cpu or 0
            print(f"{time.time() - t0:7.0f}s {prob} {a.model} {tag} b{b} cpu={cpu if cpu is None else round(cpu)}",
                  flush=True)
    print(f"done cpu={tot:.0f}s", flush=True)


if __name__ == "__main__":
    main()
