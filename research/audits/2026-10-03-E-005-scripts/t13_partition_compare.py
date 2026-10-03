"""Compare the auditor's partition criterion (finite-unroll SCC) with E-005's classification of the depth-8 uniform
space (feasible list = 'non-interleaved'), on random samples: 150 from E-005's feasible list, 150 conflict-free
schedules NOT in it (stratified: pairwise-consistent ones are the interesting part)."""
import sys, json, itertools, random
sys.path.insert(0, "research/audits/2026-10-03-E-005-scripts")
from audext import *
from usched import uniform_schedule
from t12_uniform_space import conflict_free
random.seed(1)
code = Code("bb90")
d = json.load(open("results/E-005-noninterleaved-bound/space_90_8_10.json"))
feas = {(tuple(a), b, tuple(c)) for a, b, c, _ in d["feasible"]}
fl = sorted(feas)
res = {"in_feasible": {"n": 0, "partitionable": 0, "pairwise": 0}, "not_in_feasible": {"n": 0, "partitionable": 0, "pairwise": 0}}
for sX, PZ, sZ in random.sample(fl, 150):
    r = pairwise_and_partition(uniform_schedule(code, 0, list(sX), PZ, list(sZ)), 4)
    res["in_feasible"]["n"] += 1; res["in_feasible"]["partitionable"] += r["partitionable"]; res["in_feasible"]["pairwise"] += r["pairwise_noninterleaved"]
perms = list(itertools.permutations(range(6)))
cnt = 0
while res["not_in_feasible"]["pairwise"] < 60 and cnt < 4000:
    sX, PZ, sZ = random.choice(perms), random.randrange(8), random.choice(perms)
    cnt += 1
    if not conflict_free(0, sX, PZ, sZ) or (sX, PZ, sZ) in feas:
        continue
    r = pairwise_and_partition(uniform_schedule(code, 0, list(sX), PZ, list(sZ)), 4)
    res["not_in_feasible"]["n"] += 1; res["not_in_feasible"]["partitionable"] += r["partitionable"]; res["not_in_feasible"]["pairwise"] += r["pairwise_noninterleaved"]
print(res)
json.dump(res, open("results/E-005-audit/t13_partition_compare.json", "w"), indent=1)
