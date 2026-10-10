"""E-021: exact-lift screen of many candidate schedules in the Fig. 12 extended-code class.
For each spec: R = 1 basis Z, then X, then R = 2..Rmax both bases; stops at the first lifting logical (counts the
number of lifting logicals at the stage where it failed).  Also asserts legality and determinism (DEM build).

    PYTHONPATH=.:tests uv run python -m search.experiments.e021.liftscreen out.jsonl spec0.json spec1.json ...
"""
import json
import sys
import time

from evaluators.candidate import parse_schedule
from search.experiments.e018.lift import solve
from search.experiments.e021.extgen import ext_general
from search.experiments.e021.lift21 import KIND_OF_BASIS, build_groups, label_orders, w11_from_fig12

RMAX = 6


def screen(path, rmax=RMAX, count_all_first=False):
    spec = parse_schedule(json.load(open(path))).canonical()
    lo = label_orders(spec)
    Es, sols = {}, {}
    for b in "ZX":
        k = KIND_OF_BASIS[b]
        Es[b] = ext_general(k, lo[k])
        sols[b] = w11_from_fig12(k, Es[b])
    for R in range(1, rmax + 1):
        for b in "ZX":
            try:
                groups, _ = build_groups(spec, R, b, Es[b])
            except Exception as e:  # non-deterministic / illegal
                return {"spec": path, "status": "error", "err": str(e)[:200]}
            n = 0
            for S in sols[b]:
                if solve(S, groups)[0] is not None:
                    n += 1
                    if not (count_all_first and R == 1):
                        break
            if n:
                return {"spec": path, "status": "lifts", "R": R, "basis": b, "lifting": n}
    return {"spec": path, "status": "CERTIFIED", "R": rmax}


if __name__ == "__main__":
    out = sys.argv[1]
    for p in sys.argv[2:]:
        t = time.time()
        r = screen(p)
        r["sec"] = round(time.time() - t, 1)
        with open(out, "a") as f:
            f.write(json.dumps(r) + "\n")
        if r["status"] == "CERTIFIED":
            print("CERTIFIED", p, flush=True)
