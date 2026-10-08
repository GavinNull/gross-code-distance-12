"""Audit E-018 (a9): re-run the experimenter's exact lift checker (lift.build_groups / lift.solve, unmodified) on
Fig. 12 at R = 1..3, both bases, all 4224 logicals; output to results/E-018-audit (not the experimenter's dir)."""
import json, pickle, sys, time
sys.path.insert(0, "tests")
from search.experiments.e018.lift import spec_of, check_orders, build_groups, solve, KIND_OF_BASIS
spec = spec_of("fig12").canonical(); check_orders(spec)
out = []
for R in (1, 2, 3):
    for b in "ZX":
        t0 = time.time()
        sols = pickle.load(open(f"results/E-018-gross-interleaved-12/w11_all_{KIND_OF_BASIS[b]}.pkl", "rb"))
        groups, stats, _, _ = build_groups(spec, R, b)
        n = sum(solve(S, groups)[0] is not None for S in sols)
        out.append({"R": R, "basis": b, "lifting": n, "of": len(sols), "aug_terms": stats["aug_terms"],
                    "orig_dem_errors": stats["orig_dem_errors"], "sec": round(time.time() - t0, 1)})
        print(out[-1], flush=True)
json.dump(out, open("results/E-018-audit/a9_fig12.json", "w"), indent=1)
