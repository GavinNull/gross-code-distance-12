"""E-044 audit: threshold-binomial family f_k = 1-(1-theta)^C(k,t) (f = 0 below t: single faults always corrected),
t chosen per circuit and basis by likelihood (profile over t = 3..12); ratio vs p for the best t and for a grid of
(t_full, t_ref) offsets.  In this family P_L ~ theta e_t(q) ~ theta mu^t / t!, so ratio ~ (mu_full/mu_ref)^t * amp,
i.e. p-independent unless t_full != t_ref; the crossover is decided by t_full - t_ref, which the data barely fix.
  PYTHONPATH=.:tests uv run python -m search.experiments.e044_audit.thrmix g10 ibm lam1"""
import json
import sys

import numpy as np

from search.experiments.e044_audit.robust import FORMS, OUT, PS, counts, eps, fit, g_thr

for t in range(11, 13):
    FORMS[f"thr{t}"] = (g_thr(t), [-25])


def main(full, ref, model):
    C = {c: {b: counts(c, b, model) for b in "ZX"} for c in (full, ref)}
    prof = {c: {b: {t: fit(C[c][b], f"thr{t}") for t in range(3, 13)} for b in "ZX"} for c in (full, ref)}
    best = {c: {b: min(prof[c][b], key=lambda t: prof[c][b][t]["nll"]) for b in "ZX"} for c in (full, ref)}
    pw = {c: {b: fit(C[c][b], "pow")["nll"] for b in "ZX"} for c in (full, ref)}
    out = dict(nll={f"{c}{b}": {t: round(prof[c][b][t]["nll"] - prof[c][b][best[c][b]]["nll"], 2) for t in prof[c][b]} for c in prof for b in "ZX"},
               best={f"{c}{b}": best[c][b] for c in best for b in "ZX"},
               pow_nll_minus_bestthr={f"{c}{b}": round(pw[c][b] - prof[c][b][best[c][b]]["nll"], 2) for c in pw for b in "ZX"}, ratio={})
    combos = {"best": (0, 0)}
    for dg in (-1, 0, 1):
        for di in (-1, 0, 1):
            combos[f"full{dg:+d}_ref{di:+d}"] = (dg, di)
    for name, (dg, di) in combos.items():
        F = {full: {b: prof[full][b][min(12, max(3, best[full][b] + dg))] for b in "ZX"},
             ref: {b: prof[ref][b][min(12, max(3, best[ref][b] + di))] for b in "ZX"}}
        dnll = sum(F[c][b]["nll"] - prof[c][b][best[c][b]]["nll"] for c in F for b in "ZX")
        r = {}
        for p in PS:
            x = eps(full, model, F[full], C[full], p, seed=1) / eps(ref, model, F[ref], C[ref], p, seed=2)
            r[f"{p:g}"] = [round(float(v), 3) for v in np.nanquantile(x, [0.5, 0.025, 0.975])]
        out["ratio"][name] = dict(dnll=round(dnll, 2), r=r)
        print(name, round(dnll, 2), json.dumps(r), flush=True)
    print(json.dumps({k: out[k] for k in ("best", "pow_nll_minus_bestthr", "nll")}))
    (OUT / f"thrmix_{full}_{ref}_{model}.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:4])
