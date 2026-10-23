"""E-034: coverage summary of lift certificate records (results.jsonl).  Checks per (basis, R) that the batches
s = 0..K-1 are all present and that the instance counts add up to the list sizes (nA + nB)."""
import json
import sys
from collections import defaultdict

for f in sys.argv[1:]:
    rs = [json.loads(l) for l in open(f)]
    by = defaultdict(list)
    for r in rs:
        by[(r["basis"], r["R"])].append(r)
    cov, bad = [], []
    for (b, R), L in sorted(by.items(), key=lambda t: (t[0][1], t[0][0])):
        K = L[0]["split"][1]
        full = sorted(r["split"][0] for r in L) == list(range(K))
        n = sum(r["instances"] for r in L); tot = L[0]["dem"]["nA"] + L[0]["dem"]["nB"]
        allok = all(r["ok"] and r["solver"]["answer"] == "UNSAT" and r["drat_trim"]["verdict"] == "VERIFIED"
                    and r["cake_lpr"]["verdict"] == "VERIFIED UNSAT" for r in L)
        (cov if (full and n == tot and allok) else bad).append((b, R, len(L), n, tot, full, allok))
    cpu = sum(r["solver"]["cpu_s"] + r.get("drat_trim", {}).get("cpu_s", 0) + r.get("cake_lpr", {}).get("cpu_s", 0) for r in rs)
    Rs = sorted({R for _, R, *_ in cov})
    print(json.dumps({"file": f, "batches": len(rs), "ok": sum(r["ok"] for r in rs),
                      "complete_(basis,R)": len(cov), "R": [min(Rs), max(Rs)] if Rs else None,
                      "bases": sorted({b for b, *_ in cov}), "instances": sum(c[3] for c in cov),
                      "incomplete_or_failed": bad, "tool_cpu_h": round(cpu / 3600, 2),
                      "cnf_sha_equal_E031": sum(1 for r in rs if r.get("e031_cnf_sha256_equal")),
                      "drat_sha_equal_E031": sum(1 for r in rs if r.get("e031_drat_sha256_equal"))}))
