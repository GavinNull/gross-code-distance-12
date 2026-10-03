import sys, time
sys.path.insert(0, "research/audits/2026-10-03-E-005-scripts")
from audext import *
for name in ["bb90"]:
    c = Code(name)
    cl = single_check_classes(c, "X", 0)
    H, L = c.det("X")
    for ci in [0, 45]:
        M, rH = ext_matrix(H, L, cl[ci]["residuals"]); M, _ = dedupe_columns(M)
        r = cpsat_min(M, rH, time_limit=300, workers=1); print(name, ci, M.shape, "cpsat", r["status"], r["value"], r["lower"], r["seconds"], flush=True)
        t=time.time(); r = highs_min(M, rH, time_limit=300); print(name, ci, "highs", r["status"], r["value"], round(time.time()-t,1), flush=True)
