"""Auditor E-026: DEM column prior / degree statistics (R = 12, p = 2e-3), own merge."""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_sample import build, OUT
res = {}
for c in ("p18", "fig12", "ibm"):
    for b in "ZX":
        dem, H, L, q, _ = build(c, b, 12, 2e-3)
        deg = np.diff(H.tocsc().indptr); rdeg = np.diff(H.tocsr().indptr)
        r = q / 2e-3
        res[f"{c}_{b}"] = dict(ncol=int(len(q)), lam=float(q.sum()), q_over_p_pct=[float(x) for x in np.percentile(r, [50, 90, 99, 100])],
                               n_q_over_p_gt3=int((r > 3).sum()), col_deg_mean=float(deg.mean()), col_deg_max=int(deg.max()),
                               det_deg_mean=float(rdeg.mean()), det_deg_max=int(rdeg.max()),
                               lam_cols_deg_gt4=float(q[deg > 4].sum()))
        print(c, b, res[f"{c}_{b}"], flush=True)
(OUT / "dem_stats.json").write_text(json.dumps(res, indent=1))
