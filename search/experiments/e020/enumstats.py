"""E-020 control 2: bulk-model lifting counts (single-hook d10 r21, both kinds) over the SAT-enumerated legal +
deterministic per-check P=9 schedules (plegal_P9.json, 2000 schedules, not uniform samples).

    PYTHONPATH=.:tests uv run python -m search.experiments.e020.enumstats 9
"""
import collections
import json
import sys

from search.experiments.e020.cegar import bellman_ford, prep_logicals

P = int(sys.argv[1])
d = json.load(open(f"results/E-020-gross-perchk-pipeline/plegal_P{P}.json"))
L, _ = prep_logicals("XZ", "single")
cnt = []
for opts in d["sols"]:
    T = {(ci, p): t for ci, o in enumerate(opts) for p, t in enumerate(o)}
    cnt.append(sum(bellman_ford(cons, T, P) is not None for _, _, _, cons in L))
res = {"P": P, "n": len(cnt), "modelled": len(L), "min": min(cnt), "mean": sum(cnt) / len(cnt), "max": max(cnt),
       "hist": sorted(collections.Counter(cnt).items())[:10]}
print(res)
json.dump(res, open(f"results/E-020-gross-perchk-pipeline/enumstats_P{P}.json", "w"))
