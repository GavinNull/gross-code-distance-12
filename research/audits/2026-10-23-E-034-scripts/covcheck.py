"""Auditor (E-034): independent coverage check of the lift certificates of c11 (E-031 + E-034), c12, c13 (E-034).
For every (circuit, basis, R) required: union of batch records; a batch counts as certified iff some record of it has
solver UNSAT, drat-trim VERIFIED and cake_lpr VERIFIED UNSAT (records may come from different runs only when the CNF
sha256 is identical, i.e. the same formula).  Batches s = 0..K-1 must all be certified, member counts must add up to
nA + nB = 585 + 16830, the batch index formula idx = range(s, N, K) must partition 0..N-1 (checked from counts).
    uv run python covcheck.py
"""
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
src = {"c11": ["results/E-031-xor-certificates/lift/c11/results.jsonl", "results/E-034-veripb3-u11/lift/c11/results.jsonl",
               "results/E-034-veripb3-u11/lift/c11_cake/results.jsonl"],
       "c12": ["results/E-034-veripb3-u11/lift/c12/results.jsonl"],
       "c13": ["results/E-034-veripb3-u11/lift/c13/results.jsonl"]}
need = {"c11": range(1, 26), "c12": range(1, 13), "c13": range(1, 13)}
out = {}
for c, files in src.items():
    recs = defaultdict(list)
    for f in files:
        for l in open(ROOT / f):
            r = json.loads(l); recs[r["name"]].append(r)
    res = {"records": sum(len(v) for v in recs.values()), "batches": len(recs), "missing": [], "uncertified": [],
           "sha_conflicts": [], "count_mismatch": []}
    nb = nd = nk = 0
    for b in ("Z", "X"):
        for R in need[c]:
            names = [n for n in recs if recs[n][0]["basis"] == b and recs[n][0]["R"] == R]
            if not names:
                res["missing"].append((b, R, "no batch")); continue
            Ks = {recs[n][0]["split"][1] for n in names}
            assert len(Ks) == 1, (c, b, R, Ks)
            K = Ks.pop()
            ss = sorted(recs[n][0]["split"][0] for n in names)
            if ss != list(range(K)):
                res["missing"].append((b, R, f"splits {len(ss)}/{K}"))
            N = recs[names[0]][0]["dem"]["nA"] + recs[names[0]][0]["dem"]["nB"]
            tot = 0
            for n in names:
                rs = recs[n]
                if len({r["cnf_sha256"] for r in rs}) != 1:
                    res["sha_conflicts"].append(n)
                s = rs[0]["split"][0]
                if any(r["instances"] != len(range(s, N, K)) for r in rs):
                    res["count_mismatch"].append(n)
                tot += rs[0]["instances"]
                dt = any(r["solver"]["answer"] == "UNSAT" and r.get("drat_trim", {}).get("verdict") == "VERIFIED" for r in rs)
                ck = any(r["solver"]["answer"] == "UNSAT" and r.get("cake_lpr", {}).get("verdict") == "VERIFIED UNSAT" for r in rs)
                nb += 1; nd += dt; nk += ck
                if not (dt and ck):
                    res["uncertified"].append((n, dt, ck))
            if tot != N:
                res["count_mismatch"].append((b, R, tot, N))
    res.update(batches_required=nb, drat_trim_ok=nd, cake_lpr_ok=nk, R=[min(need[c]), max(need[c])])
    res["ok"] = not (res["missing"] or res["uncertified"] or res["sha_conflicts"] or res["count_mismatch"])
    out[c] = res
    print(c, json.dumps(res))
json.dump(out, open(ROOT / "results/E-034-audit/covcheck.json", "w"), indent=1)
