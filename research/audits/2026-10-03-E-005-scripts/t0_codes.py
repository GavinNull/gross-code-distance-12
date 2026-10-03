"""Code consistency (task item 5) + class counts."""
import json, sys
import numpy as np
sys.path.insert(0, "research/audits/2026-10-03-E-005-scripts")
from audext import Code, single_check_classes, CODE_DEFS
from evaluators.tasks import bb_matrices, get_task
from search.codes.catalog import IBM_TABLE3
from baselines.bb_code import BBCode, gf2_rank
out = {}
cat = {r[0]: r for r in IBM_TABLE3}
for name, catname, task in [("bb90","[[90,8,10]]","bb90-dcirc"),("bb108","[[108,8,10]]","bb108-dcirc"),("gross","[[144,12,12]]","gross-dcirc")]:
    c = Code(name)
    l, m, A, B, nkd = CODE_DEFS[name]
    r = cat[catname]
    t = get_task(task)
    fam = t.code_family["fixed"]
    HXt, HZt = bb_matrices(fam["l"], fam["m"], fam["A"], fam["B"])
    same_task = (HXt == c.HX).all() and (HZt == c.HZ).all()
    same_cat = (r[1], r[2]) == (l, m)
    d = {"n": c.n, "k": c.k, "task_l_m_A_B": fam, "catalog": r[:5], "HX_HZ_equal_task": bool(same_task),
         "catalog_lm_equal": same_cat, "rank_HX": int(gf2_rank(c.HX)), "rank_HZ": int(gf2_rank(c.HZ))}
    if "1" not in B:
        bb = BBCode(l, m, A, B)
        d["HX_equal_baselines_BBCode"] = bool((bb.HX == c.HX).all() and (bb.HZ == c.HZ).all())
    for ct in "XZ":
        cl = single_check_classes(c, ct, 0)
        d[f"classes_{ct}"] = len(cl)
        d[f"class_sizes_{ct}"] = sorted(set(x["n_orders"] for x in cl))
        d[f"new_cols_{ct}"] = sorted(set(x["n_new_cols"] for x in cl))
    out[name] = d
    print(name, json.dumps(d, default=str))
json.dump(out, open("results/E-005-audit/t0_codes.json", "w"), indent=1, default=str)
