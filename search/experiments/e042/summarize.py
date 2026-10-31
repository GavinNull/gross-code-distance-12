"""E-042: summaries.  uv run python -m search.experiments.e042.summarize lift RESULTS.jsonl
Checks per basis that batch numbers 0..K-1 are complete, instance counts add up to 3,204 + 121,104, and every batch
has solver UNSAT, drat-trim VERIFIED, cake_lpr VERIFIED UNSAT; prints totals (CPU, proof bytes)."""
import json
import sys
from collections import defaultdict


def lift(path):
    recs = [json.loads(l) for l in open(path)]
    by = defaultdict(dict)
    for r in recs:
        by[(r["basis"], r["R"])][r["split"][0]] = r
    allok = True
    for (b, R), d in sorted(by.items()):
        K = next(iter(d.values()))["split"][1]
        complete = sorted(d) == list(range(K))
        n = sum(r["instances"] for r in d.values())
        ok = all(r["solver"]["answer"] == "UNSAT" and r["drat_trim"]["verdict"] == "VERIFIED"
                 and r["cake_lpr"]["verdict"] == "VERIFIED UNSAT" for r in d.values())
        s = lambda f: sum(f(r) for r in d.values())
        out = {"basis": b, "R": R, "batches": len(d), "K": K, "complete": complete, "instances": n,
               "expected": 3204 + 121104, "all_verified": ok,
               "clauses_max": max(r["clauses"] for r in d.values()),
               "gen_cpu_h": round(s(lambda r: r["gen_cpu_s"]) / 3600, 2),
               "cadical_cpu_h": round(s(lambda r: r["solver"]["cpu_s"]) / 3600, 2),
               "drat_trim_cpu_h": round(s(lambda r: r["drat_trim"]["cpu_s"]) / 3600, 2),
               "cake_lpr_cpu_h": round(s(lambda r: r["cake_lpr"]["cpu_s"]) / 3600, 2),
               "drat_GB": round(s(lambda r: r["drat_bytes"]) / 1e9, 2),
               "lrat_GB": round(s(lambda r: r["lrat_bytes"]) / 1e9, 2),
               "setup_cpu_s": next(iter(d.values()))["dem"]["setup_cpu_s"]}
        allok &= complete and ok and n == 3204 + 121104
        print(json.dumps(out))
    print("ALL VERIFIED" if allok else "INCOMPLETE OR FAILED")


if __name__ == "__main__":
    {"lift": lift}[sys.argv[1]](sys.argv[2])
