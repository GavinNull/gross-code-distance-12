"""Independent check of the depth-8 uniform space for selected X term-order classes: count conflict-free completions
(P_Z, sigma_Z) and test each with the auditor's own partition (SCC) criterion."""
import sys, json, itertools, time
sys.path.insert(0, "research/audits/2026-10-03-E-005-scripts")
from audext import *
from usched import uniform_schedule

def conflict_free(PX, sX, PZ, sZ):
    tx = {t: (PX + 1 + k) % 8 for k, t in enumerate(sX)}
    tz = {t: (PZ + 1 + k) % 8 for k, t in enumerate(sZ)}
    Ls = [tx[0], tx[1], tx[2], tz[3], tz[4], tz[5]]   # L data: X via A terms, Z via B terms
    Rs = [tx[3], tx[4], tx[5], tz[0], tz[1], tz[2]]
    return len(set(Ls)) == 6 and len(set(Rs)) == 6

if __name__ == "__main__":
    name = sys.argv[1]
    classes = [list(map(int, s)) for s in sys.argv[2].split(",")]
    code = Code(name)
    tcl = term_order_classes(code, "X")
    out = {}
    t0 = time.time()
    for rep in classes:
        cl = next(c for c in tcl if list(c[0]) == rep)
        comps = [(sX, PZ, sZ) for sX in cl for PZ in range(8) for sZ in itertools.permutations(range(6))
                 if conflict_free(0, sX, PZ, sZ)]
        part = 0
        for sX, PZ, sZ in comps:
            s = uniform_schedule(code, 0, list(sX), PZ, list(sZ))
            if pairwise_and_partition(s, 4)["partitionable"]:
                part += 1
        out["".join(map(str, rep))] = {"conflict_free": len(comps), "partitionable": part}
        print(rep, out["".join(map(str, rep))], round(time.time() - t0, 1), flush=True)
    json.dump(out, open(f"results/E-005-audit/t12_space_{name}.json", "w"), indent=1)
