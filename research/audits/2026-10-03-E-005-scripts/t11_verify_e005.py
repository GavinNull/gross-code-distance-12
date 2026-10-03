"""Independent verification of E-005's published witnesses with the auditor's own code construction.
A witness ('q', j) / ('r', support) is accepted iff every residual support is a suffix of the stated check order(s)
in the AUDITOR's construction, and the propagated data error is an X-type (or Z-type) nontrivial logical."""
import sys, json
sys.path.insert(0, "research/audits/2026-10-03-E-005-scripts")
from audext import *
E5 = "results/E-005-noninterleaved-bound/"
out = {}

def check(code, et, allowed, wit, cap):
    H, L = code.det(et)
    v = np.zeros(code.n, dtype=np.int64)
    bad = []
    for kind, s in wit:
        if kind == "q":
            v[s] ^= 1
        else:
            if frozenset(s) not in allowed:
                bad.append(s)
            for j in s:
                v[j] ^= 1
    ok_logical = (not ((H.astype(int) @ v) % 2).any()) and bool(((L.astype(int) @ v) % 2).any())
    return {"weight": len(wit), "le_cap": len(wit) <= cap, "residuals_valid": not bad, "logical": ok_logical,
            "ok": (not bad) and ok_logical and len(wit) <= cap}

for cname, tag in [("bb90", "90_8_10"), ("bb108", "108_8_10")]:
    code = Code(cname)
    # single-check files
    d = json.load(open(E5 + f"single_{tag}.json"))
    for et in "XZ":
        res = d["types"][et]["results"]
        oks = []
        for r in res:
            order = check_order_from_terms(code, et, 0, r["key"])
            allowed = {frozenset(S) for S in suffixes(order)}
            c = check(code, et, allowed, r["witness"], r["upper"])
            oks.append(c["ok"] and c["weight"] == r["upper"])
        out[f"single_{cname}_{et}"] = {"n": len(res), "all_ok": all(oks), "n_ok": sum(oks),
                                      "hist_upper": d["types"][et]["hist_upper"]}
    # uniform target files
    for fn in [f"target9_{tag}_X.json", f"target10_{tag}_X.json", f"target9_{tag}_Z.json"]:
        try:
            d = json.load(open(E5 + fn))
        except FileNotFoundError:
            continue
        for et, t in d["types"].items():
            rows = []
            for r in t["results"]:
                if not r.get("witness"):
                    rows.append({"key": r["key"], "status": r["status"], "checked": False}); continue
                nrow = code.HX.shape[0]
                allowed = {frozenset(S) for i in range(nrow) for S in suffixes(check_order_from_terms(code, et, i, r["key"]))}
                c = check(code, et, allowed, r["witness"], d["target"] - 1)
                c.update(key=r["key"], status=r["status"], checked=True)
                rows.append(c)
            out[f"{fn}:{et}"] = {"n_results": len(rows), "n_witness_ok": sum(1 for x in rows if x.get("ok")),
                                "n_witness_bad": sum(1 for x in rows if x["checked"] and not x["ok"]),
                                "no_witness": [x["key"] for x in rows if not x["checked"]],
                                "classes_in_feasible": t.get("classes_in_feasible"),
                                "classes_passing_single_bound": t.get("classes_passing_single_bound")}
    sp = json.load(open(E5 + f"space_{tag}.json"))
    out[f"space_{cname}"] = {"x_classes_in_feasible": sp["x_classes_in_feasible"], "z_classes_in_feasible": sp["z_classes_in_feasible"],
                             "stats": sp["stats"], "num_feasible": sp["num_feasible"]}
for k, v in out.items():
    print(k, json.dumps(v)[:700])
json.dump(out, open("results/E-005-audit/t11_verify_e005.json", "w"), indent=1)
