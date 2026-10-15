"""Re-check the solutions reported by ccsearch on a freshly built detector error model.

    python code/dcirc/verify.py CIRCUIT BASIS R RUNFILE [WEIGHT]

Rebuilds the DEM of the circuit (same columns as export.py) and checks for every SOL line of RUNFILE: the columns are
distinct, the XOR of their detector sets is empty and the XOR of their observable sets is nonzero (and, if given,
that the weight equals WEIGHT).  Then injects the faults into the circuit: for every reported column, stim's
explain_detector_error_model_errors gives a concrete circuit fault (Pauli on qubits at a given instruction); all
faults are inserted with probability 1 into the noiseless circuit and the detector sampler must fire no detector
and flip the same observables.
"""
import sys
from pathlib import Path

import stim

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from export import dem_columns, load                  # noqa: E402
from gross12.noise import add_sd6                     # noqa: E402
from gross12.schedule import build_circuits           # noqa: E402

name, basis, R, run = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
want = int(sys.argv[5]) if len(sys.argv) > 5 else None
code, spec, _ = load(name)
clean = build_circuits(spec.canonical(), code, R)[basis]
noisy = add_sd6(clean)
dem, cols = dem_columns(noisy)
cols = [c for c in cols if c[0] or c[1]]
bad = 0
n = 0
for line in open(run):
    if not line.startswith("SOL"):
        continue
    n += 1
    ids = [int(x) for x in line.split(":")[1].split()]
    d, o = set(), set()
    for j in ids:
        d ^= set(cols[j][0]); o ^= set(cols[j][1])
    ok = len(set(ids)) == len(ids) and not d and bool(o) and (want is None or len(ids) == want)
    # circuit-level injection of one representative fault per column
    filt = []
    for j in ids:
        f = stim.DetectorErrorModel()
        f.append("error", 1, [stim.target_relative_detector_id(x) for x in cols[j][0]] +
                 [stim.target_logical_observable_id(x) for x in cols[j][1]])
        filt.append(f)
    expl = noisy.explain_detector_error_model_errors(dem_filter=sum(filt[1:], filt[0]), reduce_to_one_representative_error=True)
    by_key = {}
    for e in expl:
        k = (tuple(sorted(x.dem_target.val for x in e.dem_error_terms if x.dem_target.is_relative_detector_id())),
             tuple(sorted(x.dem_target.val for x in e.dem_error_terms if x.dem_target.is_logical_observable_id())))
        by_key[k] = e.circuit_error_locations[0]
    inj_ok = all(cols[j] in by_key for j in ids)
    if inj_ok:
        # insert each representative fault (Pauli product on its targets) right after the instruction that causes it
        ins = {}
        for j in ids:
            loc = by_key[cols[j]]
            ins.setdefault(loc.stack_frames[0].instruction_offset, []).append(loc.flipped_pauli_product)
        flat = noisy.flattened()
        out = stim.Circuit()
        k = 0
        for i, op in enumerate(flat):
            if op.name in ("DEPOLARIZE1", "DEPOLARIZE2", "X_ERROR", "Z_ERROR"):
                pass
            else:
                out.append(op)
            for prod in ins.get(i, []):
                for p in prod:
                    q = p.gate_target.value
                    if p.gate_target.is_x_target:
                        out.append("X_ERROR", [q], 1)
                    elif p.gate_target.is_z_target:
                        out.append("Z_ERROR", [q], 1)
                    else:
                        out.append("Y_ERROR", [q], 1)
        s = out.compile_detector_sampler(seed=5).sample(2, append_observables=True)
        nd = out.num_detectors
        fired = int(s[0, :nd].sum())
        flipped = sorted(int(x) for x in s[0, nd:].nonzero()[0])
        inj_ok = fired == 0 and flipped == sorted(o)
    else:
        fired, flipped = None, None
    ok = ok and inj_ok
    bad += not ok
    print(("PASS" if ok else "FAIL") + f"  {name} {basis} R={R}: solution of weight {len(ids)}: distinct "
          f"{len(set(ids)) == len(ids)}, detectors left {len(d)}, observables {sorted(o)}; circuit injection of one "
          f"fault per mechanism: {fired} detectors fire, observables {flipped}")
if n == 0:
    print(f"FAIL  {name} {basis} R={R}: no SOL line in {run}")
    bad = 1
sys.exit(1 if bad else 0)
