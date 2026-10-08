"""E-017 positive control: map the weight-12 end-cycle witness (idle faults on left qubits in the reset layer of
the noisy round) to columns of the projected single-round DFS instance."""
from __future__ import annotations
import json, sys
import stim
from search.experiments.e017.dfs_inst import build
from search.experiments.e017.witness import DFS_SUPPORTS
from search.experiments.e017.oneround import LAYERS_PER_ROUND

basis = sys.argv[1] if len(sys.argv) > 1 else "Z"
inst = build("x", False, basis, 1)
c = inst["circuit"]
P = "X" if basis == "Z" else "Z"
# noisy round = round index 1 (0-based) of 3, first_j=1 -> j(round2) = 0, previous end-cycle code j_prev = 1
supp = DFS_SUPPORTS[(1, P)]
keep, rows = inst["keep"], inst["rows"]
pos = {keep[r]: i for i, r in enumerate(rows)}
colkey = {}
He, Le = inst["He"], inst["Le"]
for j in range(He.shape[1]):
    colkey[(tuple(int(i) for i in He[:, j].nonzero()[0]), tuple(int(o) for o in Le[:, j].nonzero()[0]))] = j
cols = []
for q in supp:
    # single error at end of layer 8 (reset layer of round 2) on left qubit q, in a noiseless copy
    clean = stim.Circuit()
    tick = 0
    for ins in c.flattened():
        if ins.name in ("DEPOLARIZE1", "DEPOLARIZE2", "X_ERROR", "Z_ERROR"):
            continue
        if ins.name == "TICK":
            if tick == LAYERS_PER_ROUND:
                clean.append(f"{P}_ERROR", [q], 0.01)
            tick += 1
        clean.append(ins)
    dem = clean.detector_error_model()
    for e in dem.flattened():
        if e.type == "error":
            ds = tuple(sorted(pos[t.val] for t in e.targets_copy() if t.is_relative_detector_id() and t.val in pos))
            ob = tuple(sorted(t.val for t in e.targets_copy() if t.is_logical_observable_id()))
            cols.append(colkey[(ds, ob)])
orbs = [inst["corb"][j] for j in cols]
print(json.dumps({"basis": basis, "cols": cols, "orbits": orbs, "min_orbit": min(orbs)}))
