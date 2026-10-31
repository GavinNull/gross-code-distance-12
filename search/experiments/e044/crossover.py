"""E-044 (3): per-round LER curves eps(p) (Z + X) and the crossover p* of each full-distance circuit vs IBM depth 8.

Variants for f_k (see analysis.py):
  data : per-stratum Jeffreys posteriors; below the smallest sampled k f = 0, log-linear interpolation between
         sampled k (no model beyond monotone interpolation; 'hi' = conservative upper variant).
  fitlow: same, but the fit uses only k <= KLOW (sensitivity of the extrapolation to the fitted range).
  fit  : for k <= KCUT (largest sampled k with fhat <= FCUT) f_k = exp(a) k^b, (a, b) binomial MLE over all sampled
         strata with k <= KCUT (zero-failure strata included), uncertainty from the Laplace approximation;
         above KCUT the data posteriors.  The power law is a MODEL; used where the data have no failures.
p* = largest grid p below which the median ratio full/ibm stays < 1; band = where the 97.5% / 2.5% quantiles cross 1.
  uv run python -m search.experiments.e044.crossover
"""
from __future__ import annotations

import json

import numpy as np
from scipy.optimize import minimize

from search.experiments.e044.analysis import KMAX, counts, draws_f, fill, pk, per_round
from search.experiments.e044.common import CODEFAM, OUT, ROUNDS

PAIRS = [("g10", "ibm"), ("u11", "ibm"), ("c11", "ibm90")]
MODELS = ("lam1", "lam0")
PGRID = np.round(np.geomspace(1e-4, 3e-3, 31), 7)
ND = 3000
FCUT = 0.02
KLOW = {"gross": 25, "bb90": 16}   # 'fitlow': power law fitted only to k <= KLOW (low-k slope)


def powerfit(cnt, kmaxfit=None):
    ks = np.array(sorted(cnt))
    fh = np.array([(cnt[k][1] + .5) / (cnt[k][0] + 1) for k in ks])
    ok = np.flatnonzero(fh <= FCUT)
    if not len(ok):
        return None
    kcut = ks[ok[-1]] if kmaxfit is None else min(ks[ok[-1]], kmaxfit)
    sel = ks[ks <= kcut]
    n = np.array([cnt[k][0] for k in sel], float)
    f = np.array([cnt[k][1] for k in sel], float)
    if f.sum() < 3:
        return None
    lk = np.log(sel)

    def nll(th):
        lphi = np.minimum(th[0] + th[1] * lk, -1e-9)
        phi = np.exp(lphi)
        return -np.sum(f * lphi + (n - f) * np.log1p(-phi))
    r = minimize(nll, [np.log(max(f.sum() / n.sum(), 1e-9)) - 5 * np.mean(lk), 5.0], method="Nelder-Mead",
                 options=dict(xatol=1e-8, fatol=1e-10, maxiter=20000))
    th = r.x
    h = 1e-4
    H = np.zeros((2, 2))
    for i in range(2):
        for j in range(2):
            e_i = np.eye(2)[i] * h; e_j = np.eye(2)[j] * h
            H[i, j] = (nll(th + e_i + e_j) - nll(th + e_i - e_j) - nll(th - e_i + e_j) + nll(th - e_i - e_j)) / (4 * h * h)
    cov = np.linalg.inv(H)
    return dict(a=float(th[0]), b=float(th[1]), cov=cov.tolist(), kcut=int(kcut), kmin=int(sel[0]),
                fails=int(f.sum()), shots=int(n.sum()))


def fdraws(circ, basis, model, variant, rng):
    cnt = counts(circ, basis, model)
    ks, F = draws_f(cnt, ND, rng)
    full = fill(ks, F, "hi" if variant == "hi" else "lo")
    info = None
    if variant in ("fit", "fitlow"):
        info = powerfit(cnt, None if variant == "fit" else KLOW[CODEFAM[circ]])
        if info:
            th = rng.multivariate_normal([info["a"], info["b"]], info["cov"], ND)
            kk = np.arange(1, info["kcut"] + 1)
            full[:, 1:info["kcut"] + 1] = np.minimum(1, np.exp(th[:, :1] + th[:, 1:] * np.log(kk)[None, :]))
    return full, info


def PLshot(circ, basis, model, p, variant, seed=5):
    """per-shot P_L draws for one basis"""
    full, info = fdraws(circ, basis, model, variant, np.random.default_rng(seed))
    with np.errstate(all="ignore"):
        return np.einsum("dk,k->d", full, pk(circ, basis, model, p)), info


def curve(circ, model, variant, seed):
    R = ROUNDS[CODEFAM[circ]]
    rng = np.random.default_rng(seed)
    out = np.zeros((ND, len(PGRID)))
    infos = {}
    for b in "ZX":
        full, info = fdraws(circ, b, model, variant, rng)
        infos[b] = info
        P = np.array([pk(circ, b, model, p) for p in PGRID])  # (np, KMAX+2)
        out += per_round(np.einsum("dk,pk->dp", full, P), R)
    return out, infos


def qs(x):
    return np.quantile(x, [0.5, 0.025, 0.975], axis=0)


def pstar(ratio):
    med, lo, hi = qs(ratio)

    def cross(v):
        below = v < 1
        if below.all():
            return ">=" + str(PGRID[-1])
        if not below[0]:
            return "<" + str(PGRID[0])
        return float(PGRID[np.argmin(below)])  # first grid p where it is no longer < 1
    return dict(median=cross(med), sure_below=cross(hi), possible_below=cross(lo))


def main():
    res = {}
    for model in MODELS:
        for variant in ("data", "fit", "fitlow"):
            cur = {}
            for c in ("g10", "u11", "ibm", "c11", "ibm90"):
                try:
                    cur[c] = curve(c, model, variant, 11)
                except Exception as e:
                    print("skip", c, model, variant, repr(e))
            for full, ref in PAIRS:
                if full not in cur or ref not in cur:
                    continue
                r = cur[full][0] / cur[ref][0]
                key = f"{full}_vs_{ref}_{model}_{variant}"
                res[key] = dict(p=PGRID.tolist(), eps_full=qs(cur[full][0]).T.tolist(), eps_ref=qs(cur[ref][0]).T.tolist(),
                                ratio=qs(r).T.tolist(), pstar=pstar(r), fit_full=cur[full][1], fit_ref=cur[ref][1])
                print(key, res[key]["pstar"], flush=True)
    (OUT / "crossover.json").write_text(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
