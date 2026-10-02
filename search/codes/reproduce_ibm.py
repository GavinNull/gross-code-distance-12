"""Re-generate the BB codes of arXiv:2308.07915 Table 3 with the search.codes tool chain.

    uv run python -m search.codes.reproduce_ibm --out results/codes-screen-pilot --workers 3

Checks: n, k must match exactly; BP-OSD upper bound on d must be >= the paper value (a smaller value
would be an explicit lower-weight logical, i.e. a bug or an error in the paper); for n <= --milp-max-n
the exact distance is computed by MILP; the default IBM schedule built through our adapter must be
identical (layer by layer) to baselines.schedule.ibm_depth8 on the same code.
"""
from __future__ import annotations

import os

os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse
import csv
import json
import time
from multiprocessing import Pool
from pathlib import Path

from search.codes.catalog import IBM_TABLE3
from search.codes.constraints import check_constraints
from search.codes.construct import bb_code, to_baseline_bbcode
from search.codes.distance import distance_exact_milp, distance_upper_bound_bposd
from search.codes.equivalence import canonical_key
from search.codes.schedule import check_schedule, default_schedule

RESULTS = Path(__file__).resolve().parents[2] / "results"


def _job(args):
    row, trials, budget, milp_max_n, milp_time, seed = args
    name, l, m, A, B, n_p, k_p, d_p, kind_p = row
    t0 = time.time()
    c = bb_code(l, m, A, B, name=name)
    rec = {"code": name, "l": l, "m": m, "A": A, "B": B, "n_paper": n_p, "k_paper": k_p, "d_paper": d_p,
           "d_paper_kind": kind_p, "n": c.n, "k": c.k, "key": str(canonical_key(c))}
    con = check_constraints(c)
    rec.update({"max_row_weight": con["max_row_weight"], "max_qubit_degree": con["max_qubit_degree"],
                "connected": con["connected"], "thickness": con["thickness"],
                "thickness_split": con["thickness_split"]})
    bb = to_baseline_bbcode(c)
    rec["matrices_equal_baselines_BBCode"] = bool((bb.HX == c.HX).all() and (bb.HZ == c.HZ).all())
    from baselines.schedule import ibm_depth8
    s_ours, s_base = default_schedule(c), ibm_depth8(bb)
    rec["schedule_equal_baselines_ibm_depth8"] = s_ours.layers == s_base.layers
    if c.n <= 288:
        rec["schedule_deterministic"] = check_schedule(c, s_ours, rounds=(1, 2), shots=8)["deterministic"]
    css = c.to_css()
    ub = distance_upper_bound_bposd(css, trials=trials, time_budget=budget, seed=seed, symmetric=True)
    rec["d_ub_bposd"] = ub["d_ub"]
    rec["bposd_trials"] = ub["Z_trials"]
    rec["bposd_hist"] = ub["Z_hist"]
    rec["bposd_seconds"] = round(ub["seconds"], 1)
    rec["d_lower_milp"] = rec["d_upper_milp"] = rec["d_exact"] = None
    if c.n <= milp_max_n:
        ex = distance_exact_milp(css, time_limit=milp_time, upper=ub["d_ub"], symmetric=True, translation_n2=c.n2)
        rec["d_lower_milp"], rec["d_upper_milp"] = ex["d_lower"], ex["d_upper"]
        rec["d_exact"] = ex["d_upper"] if ex["exact"] else None
        rec["milp_seconds"] = round(ex["seconds"], 1)
    rec["nk_match"] = (rec["n"], rec["k"]) == (n_p, k_p)
    rec["d_ub_ge_paper"] = ub["d_ub"] >= d_p
    rec["seconds"] = round(time.time() - t0, 1)
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(RESULTS / "codes-screen-pilot"))
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--trials", type=int, default=2000)
    ap.add_argument("--budget", type=float, default=600.0)
    ap.add_argument("--milp-max-n", type=int, default=288)
    ap.add_argument("--milp-time", type=float, default=1800.0)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    assert a.workers <= 3
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    jobs = [(row, a.trials, a.budget, a.milp_max_n, a.milp_time, a.seed + i) for i, row in enumerate(IBM_TABLE3)]
    jobs.sort(key=lambda j: -j[0][5])   # big codes first
    t0 = time.time()
    with Pool(a.workers) as pool:
        recs = pool.map(_job, jobs, chunksize=1)
    recs.sort(key=lambda r: r["n"])
    cols = ["code", "l", "m", "A", "B", "n_paper", "n", "k_paper", "k", "nk_match", "d_paper", "d_paper_kind",
            "d_ub_bposd", "d_ub_ge_paper", "d_lower_milp", "d_upper_milp", "d_exact", "bposd_trials",
            "bposd_seconds", "milp_seconds", "max_row_weight", "max_qubit_degree", "connected", "thickness",
            "thickness_split", "matrices_equal_baselines_BBCode", "schedule_equal_baselines_ibm_depth8",
            "schedule_deterministic", "seconds"]
    with open(out / "ibm_table3_check.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(recs)
    with open(out / "ibm_table3_check.json", "w") as f:
        json.dump({"records": recs, "total_seconds": round(time.time() - t0, 1), "args": vars(a)}, f, indent=1,
                  default=str)
    for r in recs:
        print({k: r.get(k) for k in cols})


if __name__ == "__main__":
    main()
