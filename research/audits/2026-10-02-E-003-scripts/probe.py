"""Probe: DEM statistics, joint-circuit feasibility, decoder timing (single process)."""
import json
import time

import numpy as np

from common import code_and_scheds, memory, dem_matrices, OUT

code, S = code_and_scheds()
res = {}
for name, sched in S.items():
    for basis in "ZX":
        c = memory(code, sched, name, 12, basis, 0.005)
        H, L, pri = dem_matrices(c)
        colw = np.asarray(H.sum(axis=0)).ravel()
        # mean detection events per shot
        dets = c.compile_detector_sampler(seed=1).sample(2000)
        ticks = sum(1 for i in c.flattened() if i.name == "TICK")
        r = {"detectors": H.shape[0], "columns": H.shape[1], "nnz": int(H.nnz),
             "mean_col_weight": float(colw.mean()), "max_col_weight": int(colw.max()),
             "cols_weight_gt2": int((colw > 2).sum()), "sum_priors": float(pri.sum()),
             "mean_events_per_shot": float(dets.sum(1).mean()), "ticks": ticks,
             "logical_cols": int((np.asarray(L.sum(axis=0)).ravel() > 0).sum()),
             "sum_priors_logical_cols": float(pri[np.asarray(L.sum(axis=0)).ravel() > 0].sum())}
        res[f"{name}_{basis}"] = r
        print(name, basis, r, flush=True)

# joint circuit feasibility
from evaluators.codes import CSSCode
from evaluators.l2 import build_joint_circuit
css = CSSCode.from_checks(code.HX, code.HZ)
for name, sched in S.items():
    circ = {b: memory(code, sched, "strikis", 12, b, 0.0) for b in "ZX"}  # pipelined generator for both
    for bnd in ("noisy", "paper"):
        try:
            J = build_joint_circuit(css, circ, sched.data, noise_model="sd6", p=0.005, boundary=bnd)
            res[f"joint_{name}_{bnd}"] = {"ok": True, "info": {k: v for k, v in J.info.items()
                                                               if isinstance(v, (int, float, str))}}
        except Exception as e:  # noqa: BLE001
            res[f"joint_{name}_{bnd}"] = {"ok": False, "err": str(e)[:400]}
        print(name, bnd, res[f"joint_{name}_{bnd}"], flush=True)
(OUT / "probe.json").write_text(json.dumps(res, indent=1))
