"""Auditor E-033: extra statistics on own + experimenter counts (lam0 3e-3 BP-OSD unless noted).
 - u11/ibm pooled variants (mine + experimenter pre-extension counts only; mine + all);
 - X/Z failure split for u11 (binomial tests, conditional on total), experimenter vs mine vs pooled;
 - IBM consistency mine vs experimenter (conditional binomial on Z+X totals);
 - own lam1 3e-3 u11 eps CI."""
import json
import numpy as np
from scipy.stats import binomtest
rng = np.random.default_rng(3305); R = 12; NS = 200000
def draws(c):
    t = 0; pt = 0
    for n, k in c:
        t = t + 1 - (1 - rng.beta(k + .5, n - k + .5, NS)) ** (1 / R); pt += 1 - (1 - k / n) ** (1 / R)
    return t, pt
def ratio(a, b):
    ta, pa = draws(a); tb, pb = draws(b); r = ta / tb
    return [round(pa / pb, 3), *np.round(np.quantile(r, [.025, .975]), 3).tolist(), round(float((r < 1).mean()), 4)]
add = lambda *xs: [(sum(x[i][0] for x in xs), sum(x[i][1] for x in xs)) for i in range(2)]
mine_u, mine_i = [(136000, 21), (135000, 27)], [(136000, 35), (135000, 31)]
cap_u, cap_i = [(40000, 7), (40000, 10)], [(49852, 15), (38001, 15)]
all_u, all_i = [(90000, 9), (90000, 22)], [(89852, 27), (78001, 27)]
out = {"mine": ratio(mine_u, mine_i), "mine+exp_precap": ratio(add(mine_u, cap_u), add(mine_i, cap_i)),
       "mine+exp_all": ratio(add(mine_u, all_u), add(mine_i, all_i))}
def xz(z, x):  # z=(n,k), x=(n,k); test k_X ~ Bin(k_Z+k_X, n_X/(n_Z+n_X))
    kt = z[1] + x[1]; pi = x[0] / (z[0] + x[0])
    return dict(Z=z, X=x, rate_ratio_X_over_Z=round((x[1] / x[0]) / (z[1] / z[0]), 2), p_two_sided=round(binomtest(x[1], kt, pi).pvalue, 4))
out["u11_XZ_exp_3e-3"] = xz((90000, 9), (90000, 22))
out["u11_XZ_mine_3e-3"] = xz((136000, 21), (135000, 27))
out["u11_XZ_pooled_3e-3"] = xz((226000, 30), (225000, 49))
out["u11_XZ_exp_4e-3"] = xz((9124, 15), (4839, 15))
out["u11_XZ_mine_4e-3(d1)"] = xz((8000, 15), (8000, 11))
out["u11_XZ_exp_5e-3"] = xz((1908, 26), (2008, 20))
out["ibm_XZ_mine"] = xz((136000, 35), (135000, 31)); out["ibm_XZ_exp"] = xz((89852, 27), (78001, 27))
# IBM per-shot (Z+X) consistency: experimenter vs mine
ke, ne, km, nm = 54, 89852 + 78001, 66, 271000
out["ibm_exp_vs_mine"] = dict(rate_exp=ke / ne, rate_mine=km / nm, ratio=round((ke / ne) / (km / nm), 2), p_two_sided=round(binomtest(ke, ke + km, ne / (ne + nm)).pvalue, 4))
ke, ne, km, nm = 31, 180000, 48, 271000
out["u11_exp_vs_mine"] = dict(ratio=round((ke / ne) / (km / nm), 2), p_two_sided=round(binomtest(ke, ke + km, ne / (ne + nm)).pvalue, 4))
t, pt = draws([(1200, 53), (1200, 50)])
out["mine_lam1_3e-3_u11_eps"] = [pt, *np.quantile(t, [.025, .975]).tolist()]
t2, _ = draws([(20583, 40), (17988, 40)])
r = t / t2; out["mine_u11_lam1_over_exp_ibm_lam1_3e-3"] = [pt / _, *np.quantile(r, [.025, .975]).tolist()]
print(json.dumps(out, indent=1))
json.dump(out, open("/Users/ephemeral/Desktop/qec-ai-search/results/E-033-audit/s_extra.json", "w"), indent=1)
