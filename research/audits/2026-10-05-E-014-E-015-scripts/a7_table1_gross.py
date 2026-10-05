"""A7: Prop. 3 key step (Table I) on the evaluator's memory circuits for Strikis Fig. 12 (gross), R = 1, 2, 3, both bases:
every single fault's end-of-circuit data image is 0 or exactly one column of the auditor's extended code (A1 (i))."""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent)); sys.path.insert(0, "tests")
import b_ibm, extx, a1_gross
from gf2 import logical_basis
from evaluators.candidate import build_circuits, parse_schedule
from evaluators.noise import add_noise
from evaluators.tasks import build_code, get_task
from schedule_helpers import from_baseline
from baselines.bb_code import gross_code
from baselines.strikis import strikis_fig12
css, _ = build_code(get_task("gross-dcirc"), None)
HX, HZ = a1_gross.bb_mats()
assert (np.asarray(css.HX) % 2 == HX).all() and (np.asarray(css.HZ) % 2 == HZ).all()
sched, _ = strikis_fig12(gross_code())
spec = parse_schedule(from_baseline(sched)).canonical()
xo, zo, ncyc = b_ibm.orders_from_circuit(build_circuits(spec, css, 2)["Z"], 144, HX, HZ)
assert xo == a1_gross.orders_from_layers(sched, HX, "X") and zo == a1_gross.orders_from_layers(sched, HZ, "Z")
LX = logical_basis(HZ, HX); LZ = logical_basis(HX, HZ)
out = []
for basis in "ZX":
    H, L, oo, part = (HZ, LZ, xo, "X") if basis == "Z" else (HX, LX, zo, "Z")
    e = extx.build(H, L, oo, 144)
    keys = {e["He"][:, j].tobytes() + e["Le"][:, j].tobytes() for j in range(e["He"].shape[1])}
    for R in (1, 2, 3):
        circ = add_noise(build_circuits(spec, css, R)[basis], "sd6", 1e-3).flattened()
        ops, faults = b_ibm.enumerate_faults(circ)
        D, O, Xf, Zf = b_ibm.simulate(ops, faults, circ.num_qubits)
        img = (Xf if part == "X" else Zf)[:144].astype(np.int64)
        hk = (H.astype(np.int64) @ img) % 2; lk = (L.astype(np.int64) @ img) % 2
        exc = 0; used = set()
        for f in range(len(faults)):
            if not hk[:, f].any() and not lk[:, f].any():
                continue
            k = hk[:, f].astype(np.uint8).tobytes() + lk[:, f].astype(np.uint8).tobytes()
            if k in keys: used.add(k)
            else: exc += 1
        rec = dict(basis=basis, R=R, faults=len(faults), exceptions=exc, cols_realised=len(used), n_cols=len(keys),
                   orders_from_circuit_equal_layers=True)
        print(rec, flush=True); out.append(rec)
Path("results/E-014-E-015-audit/a7_table1_gross.json").write_text(json.dumps(out, indent=1))
