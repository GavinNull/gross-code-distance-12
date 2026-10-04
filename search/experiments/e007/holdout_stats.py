import json, math, sys
import numpy as np
from search.experiments.e007 import common as C

rng = np.random.default_rng(0)
def paired(task):
    d = json.load(open(C.RESULTS / f"holdout-direct-{task}.json"))
    arr = {k: np.load(C.RESULTS / f"holdout-direct-{task}-{k}.npz") for k in d["cfgs"]}
    bs = 1000
    n = len(arr["paper"]["fz"]); nb = n // bs
    def agg(k):
        z, x = arr[k]["fz"][:nb*bs].reshape(nb, bs), arr[k]["fx"][:nb*bs].reshape(nb, bs)
        c = (arr[k]["cz"] + arr[k]["cx"])[:nb*bs].reshape(nb, bs)
        return (z | x).sum(1), z.sum(1), x.sum(1), c.sum(1)
    P = agg("paper")
    print(task, "shots", nb*bs, "paper fail_any", P[0].sum(), "Z", P[1].sum(), "X", P[2].sum())
    res = {}
    for k in d["cfgs"]:
        if k == "paper": continue
        A = agg(k)
        out = {"fail_any": int(A[0].sum()), "Z": int(A[1].sum()), "X": int(A[2].sum()), "cpu_ratio": float(A[3].sum()/P[3].sum())}
        boots = []
        for _ in range(4000):
            i = rng.integers(0, nb, nb)
            boots.append(A[0][i].sum()/P[0][i].sum() - 1)
        out["rel_any"] = float(A[0].sum()/P[0].sum()-1); out["rel_any_ci"] = [float(np.percentile(boots,2.5)), float(np.percentile(boots,97.5))]
        res[k] = out
        print(" ", k, out)
    res["paper"] = {"fail_any": int(P[0].sum()), "Z": int(P[1].sum()), "X": int(P[2].sum()), "shots": nb*bs}
    json.dump(res, open(C.RESULTS / f"holdout-direct-{task}-stats.json", "w"), indent=1)
def restricted(task):
    L = json.load(open(C.RESULTS / f"holdout-restricted-{task}.json"))
    res = []
    for d in L:
        c, r = d["counts"], d["ref_counts"]
        oc = sum(d["overlap"][s]["only_candidate"] for s in "ZX"); orf = sum(d["overlap"][s]["only_reference"] for s in "ZX")
        ref_sum = r["fail_Z"] + r["fail_X"]; delta = (c["fail_Z"] + c["fail_X"]) - ref_sum
        se = math.sqrt(oc + orf)
        o = {"eval": d["eval_index"], "shots": d["shots"], "cand_any": c["fail_any"], "ref_any": r["fail_any"],
             "P_cand": c["fail_any"]/d["shots"], "P_ref": r["fail_any"]/d["shots"], "rel_any": c["fail_any"]/r["fail_any"]-1,
             "rel_sectorsum": delta/ref_sum, "rel_sectorsum_ci": [(delta-1.96*se)/ref_sum, (delta+1.96*se)/ref_sum],
             "cpu_ratio": d["speed"]["ratio_to_reference"], "search_score": d["search_score"],
             "sectors": {s: {k: v for k, v in d["sectors"][s].items() if k in ("failures","wrong","timeout","budget")} for s in "ZX"}}
        res.append(o); print(o)
    json.dump(res, open(C.RESULTS / f"holdout-restricted-{task}-stats.json", "w"), indent=1)
if __name__ == "__main__":
    for a in sys.argv[1:]:
        kind, task = a.split(":")
        (paired if kind == "direct" else restricted)(task)
