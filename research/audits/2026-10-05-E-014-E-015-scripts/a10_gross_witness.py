"""A5c: own injection-verified weight-11 witness for the evaluated Fig. 12 circuits (R = 1, 2, 3, both bases), from the
lead's W=11 extended logicals mapped into the auditor's code (a6_w11.py) and the auditor's fault simulator."""
import itertools, json, sys
from collections import defaultdict
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent)); sys.path.insert(0, "tests")
import b_ibm, extx, a1_gross
from b6_theorems import stim_inject
from gf2 import logical_basis
from evaluators.candidate import build_circuits, parse_schedule
from evaluators.noise import add_noise
from evaluators.tasks import build_code, get_task
from schedule_helpers import from_baseline
from baselines.bb_code import gross_code
from baselines.strikis import strikis_fig12
LEAD = Path("results/E-014-gross-dcirc11-proof")
css, _ = build_code(get_task("gross-dcirc"), None)
HX, HZ = a1_gross.bb_mats()
sched, _ = strikis_fig12(gross_code())
spec = parse_schedule(from_baseline(sched)).canonical()
xo = a1_gross.orders_from_layers(sched, HX, "X"); zo = a1_gross.orders_from_layers(sched, HZ, "Z")
LX = logical_basis(HZ, HX); LZ = logical_basis(HX, HZ)
out = []
for basis, kind in (("Z", "X"), ("X", "Z")):
    H, L, oo, part = (HZ, LZ, xo, "X") if basis == "Z" else (HX, LX, zo, "Z")
    e = extx.build(H, L, oo, 144)
    He2, Le2, _, _ = extx.read128(LEAD / f"inst_{kind}.txt")
    ok, info = extx.compare_columns(e["He"], e["Le"], True, He2, Le2[:12])
    inv = {b: a for a, b in enumerate(info["map"])}
    sols = [[inv[int(c)] for c in l.split("cols:")[1].split()] for l in open(LEAD / f"positive_W11_{kind}.txt") if l.startswith("FOUND")]
    colkey = {e["He"][:, j].tobytes() + e["Le"][:, j].tobytes(): j for j in range(e["He"].shape[1])}
    for R in (1, 2, 3):
        circ = add_noise(build_circuits(spec, css, R)[basis], "sd6", 1e-3).flattened()
        ops, faults = b_ibm.enumerate_faults(circ)
        D, O, Xf, Zf = b_ibm.simulate(ops, faults, circ.num_qubits)
        img = (Xf if part == "X" else Zf)[:144].astype(np.int64)
        hk = (H.astype(np.int64) @ img) % 2; lk = (L.astype(np.int64) @ img) % 2
        detv = [int.from_bytes(np.packbits(D[:, f]).tobytes(), "big") for f in range(len(faults))]
        obsv = [int.from_bytes(np.packbits(O[:, f]).tobytes(), "big") for f in range(len(faults))]
        groups = defaultdict(dict)
        for f in range(len(faults)):
            if hk[:, f].any() or lk[:, f].any():
                j = colkey[hk[:, f].astype(np.uint8).tobytes() + lk[:, f].astype(np.uint8).tobytes()]
                groups[j].setdefault((detv[f], obsv[f]), f)
        hit = None
        for S in sols:
            G = [list(groups[j].values()) for j in S]
            h = len(G) // 2
            left = defaultdict(list)
            for c in itertools.product(*G[:h]):
                dm = om = 0
                for f in c: dm ^= detv[f]; om ^= obsv[f]
                left[dm].append((om, c))
            for c in itertools.product(*G[h:]):
                dm = om = 0
                for f in c: dm ^= detv[f]; om ^= obsv[f]
                for om2, c2 in left.get(dm, ()):
                    if om ^ om2: hit = c2 + c; break
                if hit: break
            if hit: break
        rec = dict(basis=basis, R=R, n_sols=len(sols), witness=hit is not None)
        if hit:
            rec["n_faults"] = len(hit)
            rec["distinct_dem_terms"] = len({(detv[f], obsv[f]) for f in hit})
            rec["stim_injection"] = stim_inject(circ, ops, [faults[f] for f in hit])
        print(rec, flush=True); out.append(rec)
Path("results/E-014-E-015-audit/a10_gross_witness.json").write_text(json.dumps(out, indent=1, default=str))
