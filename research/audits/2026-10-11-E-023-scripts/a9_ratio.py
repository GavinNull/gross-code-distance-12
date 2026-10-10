"""Audit E-023: own re-analysis of bulk per-round LER and paper/repo ratio from fixed-weight counts.
Sources: 'exp' = experimenter's bulk fw npz (orig basis); 'sparse' = audit a6 json (sparsified basis).
LER_s(p) = Σ_w π_w(p) f_w ; π_w Poisson-binomial of the bulk columns at p; f_w log-log interpolated between grid weights
(same family as the experimenter: power-law above the grid with the last slope), Jeffreys posterior draws per grid weight.
Also a variant 'lin' (linear interpolation of f in w) for sensitivity.  per round = 1-(1-Σ_s LER_s)^(1/TB)."""
import sys, glob, json
import numpy as np
sys.path.insert(0, '.')
from search.experiments.e023.common import sectors, bulk_mask, weight_distribution
P = [1e-4, 3e-4, 5e-4, 1e-3, 2e-3]
WMAX = 120

def counts_exp(prob, label, dec):
    c = {}
    for f in glob.glob(f"results/E-023-ler-benefit/fw/{prob}_sd6_bulk_w*_b*.npz"):
        z = np.load(f); w = int(z["w"]); k = f"{label}_{dec}_f"
        a = c.setdefault(w, [0, 0]); a[0] += int(z[k].sum()); a[1] += len(z[k])
    return c

def counts_sparse(prob, label, dec):
    D = json.load(open(f"results/E-023-audit/a6_{prob}_{label}_sparse.json"))
    return {int(w): [r[f"sparse_{dec}"]["k"], r[f"sparse_{dec}"]["n"]] for w, r in D["grid"].items()}

def build(ws, fm, mode):
    wa = np.arange(WMAX + 1); f = np.zeros(WMAX + 1)
    inside = (wa >= ws[0]) & (wa <= ws[-1])
    if mode == "loglog":
        lf = np.log(np.maximum(fm, 1e-300)); lw = np.log(ws)
        f[inside] = np.exp(np.interp(np.log(wa[inside]), lw, lf))
        sl = max((lf[-1] - lf[-2]) / (lw[-1] - lw[-2]), 0)
        f[wa > ws[-1]] = np.exp(lf[-1] + sl * (np.log(wa[wa > ws[-1]]) - lw[-1]))
    else:
        f[inside] = np.interp(wa[inside], ws, fm)
        f[wa > ws[-1]] = fm[-1]
    f[:ws[0]] = 0; f[0] = 0
    return np.minimum(f, 1)

def curve(prob, src, dec, mode, rng, nb=400):
    tot_c, tot_b, TBs = 0, 0, []
    for si, sec in enumerate(sectors(prob, "sd6", 1e-3)):
        mask, TB = bulk_mask(prob, sec); TBs.append(TB)
        pis = [weight_distribution(sectors(prob, "sd6", p)[si].q[mask], WMAX) for p in P]
        c = (counts_exp if src == "exp" else counts_sparse)(prob, sec.label, dec)
        ws = np.array(sorted(c)); k = np.array([c[w][0] for w in ws]); n = np.array([c[w][1] for w in ws])
        fc = build(ws, np.maximum(k / n, 1e-12), mode)
        tot_c = tot_c + np.array([(pi * fc).sum() for pi in pis])
        B = np.array([[(pi * build(ws, rng.beta(k + .5, n - k + .5), mode)).sum() for pi in pis] for _ in range(nb)])
        tot_b = tot_b + B
    T = np.mean(TBs)
    pr = lambda x: 1 - (1 - np.minimum(x, .999)) ** (1 / T)
    return pr(tot_c), pr(tot_b)

if __name__ == "__main__":
    srcs = sys.argv[1].split(",")
    rng = np.random.default_rng(99)
    out = {}
    for src in srcs:
        for dec in ("bposd", "relay"):
            for mode in ("loglog", "lin"):
                cl, bl = curve("m54_paper", src, dec, mode, rng)
                ch, bh = curve("m54_repo", src, dec, mode, rng)
                R = bl / bh
                row = dict(p=P, ler_paper=cl.tolist(), ler_repo=ch.tolist(), ratio=(cl / ch).tolist(),
                           r95=[np.percentile(R, 2.5, 0).tolist(), np.percentile(R, 97.5, 0).tolist()])
                out[f"{src}|{dec}|{mode}"] = row
                print(src, dec, mode)
                for i, p in enumerate(P):
                    print(f"   p={p:.0e} paper {cl[i]:.2e} repo {ch[i]:.2e} ratio {cl[i]/ch[i]:.2f} [{row['r95'][0][i]:.2f}, {row['r95'][1][i]:.2f}]", flush=True)
    json.dump(out, open(f"results/E-023-audit/a9_ratio_{'_'.join(srcs)}.json", "w"), indent=1)
