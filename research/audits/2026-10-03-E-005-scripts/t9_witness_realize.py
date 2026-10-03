"""Full-E witness at weight <= CAP for a schedule (HiGHS feasibility), then realise it as circuit faults by injection.
usage: t9_witness_realize.py WHICH TYPE CAP TIME"""
import sys, json, time
sys.path.insert(0, "research/audits/2026-10-03-E-005-scripts")
from audext import *
from t4_fullE import load
from realize import realize

which, et, cap, tl = sys.argv[1], sys.argv[2], int(sys.argv[3]), float(sys.argv[4])
code, sched = load(which)
sched.validate(code.HX, code.HZ)
part = pairwise_and_partition(sched, 6)
orders = orders_from_schedule(sched)[et]
res, owner = [], []
for row, o in enumerate(orders):
    for l in range(2, len(o) - 1):
        res.append(tuple(o[l:])); owner.append((row, l))
H, L = code.det(et)
M, rH = ext_matrix(H, L, res)
r = highs_fixed(M, rH, cap, tl, feasibility=True)
out = {"which": which, "type": et, "cap": cap, "partition": part, "ext_shape": list(M.shape),
       "status": r["status"], "seconds": r["seconds"]}
if r.get("x") is not None:
    sup = [int(j) for j in np.nonzero(r["x"])[0]]
    data = [j for j in sup if j < code.n]
    hooks = [owner[j - code.n] for j in sup if j >= code.n]
    out.update(weight=len(sup), data_cols=data, hooks=hooks)
    t0 = time.time()
    rz = realize(sched, code, et, data, hooks, rounds=3)
    rz["seconds"] = round(time.time() - t0, 1)
    out["realization"] = rz
print(json.dumps({k: v for k, v in out.items() if k != "realization"}),
      json.dumps({k: v for k, v in out.get("realization", {}).items() if k != "faults"}))
tag = which.replace(":", "_").replace("/", "_")[-40:]
json.dump(out, open(f"results/E-005-audit/witness_{tag}_{et}_cap{cap}.json", "w"), indent=1)
