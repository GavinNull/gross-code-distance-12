"""Audit E-021 (b5): lift-independent exact lower bound attempt via the evaluator's public lower_bound
(RC2 MaxSAT on stim's shortest_error_sat_problem, or CP-SAT with target).
    PYTHONPATH=.:tests uv run python research/audits/2026-10-10-E-021-scripts/b5_lower.py basis R method seconds [target]
"""
import json, sys, time
sys.path.insert(0, "research/audits/2026-10-10-E-021-scripts")
from b_common import *
from evaluators.distance import lower_bound

basis, R, method, sec = sys.argv[1], int(sys.argv[2]), sys.argv[3], float(sys.argv[4])
target = int(sys.argv[5]) if len(sys.argv) > 5 else None
c = add_noise(build_circuits(load_spec().canonical(), code, R)[basis], "sd6", 1e-3)
r = lower_bound(c, method=method, time_limit_s=sec, target=target, seed=11)
print(r, flush=True)
json.dump(str(r), open(f"{OUT}/b5_{basis}_R{R}_{method}_{target}.json", "w"))
