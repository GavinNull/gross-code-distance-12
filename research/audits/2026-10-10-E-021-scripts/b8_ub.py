"""Audit E-021 (b8): heuristic attack with the evaluator's public upper_bound (stim search + BP-OSD + LNS),
new seeds, many R. Any verified witness of weight <= 11 would refute the claim.
    PYTHONPATH=.:tests uv run python research/audits/2026-10-10-E-021-scripts/b8_ub.py basis R seed trials max_sec
"""
import json, sys
sys.path.insert(0, "research/audits/2026-10-10-E-021-scripts")
from b_common import *
from evaluators.distance import upper_bound

basis, R, seed, trials, msec = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), float(sys.argv[5])
c = add_noise(build_circuits(load_spec().canonical(), code, R)[basis], "sd6", 1e-3)
r = upper_bound(c, seed=seed, bposd_trials=trials, num_workers=1, max_seconds=msec, stim_search_timeout_s=300)
w = r.weight
meth = r.summary()
rec = {"basis": basis, "R": R, "seed": seed, "trials": trials, "upper_bound": w, "methods": meth, "hist": r.low_weight_histogram, "sec": r.seconds, "early": r.stopped_early}
print(rec, flush=True)
with open(f"{OUT}/b8_ub.jsonl", "a") as f:
    f.write(json.dumps(rec) + "\n")
