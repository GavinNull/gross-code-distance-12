"""E-030 leading order (ideal most-likely-error decoder): exact enumeration of the minimum-weight undetected logicals
of each circuit's full SD6 DEM with ccsearch (E-029, 'enum W' after 'decide W-1' = none), expanded by the 45 DEM
translations (found and verified on the DEM by e029.export.translations_dem), counted at R = 2..Rmax; per-round count
= N(R+1) - N(R) (saturation check: the differences must be constant).  Coefficient of the leading power
p^{ceil(w/2)} per round: for even w, A = (1/2) sum_L e_{w/2}(q_L) / p^{w/2} (exact half-half ties counted 1/2);
for odd w, A = sum_L e_{(w+1)/2}(q_L) / p^{(w+1)/2}; priors q from the DEM of the given noise model at p = P_LEAD,
matched by (detectors, observables) signature.  Union form (a subset shared by several logicals counts several times),
so it is an estimate, not a bound (E-023 audit wording).

  PYTHONPATH=.:tests uv run python -m search.experiments.e030.lead --circ ibm --W 8 --R 1 2 3 4 --models lam0,lam0.1,lam0.3,lam1
"""
import argparse
import itertools
import json
import subprocess
from pathlib import Path

import numpy as np

from search.experiments.e029.export import dem_columns, translations_dem
from search.experiments.e030.common import OUT, noisy

P_LEAD = 1e-4
BIN = OUT / "ccsearch"


def esym(q, k):
    e = np.zeros(k + 1); e[0] = 1.0
    for x in q:
        e[1:] = e[1:] + x * e[:-1]
    return e[k]


def run_enum(circ, basis, R, W):
    inst = OUT / "inst" / f"{circ}_{basis}_R{R}.txt"
    if not inst.exists():
        spec = {"ibm": "search/experiments/e030/ibm90_spec.json"}.get(circ, f"search/experiments/e030/{circ}_spec.json")
        if circ == "c16":
            spec = "search/experiments/e028/c16_spec.json"
        subprocess.run(["uv", "run", "python", "-m", "search.experiments.e029.export", "dem", spec, "bb90-dcirc", basis,
                        str(R), str(inst)], check=True, capture_output=True)
    out = OUT / "runs" / f"{circ}_{basis}_R{R}_enum{W}.txt"
    if not (out.exists() and "DONE" in out.read_text()):
        dec = OUT / "runs" / f"{circ}_{basis}_R{R}_decide{W - 1}.txt"
        if not (dec.exists() and "DONE NONE" in dec.read_text()):
            dec.write_text(subprocess.run([str(BIN), str(inst), "decide", str(W - 1)], check=True, capture_output=True,
                                          text=True).stdout)
        assert "DONE NONE" in dec.read_text(), f"weight <= {W - 1} exists: {dec}"
        out.write_text(subprocess.run([str(BIN), str(inst), "enum", str(W)], check=True, capture_output=True,
                                      text=True).stdout)
    sols = [tuple(int(x) for x in ln.split(":")[1].split()) for ln in out.read_text().splitlines() if ln.startswith("SOL")]
    return sols, out.read_text().splitlines()[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--circ", required=True)
    ap.add_argument("--W", type=int, required=True)
    ap.add_argument("--R", type=int, nargs="+", default=[1, 2, 3, 4])
    ap.add_argument("--bases", default="ZX")
    ap.add_argument("--models", default="lam0,lam0.1,lam0.3,lam1")
    a = ap.parse_args()
    models = a.models.split(",")
    res = {"circ": a.circ, "W": a.W, "P_LEAD": P_LEAD, "per_R": {}}
    for b in a.bases:
        for R in a.R:
            sols, done = run_enum(a.circ, b, R, a.W)
            dem, cols = dem_columns(noisy(a.circ, b, R, 1e-3, "lam1"))
            cols = [c for c in cols if c[0] or c[1]]
            group, _ = translations_dem(dem, cols, 15, 3)
            assert len(group) == 45
            full = set()
            for S in sols:
                for _, perm in group:
                    full.add(tuple(sorted(perm[j] for j in S)))
            for S in full:     # every logical re-checked on the DEM
                d, o = set(), set()
                for j in S:
                    d ^= set(cols[j][0]); o ^= set(cols[j][1])
                assert not d and o and len(set(S)) == a.W
            row = {"n_logicals": len(full), "enum": done}
            for m in models:
                _, cm = dem_columns(noisy(a.circ, b, R, P_LEAD, m))
                dm = noisy(a.circ, b, R, P_LEAD, m).detector_error_model(decompose_errors=False)
                pr = {}
                for inst, key in zip([i for i in dm.flattened() if i.type == "error"], cm):
                    pr[key] = pr.get(key, 0.0) + inst.args_copy()[0]   # (no duplicate signatures expected)
                k = (a.W + 1) // 2
                tot, dead = 0.0, 0
                for S in full:
                    q = [pr.get(cols[j], 0.0) for j in S]
                    dead += any(x == 0 for x in q)
                    tot += esym(q, k) * (0.5 if a.W % 2 == 0 else 1.0)
                row[m] = {"A": tot / P_LEAD ** k, "dead_logicals": dead}
            res["per_R"][f"{b}{R}"] = row
            print(b, R, json.dumps(row), flush=True)
    # per round (differences)
    summ = {}
    for b in a.bases:
        Rs = sorted(a.R)
        diffs = [res["per_R"][f"{b}{R2}"]["n_logicals"] - res["per_R"][f"{b}{R1}"]["n_logicals"] for R1, R2 in zip(Rs, Rs[1:])]
        summ[b] = {"count_diffs": diffs}
        for m in models:
            summ[b][m] = [res["per_R"][f"{b}{R2}"][m]["A"] - res["per_R"][f"{b}{R1}"][m]["A"] for R1, R2 in zip(Rs, Rs[1:])]
    res["per_round"] = summ
    print(json.dumps(summ), flush=True)
    (OUT / f"lead_{a.circ}_W{a.W}.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
