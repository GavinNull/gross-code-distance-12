"""Project the single-round DEM onto memory-type detectors + observables (CSS relaxation) and merge columns."""
from __future__ import annotations
import numpy as np
import stim
from search.experiments.e017.oneround import one_round_circuit


def projected_columns(c: stim.Circuit, basis: str):
    want = 1 if basis == "Z" else 0      # Z memory -> Z-type detectors (coord[2] == 1)
    coords = c.get_detector_coordinates()
    keep = sorted(d for d, co in coords.items() if int(co[2]) == want)
    pos = {d: i for i, d in enumerate(keep)}
    dem = c.detector_error_model(decompose_errors=False)
    cols = set()
    for ins in dem.flattened():
        if ins.type != "error":
            continue
        ds, ob = [], []
        for t in ins.targets_copy():
            if t.is_relative_detector_id() and t.val in pos:
                ds.append(pos[t.val])
            elif t.is_logical_observable_id():
                ob.append(t.val)
        if ds or ob:
            cols.add((tuple(sorted(ds)), tuple(sorted(ob))))
    return keep, sorted(cols)


if __name__ == "__main__":
    for basis in "XZ":
        c, M = one_round_circuit(basis=basis)
        keep, cols = projected_columns(c, basis)
        degs = np.zeros(len(keep), int)
        for ds, ob in cols:
            for d in ds:
                degs[d] += 1
        w = [len(ds) for ds, ob in cols]
        print(basis, "rows", len(keep), "cols", len(cols), "col weight hist", np.bincount(w).tolist(),
              "row degree min/mean/max", degs.min(), degs.mean().round(1), degs.max(),
              "obs-only cols", sum(1 for ds, ob in cols if not ds))
