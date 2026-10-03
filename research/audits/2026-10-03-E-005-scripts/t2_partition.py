import sys, json
sys.path.insert(0, "research/audits/2026-10-03-E-005-scripts")
from audext import *
from baselines.bb_code import BBCode
from baselines.schedule import ibm_depth8
from baselines.strikis import strikis_fig12
out = {}
g = BBCode(12, 6, ["x^3","y","y^2"], ["y^3","x","x^2"])
s12, meta = strikis_fig12(g)
s12.validate(g.HX, g.HZ)
for nm, sc in [("gross_fig12", s12), ("gross_ibm", ibm_depth8(g)), ("bb108_ibm", ibm_depth8(BBCode(9,6,["x^3","y","y^2"],["y^3","x","x^2"])))]:
    for R in (4, 8):
        out[f"{nm}_R{R}"] = pairwise_and_partition(sc, R)
        print(nm, R, out[f"{nm}_R{R}"], flush=True)
json.dump(out, open("results/E-005-audit/t2_partition.json", "w"), indent=1)
