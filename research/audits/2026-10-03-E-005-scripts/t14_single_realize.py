"""Prop.-4 mechanism check: single-check extended code of the ACTUAL check-0 order of a circuit -> min-weight witness
-> realise as circuit faults (hooks only on check 0) by injection."""
import sys, json
sys.path.insert(0, "research/audits/2026-10-03-E-005-scripts")
from audext import *
from t4_fullE import load
from realize import realize
if __name__ == "__main__":
    which, et, row = sys.argv[1], sys.argv[2], int(sys.argv[3])
    code, sched = load(which)
    o = orders_from_schedule(sched)[et][row]
    res = [tuple(o[l:]) for l in range(2, 5)]
    H, L = code.det(et)
    M, rH = ext_matrix(H, L, res)
    r = highs_fixed(M, rH, code.nkd[2], 600)
    sup = [int(j) for j in np.nonzero(r["x"])[0]]
    data = [j for j in sup if j < code.n]; hooks = [(row, 2 + (j - code.n)) for j in sup if j >= code.n]
    rz = realize(sched, code, et, data, hooks, rounds=3)
    out = {"which": which, "type": et, "row": row, "order": o, "single_dext": r["value"], "status": r["status"],
           "data": data, "hooks": hooks, "realization": {k: v for k, v in rz.items()}}
    print(json.dumps({k: v for k, v in out.items() if k != "realization"}), {k: v for k, v in rz.items() if k != "faults"})
    json.dump(out, open(f"results/E-005-audit/single_realize_{which.split(':')[-1] if ':' in which else which}_{et}{row}.json", "w"), indent=1)
