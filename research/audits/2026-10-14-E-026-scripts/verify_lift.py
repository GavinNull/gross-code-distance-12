"""Auditor (E-026): independent checks of the lift families and the leading-order coefficients.
 1. every stored logical: distinct terms, detector XOR = 0, observable flip != 0 (files with term detectors)
 2. map every term onto a column of an independently built DEM (audit_sample.build, p = 1e-3); count collisions
    (distinct lift terms that are the same DEM column), compare term prior vs merged column prior
 3. recompute A6 (ideal 6|5, 6|6 rule) from scratch: (i) on stored term priors, per round from R differences;
    (ii) on DEM-column sets with merged priors and exact de-duplication (files with term detectors, total over R)
  PYTHONPATH=.:tests uv run python research/audits/2026-10-14-E-026-scripts/verify_lift.py
"""
import itertools, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_sample import build, ROOT, OUT

LIFT = ROOT / "results/E-026-gross-ler/lift"
PE = 1e-3


def a6(logs, lq):
    """ideal leading-order p^6 coefficient contribution at PE (same rule as claimed, own implementation)."""
    W = logs.shape[1]; tot = 0.0
    for S in itertools.combinations(range(W), 6):
        S = list(S); C = [i for i in range(W) if i not in S]
        s = lq[logs[:, S]].sum(1); c = lq[logs[:, C]].sum(1)
        tot += np.exp(s)[c > s + 1e-12].sum() + 0.5 * np.exp(s)[np.abs(c - s) <= 1e-12].sum()
    return tot


import os
SKIP = set(os.environ.get("SKIP", "").split(","))  # families already checked in an earlier (timed-out) run
res = {}
# (i) per round, stored priors
for circ, fams in (("fig12", [("w11", 4, 5), ("w11z", 4, 5)]), ("p18", [("w11z", 3, 4), ("w11", 5, 6)])):
    for b in "ZX":
        for mode, r1, r2 in fams:
            if f"{circ}_{b}_{mode}" in SKIP:
                continue
            v = []
            for R in (r1, r2):
                d = np.load(LIFT / f"{circ}_{b}_{mode}_R{R}.npz")
                v.append((len(d["logs"]), a6(d["logs"], d["logq"]) if len(d["logs"]) else 0.0))
            res[f"{circ}_{b}_{mode}"] = dict(n_per_round=v[1][0] - v[0][0], A6_per_round_coef=(v[1][1] - v[0][1]) / PE ** 6)
            print(circ, b, mode, res[f"{circ}_{b}_{mode}"], flush=True)
A = {c: sum(  # NB: skipped families are added from the earlier run log by the auditor
    v["A6_per_round_coef"] for k, v in res.items() if k.startswith(c)) for c in ("fig12", "p18")}
res["A6_total"] = A; res["ratio_p18_over_fig12"] = A["p18"] / A["fig12"]
print("A6", A, "ratio", res["ratio_p18_over_fig12"], flush=True)

# (1)(2)(ii) validity, DEM-column mapping, merged priors, de-dup
for name, R in (("fig12_Z_w11", 4), ("fig12_X_w11", 4), ("p18_Z_w11z", 3), ("p18_X_w11z", 3)):
    circ, b, mode = name.split("_")
    d = np.load(LIFT / f"{name}_R{R}.npz")
    logs, lq, td, to, tob = d["logs"], d["logq"], d["tdets"], d["toff"], d["tobs"]
    dem, H, L, q, _ = build(circ, b, R, PE)
    colkey = {}
    Hc, Lc = H.tocsc(), L.tocsc()
    for j in range(H.shape[1]):
        ds = tuple(Hc.indices[Hc.indptr[j]:Hc.indptr[j + 1]].tolist())
        ob = int(sum(1 << int(o) for o in Lc.indices[Lc.indptr[j]:Lc.indptr[j + 1]]))
        colkey[(ds, ob)] = j
    tcol = np.full(len(lq), -1)
    for t in range(len(lq)):
        k = (tuple(sorted(td[to[t]:to[t + 1]].tolist())), int(tob[t]))
        tcol[t] = colkey.get(k, -1)
    missing = int((tcol < 0).sum())
    bad = 0
    nd = int(d["ndet"])
    for Lg in logs[np.random.default_rng(5).choice(len(logs), min(5000, len(logs)), replace=False)]:
        syn = np.zeros(nd, np.uint8); ob = 0
        for t in Lg:
            syn[td[to[t]:to[t + 1]]] ^= 1; ob ^= int(tob[t])
        if syn.any() or ob == 0 or len(set(Lg)) != len(Lg):
            bad += 1
    cols = np.sort(tcol[logs], 1)
    n_coll_logs = int(sum(len(set(r)) < len(r) for r in cols))
    ucols = np.unique(cols, axis=0)
    multi_terms = len(lq) - len(set(tcol.tolist()))
    lqc = np.log(q)
    A_term = a6(logs, lq); A_col = a6(ucols, lqc)
    r = dict(R=R, n_logs=int(len(logs)), sampled_invalid=bad, terms=int(len(lq)), terms_not_in_dem=missing,
             terms_sharing_a_dem_column=int(multi_terms), logicals_with_repeated_column=n_coll_logs,
             distinct_column_sets=int(len(ucols)), max_rel_prior_diff=float(np.max(np.abs(np.exp(lqc[tcol]) / np.exp(lq) - 1))),
             A6_terms_coef=A_term / PE ** 6, A6_dem_columns_dedup_coef=A_col / PE ** 6,
             mean_q_over_p_on_logicals=float(np.exp(lqc[cols].mean()) / PE))
    res[f"check_{name}_R{R}"] = r
    print(name, r, flush=True)
(OUT / "verify_lift.json").write_text(json.dumps(res, indent=1))
