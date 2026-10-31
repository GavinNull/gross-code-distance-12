"""E-044 analysis (P_p(K=k) from the p = 1e-3 DEM with odds scaled by p/1e-3; probe: max deviation < 0.1%): P_L(p) = sum_k P_p(K = k) f_k from the stratified counts (strat.py), per basis, then per round.

P_p(K = k): exact Poisson-binomial law of the sinter DEM's mechanism probabilities at p (cached, pk/).
f_k: Jeffreys Beta(f + 1/2, n - f + 1/2) posterior per sampled k; draws propagated through the sum.
Unsampled k inside the sampled range: log-linear interpolation of the drawn f between neighbours (monotone).
Below the smallest sampled k (k0): 'lo' variant f = 0, 'hi' variant f = f_{k0} draw (f non-decreasing in k assumed).
Above the largest sampled k (k1): 'lo' f = f_{k1}, 'hi' f = 1.
'fit' variant: below k_fit the drawn f is replaced by a power law a k^b fitted (weighted least squares on the drawn
log f) to the lowest sampled strata with >= MINF failures -- EXTRAPOLATION, labelled as such.
eps_round = 1 - (1 - P_L)^(1/R); reported per basis and Z + X.
"""
from __future__ import annotations

import json
from collections import defaultdict
from functools import lru_cache

import numpy as np

from search.experiments.e044.common import CODEFAM, OUT, ROUNDS, noisy, sinter_dem
from search.experiments.e044.strat import mechanisms

KMAX = 160
PKD = OUT / "pk"
PKD.mkdir(exist_ok=True)


def pk(circ, basis, model, p):
    f = PKD / f"{circ}_{basis}_{model}_{p:g}.npy"
    if f.exists():
        return np.load(f)
    f0 = PKD / f"q_{circ}_{basis}_{model}.npy"
    if not f0.exists():
        np.save(f0, mechanisms(sinter_dem(noisy(circ, basis, 1e-3, model)))[0])
    w0 = np.load(f0)
    w = w0 / (1 - w0) * (p / 1e-3)          # odds scale linearly in p to < 0.1% (probe.jsonl wdev)
    q = w / (1 + w)
    d = np.zeros(KMAX + 2)
    d[0] = 1.0
    for x in q:
        d[1:KMAX + 1] = d[1:KMAX + 1] * (1 - x) + d[0:KMAX] * x
        d[0] *= 1 - x
    d[KMAX + 1] = max(0.0, 1 - d[:KMAX + 1].sum())  # tail mass P(K > KMAX)
    np.save(f, d)
    return d


def counts(circ, basis, model, pdec=1e-3, tags=None):
    c = defaultdict(lambda: [0, 0])
    f = OUT / "strat" / f"{circ}_{basis}_{model}_pdec{pdec:g}.jsonl"
    if not f.exists():
        return {}
    for ln in f.read_text().splitlines():
        r = json.loads(ln)
        if tags and r["tag"] not in tags:
            continue
        c[r["k"]][0] += r["n"]
        c[r["k"]][1] += r["fail"]
    return {k: tuple(v) for k, v in sorted(c.items())}


def draws_f(cnt, nd, rng):
    ks = np.array(sorted(cnt))
    F = np.empty((nd, len(ks)))
    for i, k in enumerate(ks):
        n, f = cnt[k]
        F[:, i] = rng.beta(f + 0.5, n - f + 0.5, nd)
    return ks, F


def fill(ks, F, variant, minf_fit=5, cnt=None, nfit=4):
    """f_k draws for k = 0..KMAX (+ tail column), shape (nd, KMAX + 2)"""
    nd = F.shape[0]
    out = np.zeros((nd, KMAX + 2))
    lF = np.log(np.maximum(F, 1e-300))
    lk = np.log(ks)
    for k in range(1, KMAX + 1):
        if k < ks[0]:
            out[:, k] = 0.0 if variant == "lo" else F[:, 0]
        elif k > ks[-1]:
            out[:, k] = F[:, -1] if variant != "hi" else 1.0
        else:
            j = np.searchsorted(ks, k)
            if ks[j] == k:
                out[:, k] = F[:, j]
            else:
                w = (np.log(k) - lk[j - 1]) / (lk[j] - lk[j - 1])
                out[:, k] = np.exp((1 - w) * lF[:, j - 1] + w * lF[:, j])
    out[:, KMAX + 1] = 1.0 if variant == "hi" else out[:, KMAX]
    if variant == "fit":
        good = [i for i, k in enumerate(ks) if cnt[k][1] >= minf_fit][:nfit]
        if len(good) >= 2:
            kf = ks[good[0]]
            X = np.vstack([np.ones(len(good)), lk[good]]).T
            for d in range(nd):
                coef, *_ = np.linalg.lstsq(X, lF[d, good], rcond=None)
                for k in range(1, kf):
                    out[d, k] = np.exp(coef[0] + coef[1] * np.log(k))
    return out


def PL(circ, basis, model, p, variant="mid", nd=4000, seed=7, pdec=1e-3, tags=None):
    cnt = counts(circ, basis, model, pdec, tags)
    rng = np.random.default_rng(seed)
    ks, F = draws_f(cnt, nd, rng)
    v = {"mid": "lo", "lo": "lo", "hi": "hi", "fit": "fit"}[variant]
    full = fill(ks, F, v, cnt=cnt)
    return full @ pk(circ, basis, model, p)


def per_round(x, R):
    return 1 - (1 - np.clip(x, 0, 1)) ** (1 / R)


def eps(circ, model, p, variant="mid", nd=4000, seed=7, pdec=1e-3, tags=None):
    R = ROUNDS[CODEFAM[circ]]
    tot = 0
    for i, b in enumerate("ZX"):
        tot = tot + per_round(PL(circ, b, model, p, variant, nd, seed + i, pdec, tags), R)
    return tot


def q(x):
    return [float(np.median(x)), float(np.quantile(x, 0.025)), float(np.quantile(x, 0.975))]
