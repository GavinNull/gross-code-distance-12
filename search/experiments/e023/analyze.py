"""E-023 analysis: LER(p) per circuit / noise / decoder, A/B ratios, crossover.  experimenter.

Per sector s and decoder D:
  LER_s(p) = Σ_w π_w(p) f_w,   π_w exact Poisson-binomial of the sector DEM at p.
  f_w is split into  structural part  f~_w = P(random w-set ⊇ some minimal D-failing structural core)
                       (union bound, P(S ⊆ E | |E| = w) = Π_{i∈S} r_i · e_{w-|S|}(r) / e_w(r), e_k elementary symmetric)
                   +  non-structural part g_w measured by fixed-weight MC: fraction of samples on which D fails AND the
                       sample contains no D-failing structural core.
  REVISED after the core run (decoders fail on weight-2/3 subsets of *higher-weight* logicals, which are far too
  many to enumerate): the decoder curve uses the MC f_w directly at every grid weight w = 1..16 (log-log
  interpolation between grid points, power law above), uncertainty from Jeffreys Beta(k+1/2, n-k+1/2) posterior
  draws per grid weight (so k = 0 weights contribute their honest upper range).  The structural f~_w is kept only
  as a diagnostic lower bound (MC must not fall below it).
Ideal decoder ("ideal"): structural cores with the MLE-vs-complement rule (lower bound on MLE failure) only.
LER per round (all k logicals): 1 - (1 - Σ_s LER_s)^(1/T).
"""
from __future__ import annotations

import argparse
import glob
import json
from collections import defaultdict

import numpy as np

from search.experiments.e023.common import OUT, P_DEC, PROBLEMS, sectors, weight_distribution

_MASK = None
PGRID = np.array([1e-4, 2e-4, 3e-4, 5e-4, 7e-4, 1e-3, 1.5e-3, 2e-3, 3e-3, 4e-3])
WMAX = 120


def esym(r, kmax):
    e = np.zeros(kmax + 1)
    e[0] = 1.0
    for x in r:
        e[1:] = e[1:] + x * e[:-1]
    return e


def load_cores(prob, model, label, dec):
    """Union of all split strata (files {prob}_{model}_{label}*.npz); duplicates keep the first stratum (sorted)."""
    import itertools
    fail, seen = {}, set()
    ideal = dec in ("ideal3", "ideal4")
    for path in sorted(glob.glob(str(OUT / "splits" / f"{prob}_{model}_{label}*.npz"))):
        if ideal != ("_I" in path.split(f"_{label}")[-1]):
            continue                    # ideal uses the ideal-only strata (_I*), decoders the decoded strata
        z = np.load(path, allow_pickle=True)
        if ideal:
            S = [tuple(int(x) for x in row if x >= 0) for row in z["S"]]
            for s_, fv, h, nm in zip(S, z[dec], z["ht"], z["nonmin"]):
                if s_ in seen:
                    continue
                seen.add(s_)
                if fv > 0 and not nm:
                    fail[s_] = (fv, h)
            continue
        names = list(z["names"])
        if dec in ("ideal3", "ideal4"):
            f = z[dec]
        elif dec not in names:
            continue
        else:
            f = z["dec"][:, names.index(dec)].astype(float)
        S = [tuple(int(x) for x in row if x >= 0) for row in z["S"]]
        for s_, fv, h in zip(S, f, z["ht"]):
            if s_ in seen:
                continue
            seen.add(s_)
            if fv > 0:
                fail[s_] = (fv, h)
    if ideal:
        return {s_: fv * h for s_, (fv, h) in fail.items()}
    minimal = {}
    for s_, (fv, h) in fail.items():
        sub = any(c in fail for t in range(1, len(s_)) for c in itertools.combinations(s_, t))
        if not sub:
            minimal[s_] = fv * h
    return minimal


def struct_terms(minimal, q):
    """Σ_cores weight · Π q  (per core size)."""
    out = defaultdict(float)
    for s, wgt in minimal.items():
        out[len(s)] += wgt * float(np.prod(q[list(s)]))
    return dict(out)


def struct_fw(minimal, r, wmax):
    e = esym(r, wmax)
    f = np.zeros(wmax + 1)
    A = defaultdict(float)
    for s, wgt in minimal.items():
        A[len(s)] += wgt * float(np.prod(r[list(s)]))
    for t, At in A.items():
        for w in range(t, wmax + 1):
            f[w] += At * e[w - t] / e[w]
    return np.minimum(f, 1.0)


def contains_core(sample, index, minimal_sets):
    ss = set(int(x) for x in sample)
    for c in sample:
        for core in index.get(int(c), ()):
            if core[0] == int(c) and set(core) <= ss:
                return True
    return False


def load_fw(prob, model, label, dec, minimal, region="full"):
    """-> dict w -> (n, k_total, k_nonstruct).  region='bulk' reads the bulk-only MC files."""
    idx = defaultdict(list)
    for core in minimal:
        idx[core[0]].append(core)
    out = defaultdict(lambda: [0, 0, 0])
    pat = f"{prob}_{model}_w*_b*.npz" if region == "full" else f"{prob}_{model}_bulk_w*_b*.npz"
    for f in sorted(glob.glob(str(OUT / "fw" / pat))):
        z = np.load(f)
        if f"{label}_{dec}_f" not in z:
            continue
        w = int(z["w"])
        fl = z[f"{label}_{dec}_f"]
        sets = z[f"{label}_sets"]
        keep = _MASK[sets].all(1)
        fl, sets = fl[keep], sets[keep]
        o = out[w]
        o[0] += len(fl)
        o[1] += int(fl.sum())
        for i in np.flatnonzero(fl):
            if not contains_core(sets[i], idx, minimal):
                o[2] += 1
    return dict(out)


def cloglog_fit(ws, ns, ks):
    """binomial MLE of cloglog g = a + b log w; returns (a, b) or None."""
    from scipy.optimize import minimize
    ws, ns, ks = map(np.asarray, (ws, ns, ks))
    if ks.sum() == 0:
        return None
    lw = np.log(ws)

    def nll(th):
        g = 1 - np.exp(-np.exp(th[0] + th[1] * lw))
        g = np.clip(g, 1e-300, 1 - 1e-15)
        return -(ks * np.log(g) + (ns - ks) * np.log1p(-g)).sum()
    best = None
    for b0 in (2.0, 4.0, 6.0, 8.0):
        a0 = np.log(max(ks.sum(), 0.5) / ns.sum()) - b0 * lw.mean()
        r = minimize(nll, [a0, b0], method="Nelder-Mead", options=dict(xatol=1e-6, fatol=1e-9, maxiter=4000))
        if best is None or r.fun < best.fun:
            best = r
    return best.x


def sector_curve(prob, model, si, dec, rng, nboot=200, region="full"):
    """Returns dict with arrays over PGRID: central, lo68, hi68, lo95, hi95, plus diagnostics.
    region='bulk': restrict to time-bulk columns (common.bulk_mask): π_w from the bulk columns only, f_w from the MC
    samples that lie entirely in the bulk (an exact sample of the bulk-conditioned law), cores inside the bulk."""
    from search.experiments.e023.common import bulk_mask
    sec0 = sectors(prob, model, P_DEC)[si]
    label = sec0.label
    if region == "bulk":
        MASK, TB = bulk_mask(prob, sectors(prob, "sd6", P_DEC)[si])
    else:
        MASK, TB = np.ones(sec0.ncol, bool), None
    r0 = np.where(MASK, sec0.q / (1 - sec0.q), 0.0)
    qs = [np.where(MASK, sectors(prob, model, p)[si].q, 0.0) for p in PGRID]
    pis = [weight_distribution(q[MASK], WMAX) for q in qs]
    global _MASK
    _MASK = MASK
    if dec.startswith("ideal"):
        m3 = load_cores(prob, model, label, "ideal3")
        m4 = load_cores(prob, model, label, "ideal4")
        if region == "bulk":
            m3 = {k: v for k, v in m3.items() if MASK[list(k)].all()}
            m4 = {k: v for k, v in m4.items() if MASK[list(k)].all()}
        cen = np.array([sum(struct_terms(m4 if p <= 3e-4 else m3, q).values()) for p, q in zip(PGRID, qs)])
        return dict(central=cen, lo68=cen, hi68=cen, lo95=cen, hi95=cen, TB=TB,
                    terms=[{str(k): v for k, v in struct_terms(m3, q).items()} for q in qs])
    if dec.endswith("_struct"):
        # decoder-tested structural cores only (union bound over minimal failing cores): what the decoder does on the
        # low-weight-logical splits; a lower bound if the decoder has other low-weight failures (checked by MC)
        mn = load_cores(prob, model, label, dec[:-7])
        if region == "bulk":
            mn = {k: v for k, v in mn.items() if MASK[list(k)].all()}
        cen = np.array([sum(struct_terms(mn, q).values()) for q in qs])
        # bootstrap over the HT-sampled cores (Poisson(1) weights per decoded failing core)
        keys = list(mn)
        W = np.array([mn[k] for k in keys])
        PQ = np.array([[float(np.prod(q[list(k)])) for k in keys] for q in qs]) if keys else np.zeros((len(qs), 0))
        B = np.array([(PQ * (W * rng.poisson(1.0, len(W)))[None, :]).sum(1) for _ in range(nboot)])
        return dict(central=cen, lo68=np.percentile(B, 16, 0), hi68=np.percentile(B, 84, 0),
                    lo95=np.percentile(B, 2.5, 0), hi95=np.percentile(B, 97.5, 0), TB=TB, boot=B,
                    terms=[{str(k): v for k, v in struct_terms(mn, q).items()} for q in qs])
    fitmode = dec.endswith("_fit")
    if fitmode:
        dec = dec[:-4]
    minimal = load_cores(prob, model, label, dec)
    if region == "bulk":
        minimal = {k: v for k, v in minimal.items() if MASK[list(k)].all()}
    fst = struct_fw(minimal, r0, WMAX)            # structural lower bound on f_w for this decoder
    if fitmode:
        # model: f_w = f~_w (decoder-failing structural cores, union bound) + g_w, g_w = cloglog-linear-in-log-w
        # binomial fit to the MC failures that contain no such core (all grid weights, zeros included).
        # Used where the decoder never fails at low w in MC (BB108): the low-p tail is then structure + fitted
        # power law -- a MODEL extrapolation, reported as such.
        fw = load_fw(prob, model, label, dec, minimal, region)
        ws = np.array(sorted(fw))
        ns = np.array([fw[w][0] for w in ws])
        kn = np.array([fw[w][2] for w in ws])
        wa = np.arange(WMAX + 1)

        def gfun(k):
            th = cloglog_fit(ws, ns, k)
            if th is None:
                return np.zeros(WMAX + 1)
            g = 1 - np.exp(-np.exp(th[0] + th[1] * np.log(np.maximum(wa, 1))))
            g[0] = 0
            return g
        fc = np.minimum(fst + gfun(kn), 1)
        cen = np.array([float((pi * fc).sum()) for pi in pis])
        keys = list(minimal)
        Wc = np.array([minimal[k] for k in keys])
        B = []
        for _ in range(nboot):
            kb = rng.binomial(ns, kn / np.maximum(ns, 1))
            sc = (Wc * rng.poisson(1.0, len(Wc))).sum() / max(Wc.sum(), 1e-300)
            fb = np.minimum(fst * sc + gfun(kb), 1)
            B.append([float((pi * fb).sum()) for pi in pis])
        B = np.array(B)
        return dict(central=cen, lo68=np.percentile(B, 16, 0), hi68=np.percentile(B, 84, 0),
                    lo95=np.percentile(B, 2.5, 0), hi95=np.percentile(B, 97.5, 0), boot=B, TB=TB,
                    struct=np.array([float((pi * fst).sum()) for pi in pis]),
                    grid=dict(w=ws.tolist(), n=ns.tolist(), k_nonstruct=kn.tolist()))
    fw = load_fw(prob, model, label, dec, minimal, region)
    ws = np.array(sorted(fw))
    ns = np.array([fw[w][0] for w in ws])
    kt = np.array([fw[w][1] for w in ws])
    kn = np.array([fw[w][2] for w in ws])
    wa = np.arange(WMAX + 1)

    def build(fm):
        """fm: f at the measured weights -> full f_w: log-log interpolation in w between grid points,
        power-law extrapolation above the grid (slope of the last two points, capped at 1)."""
        lf = np.log(np.maximum(fm, 1e-300))
        lw = np.log(ws)
        f = np.zeros(WMAX + 1)
        inside = (wa >= ws[0]) & (wa <= ws[-1])
        f[inside] = np.exp(np.interp(np.log(wa[inside]), lw, lf))
        if len(ws) >= 2:
            sl = (lf[-1] - lf[-2]) / (lw[-1] - lw[-2])
            hi = wa > ws[-1]
            f[hi] = np.exp(lf[-1] + max(sl, 0) * (np.log(wa[hi]) - lw[-1]))
        f[0] = 0.0
        return np.minimum(f, 1.0)

    fhat = np.where(ns > 0, kt / np.maximum(ns, 1), 0)
    f_c = build(np.maximum(fhat, 1e-12))
    cen = np.array([float((pi * f_c).sum()) for pi in pis])
    boots = []
    for _ in range(nboot):
        fb = rng.beta(kt + 0.5, ns - kt + 0.5)          # Jeffreys posterior per grid weight (handles k = 0)
        boots.append([float((pi * build(fb)).sum()) for pi in pis])
    B = np.array(boots)
    st = np.array([float((pi * fst).sum()) for pi in pis])
    # share of LER coming from grid weights with zero observed failures (upper-limit dominated)
    zero_share = np.array([float((pi[ws[kt == 0]] * build(np.maximum(fhat, 1e-12))[ws[kt == 0]]).sum()) for pi in pis])
    return dict(central=cen, lo68=np.percentile(B, 16, 0), hi68=np.percentile(B, 84, 0),
                lo95=np.percentile(B, 2.5, 0), hi95=np.percentile(B, 97.5, 0), struct=st,
                grid=dict(w=ws.tolist(), n=ns.tolist(), k_tot=kt.tolist(), k_nonstruct=kn.tolist(),
                          f_struct=[float(fst[w]) for w in ws]),
                n_cores=len(minimal), boot=B, TB=TB)


def per_round(P, T):
    return 1 - (1 - np.minimum(P, 0.999)) ** (1 / T)


def problem_curve(prob, model, dec, rng, nboot=200, region="full"):
    secs = sectors(prob, model, P_DEC)
    parts = [sector_curve(prob, model, si, dec, rng, nboot, region) for si in range(len(secs))]
    T = PROBLEMS[prob]["T"] if region == "full" else float(np.mean([p["TB"] for p in parts]))
    cen = per_round(sum(p["central"] for p in parts), T)
    if "boot" in parts[0]:
        Bs = per_round(sum(p["boot"] for p in parts), T)
    else:
        Bs = cen[None, :]
    return dict(central=cen, boot=Bs, parts=parts)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default="m54_paper:m54_repo")
    ap.add_argument("--models", default="sd6")
    ap.add_argument("--decoders", default="bposd,relay,ideal")
    ap.add_argument("--nboot", type=int, default=200)
    ap.add_argument("--seed", type=int, default=23900)
    ap.add_argument("--tag", default="")
    ap.add_argument("--region", default="full", choices=["full", "bulk"])
    a = ap.parse_args(argv)
    rng = np.random.default_rng(a.seed)
    out = {}
    for pair in a.pairs.split(","):
        lo, hi = pair.split(":")
        for model in a.models.split(","):
            for dec in a.decoders.split(","):
                cl = problem_curve(lo, model, dec, rng, a.nboot, a.region)
                ch = problem_curve(hi, model, dec, rng, a.nboot, a.region)
                nb = min(len(cl["boot"]), len(ch["boot"]))
                R = cl["boot"][:nb] / ch["boot"][:nb]
                ratio = cl["central"] / ch["central"]
                key = f"{lo}|{hi}|{model}|{dec}"
                row = dict(p=PGRID.tolist(), ler_lo_dcirc=cl["central"].tolist(), ler_hi_dcirc=ch["central"].tolist(),
                           ratio=ratio.tolist(),
                           ratio_68=[np.percentile(R, 16, 0).tolist(), np.percentile(R, 84, 0).tolist()],
                           ratio_95=[np.percentile(R, 2.5, 0).tolist(), np.percentile(R, 97.5, 0).tolist()],
                           ler_lo_95=[np.percentile(cl["boot"], 2.5, 0).tolist(), np.percentile(cl["boot"], 97.5, 0).tolist()],
                           ler_hi_95=[np.percentile(ch["boot"], 2.5, 0).tolist(), np.percentile(ch["boot"], 97.5, 0).tolist()])
                for nm, c in (("lo", cl), ("hi", ch)):
                    row[f"diag_{nm}"] = [{k: v for k, v in p.items() if k not in ("boot",)
                                          and not isinstance(v, np.ndarray)} | {k: v.tolist() for k, v in p.items()
                                          if isinstance(v, np.ndarray) and k != "boot"} for p in c["parts"]]
                out[key] = row
                print(key)
                for i, p in enumerate(PGRID):
                    print(f"  p={p:.1e}  LER/round lo={cl['central'][i]:.3e} hi={ch['central'][i]:.3e}  "
                          f"ratio={ratio[i]:.2f}  95%[{row['ratio_95'][0][i]:.2f},{row['ratio_95'][1][i]:.2f}]")
    (OUT / f"analysis{a.tag}.json").write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
