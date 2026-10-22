"""E-033 leading order (ideal most-likely-error decoder) from exact ccsearch enumerations (run_cc.sh, enum mode) of the
full SD6 DEM (e029.export dem; same columns as here).  Each root-case solution is expanded by the 72 DEM translations
(found and verified on the DEM by e029.export.translations_dem), every logical re-checked on the DEM (detectors cancel,
observable nonzero, W distinct columns), counted at each R; per-round count = N(R+1) - N(R) (saturation = constant
differences).  Coefficient of the leading power p^{ceil(W/2)}: even W: A = (1/2) sum_L e_{W/2}(q_L) / p^{W/2} (exact
half-half ties counted 1/2); odd W: A = sum_L e_{(W+1)/2}(q_L) / p^{(W+1)/2}; priors q from the DEM of each noise model
at p = P_LEAD matched by (detectors, observables) signature.  Union form: an estimate, not a bound.

  PYTHONPATH=.:tests uv run python -m search.experiments.e033.lead --circ ibm --W 10 --bases ZX --R 1 2 3
Output: results/E-033-gross-u11-ler/lead_<circ>_W<W>_<bases>.json (per basis, per R)."""
import argparse
import json

import numpy as np

from search.experiments.e029.export import dem_columns, translations_dem
from search.experiments.e033.common import OUT, noisy

P_LEAD = 1e-4


def esym(q, k):
    e = np.zeros(k + 1); e[0] = 1.0
    for x in q:
        e[1:] = e[1:] + x * e[:-1]
    return e[k]


def read_sols(circ, basis, R, W):
    f = OUT / "runs" / f"{circ}_{basis}_R{R}_enum{W}.txt"
    files = [f] if f.exists() else sorted((OUT / "runs").glob(f"{circ}_{basis}_R{R}_enum{W}_o*.txt"))  # orbit-range parts
    assert files, f
    sols, done = [], []
    covered = set()
    for g in files:
        txt = g.read_text()
        d = [ln for ln in txt.splitlines() if ln.startswith("DONE")]
        assert d and ("ENUMERATED" in d[0] or "NONE" in d[0]), (g, d)
        rng = [ln for ln in txt.splitlines() if ln.startswith("INST")][0].split("orbits=[")[1].rstrip(")").split(",")
        covered |= set(range(int(rng[0]), int(rng[1])))
        norb = int([ln for ln in txt.splitlines() if ln.startswith("INST")][0].split("norb=")[1].split()[0])
        done.append(d[0])
        sols += [tuple(int(x) for x in ln.split(":")[1].split()) for ln in txt.splitlines() if ln.startswith("SOL")]
    assert covered == set(range(norb)), ("orbit ranges incomplete", files)
    return sols, " | ".join(done)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--circ", required=True)
    ap.add_argument("--W", type=int, required=True)
    ap.add_argument("--R", type=int, nargs="+", required=True)
    ap.add_argument("--bases", default="ZX")
    ap.add_argument("--models", default="lam0,lam0.1,lam1")
    a = ap.parse_args()
    models = a.models.split(",")
    res = {"circ": a.circ, "W": a.W, "P_LEAD": P_LEAD, "per_R": {}}
    k = (a.W + 1) // 2
    for b in a.bases:
        for R in a.R:
            sols, done = read_sols(a.circ, b, R, a.W)
            assert all(len(S) == a.W for S in sols), "solution of lower weight present"
            dem, cols = dem_columns(noisy(a.circ, b, R, 1e-3, "lam1"))
            cols = [c for c in cols if c[0] or c[1]]
            group, _ = translations_dem(dem, cols, 12, 6)
            assert len(group) == 72
            full = set()
            for S in sols:
                for _, perm in group:
                    full.add(tuple(sorted(perm[j] for j in S)))
            for S in full:
                d, o = set(), set()
                for j in S:
                    d ^= set(cols[j][0]); o ^= set(cols[j][1])
                assert not d and o and len(set(S)) == a.W
            row = {"n_logicals": len(full), "n_root_solutions": len(sols), "enum": done}
            for m in models:
                circ = noisy(a.circ, b, R, P_LEAD, m)
                _, cm = dem_columns(circ)
                dm = circ.detector_error_model(decompose_errors=False)
                pr = {}
                for inst, key in zip([i for i in dm.flattened() if i.type == "error"], cm):
                    pr[key] = pr.get(key, 0.0) + inst.args_copy()[0]
                tot, dead = 0.0, 0
                for S in full:
                    q = [pr.get(cols[j], 0.0) for j in S]
                    dead += any(x == 0 for x in q)
                    tot += esym(q, k) * (0.5 if a.W % 2 == 0 else 1.0)
                row[m] = {"A": tot / P_LEAD ** k, "dead_logicals": dead}
            res["per_R"][f"{b}{R}"] = row
            print(b, R, json.dumps(row), flush=True)
    summ = {}
    for b in a.bases:
        Rs = sorted(a.R)
        summ[b] = {"counts": [res["per_R"][f"{b}{R}"]["n_logicals"] for R in Rs],
                   "count_diffs": [res["per_R"][f"{b}{R2}"]["n_logicals"] - res["per_R"][f"{b}{R1}"]["n_logicals"]
                                   for R1, R2 in zip(Rs, Rs[1:])]}
        for m in models:
            summ[b][m] = [res["per_R"][f"{b}{R2}"][m]["A"] - res["per_R"][f"{b}{R1}"][m]["A"] for R1, R2 in zip(Rs, Rs[1:])]
    res["per_round"] = summ
    print(json.dumps(summ), flush=True)
    (OUT / f"lead_{a.circ}_W{a.W}_{a.bases}_R{'-'.join(map(str, a.R))}.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
