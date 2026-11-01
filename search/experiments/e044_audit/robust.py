"""E-044 audit (items 2-4): own re-analysis of the stratified counts (results/E-044-crossover/strat/*.jsonl).
Own P(K = k): exact Poisson-binomial of the UNMERGED flat DEM mechanisms (what strat.py samples over), computed from
the DEM at each p (no odds scaling).  Own fits (binomial MLE, Laplace draws) of several functional forms and windows;
own monotone-only nonparametric bound; with / without phase C.
  PYTHONPATH=.:tests uv run python -m search.experiments.e044_audit.robust"""
import json
import sys
from collections import defaultdict
from functools import lru_cache
from math import comb

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln
from scipy.stats import beta

from search.experiments.e044.common import ROOT, noisy

STRAT = ROOT / "results" / "E-044-crossover" / "strat"
OUT = ROOT / "results" / "E-044-audit"
KMAX = 200
R = {"ibm": 12, "g10": 12, "u11": 12, "c11": 10, "ibm90": 10}
PS = [1e-4, 2.5e-4, 4e-4, 5.5e-4, 7e-4, 8.5e-4, 1e-3, 1.2e-3, 1.5e-3, 2e-3, 3e-3]
FCUT = 0.02
ND = 2000


@lru_cache(maxsize=None)
def pk(circ, basis, model, p):
    f = OUT / "pk" / f"{circ}_{basis}_{model}_{p:g}.npy"
    f.parent.mkdir(exist_ok=True)
    if f.exists():
        return np.load(f)
    dem = noisy(circ, basis, p, model).detector_error_model(approximate_disjoint_errors=True)
    q = np.array([e.args_copy()[0] for e in dem.flattened() if e.type == "error"])
    d = np.zeros(KMAX + 1); d[0] = 1
    for x in q:
        d[1:] = d[1:] * (1 - x) + d[:-1] * x
        d[0] *= 1 - x
    np.save(f, d)
    return d


def counts(circ, basis, model, tags=None):
    c = defaultdict(lambda: [0, 0])
    for ln in (STRAT / f"{circ}_{basis}_{model}_pdec0.001.jsonl").read_text().splitlines():
        r = json.loads(ln)
        if tags is None or r["tag"] in tags:
            c[r["k"]][0] += r["n"]; c[r["k"]][1] += r["fail"]
    return {k: tuple(v) for k, v in sorted(c.items())}


# ---------- functional forms: log f = g(theta, k) ----------
def g_pow(th, k): return th[0] + th[1] * np.log(k)
def g_lq(th, k): return th[0] + th[1] * np.log(k) + th[2] * np.log(k) ** 2
def g_exp(th, k): return th[0] + th[1] * k
def g_thr(t):
    def g(th, k):
        lc = gammaln(k + 1) - gammaln(t + 1) - gammaln(np.maximum(k - t, 0) + 1)
        # f = 1 - (1 - e^th0)^C(k,t) ~ C(k,t) e^th0 ; log form, -inf below t
        return np.where(k >= t, th[0] + lc, -np.inf)
    return g


FORMS = {"pow": (g_pow, [-30, 7]), "logquad": (g_lq, [-30, 7, 0]), "exp": (g_exp, [-15, 0.4])}
for t in range(3, 11):
    FORMS[f"thr{t}"] = (g_thr(t), [-25])


def fit(cnt, form, klo=None, khi=None):
    g, x0 = FORMS[form]
    ks = np.array(sorted(cnt))
    fh = np.array([(cnt[k][1] + .5) / (cnt[k][0] + 1) for k in ks])
    ok = np.flatnonzero(fh <= FCUT)
    kcut = ks[ok[-1]]
    sel = ks[(ks <= kcut) & (ks >= (klo or 0)) & (ks <= (khi or 10 ** 9))]
    n = np.array([cnt[k][0] for k in sel], float); f = np.array([cnt[k][1] for k in sel], float)
    if f.sum() < 3:
        return None

    def nll(th):
        lp = np.minimum(g(th, sel.astype(float)), -1e-12)
        with np.errstate(all="ignore"):
            t1 = np.where(f > 0, f * lp, 0.0)
        return -np.sum(t1 + (n - f) * np.log1p(-np.exp(lp)))
    best = None
    for s in range(6):
        st = np.array(x0, float) + (np.random.default_rng(s).normal(0, 2, len(x0)) if s else 0)
        st[0] = np.log(max(f.sum() / n.sum(), 1e-9)) - (g(np.r_[0, st[1:]], np.array([np.mean(sel)], float))[0])
        r = minimize(nll, st, method="Nelder-Mead", options=dict(xatol=1e-9, fatol=1e-11, maxiter=40000))
        if best is None or r.fun < best.fun:
            best = r
    th = best.x
    h = 1e-4 * np.maximum(1, np.abs(th))
    m = len(th); H = np.zeros((m, m))
    for i in range(m):
        for j in range(m):
            ei = np.eye(m)[i] * h[i]; ej = np.eye(m)[j] * h[j]
            H[i, j] = (nll(th + ei + ej) - nll(th + ei - ej) - nll(th - ei + ej) + nll(th - ei - ej)) / (4 * h[i] * h[j])
    try:
        cov = np.linalg.inv(H)
        if np.any(np.linalg.eigvalsh(cov) <= 0):
            cov = None
    except np.linalg.LinAlgError:
        cov = None
    return dict(th=th, cov=cov, nll=float(best.fun), kcut=int(kcut), kmin=int(sel[0]), kmax=int(sel[-1]), fails=int(f.sum()),
                shots=int(n.sum()), aic=2 * best.fun + 2 * m, form=form)


def fcurve(cnt, info, nd, rng):
    """draws (nd, KMAX+1) of f_k: model for k <= kcut, Jeffreys draws above kcut (data), 1 beyond sampled range"""
    g = FORMS[info["form"]][0]
    out = np.ones((nd, KMAX + 1))
    th = None
    if info["cov"] is not None:
        try:
            th = rng.multivariate_normal(info["th"], info["cov"], nd)
        except np.linalg.LinAlgError:
            th = None
    if th is None:
        th = np.repeat(info["th"][None], nd, 0)
    kk = np.arange(1, info["kcut"] + 1, dtype=float)
    with np.errstate(all="ignore"):
        out[:, 1:info["kcut"] + 1] = np.minimum(1, np.exp(np.array([g(t, kk) for t in th])))
    out[:, 0] = 0
    ks = sorted(cnt)
    for k in ks:
        if k > info["kcut"]:
            n, f = cnt[k]
            out[:, k] = rng.beta(f + .5, n - f + .5, nd)
    # interpolate between sampled k above kcut, last sampled value carried up to KMAX (as E-044 'lo')
    above = [k for k in ks if k > info["kcut"]]
    for k in range(info["kcut"] + 1, KMAX + 1):
        if k in cnt:
            continue
        lo = max([x for x in above if x < k] or [info["kcut"]]); hi = min([x for x in above if x > k] or [None], key=lambda x: x or 1e9)
        out[:, k] = out[:, lo] if hi is None else np.exp((np.log(out[:, lo] + 1e-300) * (hi - k) + np.log(out[:, hi] + 1e-300) * (k - lo)) / (hi - lo))
    return out


def eps(circ, model, fits, cnts, p, nd=ND, seed=0):
    rng = np.random.default_rng(seed)
    tot = 0
    for b in "ZX":
        F = fcurve(cnts[b], fits[b], nd, rng)
        PL = F @ pk(circ, b, model, p)
        tot = tot + 1 - (1 - np.clip(PL, 0, 1)) ** (1 / R[circ])
    return tot


def monotone_bound(cnt, p, circ, basis, model, side, a=0.025):
    """nonparametric: f non-decreasing in k.  side='lo': f_k >= max_i BetaLo(pooled strata i..k);
    'hi': f_k <= min_j BetaHi(pooled strata k..j); below smallest sampled k: lo 0, hi f_hi(kmin); above largest: lo carried, hi 1"""
    ks = sorted(cnt)
    P = pk(circ, basis, model, p)
    fk = np.zeros(KMAX + 1)
    for k in range(1, KMAX + 1):
        if side == "lo":
            best = 0.0
            win = [x for x in ks if x <= k]
            for i in range(len(win)):
                n = sum(cnt[x][0] for x in win[i:]); f = sum(cnt[x][1] for x in win[i:])
                if f:
                    best = max(best, beta.ppf(a, f, n - f + 1))
            fk[k] = best
        else:
            win = [x for x in ks if x >= k]
            if not win:
                fk[k] = 1.0; continue
            best = 1.0
            for j in range(len(win)):
                n = sum(cnt[x][0] for x in win[:j + 1]); f = sum(cnt[x][1] for x in win[:j + 1])
                best = min(best, beta.ppf(1 - a, f + 1, n - f))
            fk[k] = best
    PL = fk @ P
    return 1 - (1 - PL) ** (1 / R[circ])


PAIRS = [("g10", "ibm", "lam1"), ("u11", "ibm", "lam1"), ("c11", "ibm90", "lam1"), ("c11", "ibm90", "lam0")]


def main(which="all"):
    res = {}
    for full, ref, model in PAIRS:
        if which != "all" and f"{full}/{ref}/{model}" != which:
            continue
        for tagset, tname in ((None, "all"), (("pilot", "main"), "noPhaseC")):
            if tname == "noPhaseC" and model != "lam1" or tname == "noPhaseC" and ref != "ibm":
                continue
            C = {c: {b: counts(c, b, model, tagset) for b in "ZX"} for c in (full, ref)}
            windows = {"pow": (None, None), "pow_k<=30": (None, 30), "pow_k>=15": (15, None), "pow_k>=20": (20, None),
                       "pow_k<=20": (None, 20), "logquad": (None, None), "exp": (None, None), "exp_k<=30": (None, 30)}
            for t in range(3, 11):
                windows[f"thr{t}"] = (None, None)
            for wname, (klo, khi) in windows.items():
                form = wname.split("_")[0]
                F = {c: {b: fit(C[c][b], form, klo, khi) for b in "ZX"} for c in (full, ref)}
                if any(F[c][b] is None for c in F for b in "ZX"):
                    res[f"{full}/{ref}/{model}/{tname}/{wname}"] = "insufficient failures"
                    continue
                row = {"fit": {f"{c}{b}": dict(th=[round(float(x), 3) for x in F[c][b]["th"]], kmin=F[c][b]["kmin"], kmax=F[c][b]["kmax"],
                                               fails=F[c][b]["fails"], aic=round(F[c][b]["aic"], 2), laplace=F[c][b]["cov"] is not None)
                               for c in F for b in "ZX"}, "ratio": {}}
                for p in PS:
                    r = eps(full, model, F[full], C[full], p, seed=1) / eps(ref, model, F[ref], C[ref], p, seed=2)
                    row["ratio"][f"{p:g}"] = [round(float(x), 3) for x in np.quantile(r, [0.5, 0.025, 0.975])]
                res[f"{full}/{ref}/{model}/{tname}/{wname}"] = row
                print(f"{full}/{ref}/{model}/{tname}/{wname}", json.dumps(row["ratio"]), {k: (v["th"], v["fails"], v["aic"]) for k, v in row["fit"].items()}, flush=True)
            if tname == "all":
                mono = {}
                for p in PS:
                    lo = sum(monotone_bound(C[full][b], p, full, b, model, "lo") for b in "ZX")
                    hi = sum(monotone_bound(C[ref][b], p, ref, b, model, "hi") for b in "ZX")
                    lo2 = sum(monotone_bound(C[ref][b], p, ref, b, model, "lo") for b in "ZX")
                    hi2 = sum(monotone_bound(C[full][b], p, full, b, model, "hi") for b in "ZX")
                    mono[f"{p:g}"] = dict(ratio_lower=lo / hi, ratio_upper=hi2 / lo2, full=[lo, hi2], ref=[lo2, hi])
                res[f"{full}/{ref}/{model}/monotone"] = mono
                print(f"{full}/{ref}/{model}/monotone", json.dumps({k: [round(v['ratio_lower'], 3), round(v['ratio_upper'], 3)] for k, v in mono.items()}), flush=True)
    (OUT / f"robust_{which.replace('/', '_')}.json").write_text(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main(*sys.argv[1:])
