"""A6: c13 vs c16 -- DEM signature sets (detector set, observable set) on the OWN encoder, SD6 lam = 1, R = 1..12,
both bases.  Equal sets => identical minimum undetected-logical weight at every such R.
    uv run python research/audits/2026-10-22-E-030-scripts/a6_c13_sig.py"""
import json, sys
sys.path.insert(0, "research/audits/2026-10-22-E-030-scripts")
from mylib import *
a, b = load_spec("search/experiments/e030/c13_spec.json"), load_spec("search/experiments/e028/c16_spec.json")
res = {}
for R in range(1, 13):
    for B in "ZX":
        sa = {(d, o) for d, o, _ in dem_terms(memory_circuit(a, B, R, 1e-3))[0]}
        sb = {(d, o) for d, o, _ in dem_terms(memory_circuit(b, B, R, 1e-3))[0]}
        res[f"{B}{R}"] = [len(sa), len(sb), sa == sb]
        print(B, R, res[f"{B}{R}"], flush=True)
json.dump(res, open("results/E-030-audit/a6_c13_sig.json", "w"), indent=1)
