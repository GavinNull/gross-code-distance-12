"""A2: legality / determinism / symmetry of c16 (and u16), own encoder vs evaluator DEM."""
import sys, json, collections
sys.path.insert(0, "research/audits/2026-10-15-E-028-scripts")
import numpy as np, stim
from alib import *

HX, HZ, LX, LZ = code_with_logicals()
for name in ("c16", "u16"):
    spec = load_spec(f"search/experiments/e028/{name}_spec.json")
    D = spec["period"]
    print("==", name, "period", D, "keys", sorted(spec))
    # legality: per data qubit per layer at most one CNOT; per ancilla distinct times; prep<cnot<meas
    use = collections.Counter()
    for typ, chk in (("X", spec["x_checks"]), ("Z", spec["z_checks"])):
        for c in chk:
            for a, t in c["cnots"]:
                use[(a, t)] += 1
    print(" data-layer clashes:", sum(1 for v in use.values() if v > 1))
    # pairwise commutation (determinism within a round, all checks share the same window)
    preps = {c["prep"] for c in spec["x_checks"] + spec["z_checks"]}
    meas = {c["meas"] for c in spec["x_checks"] + spec["z_checks"]}
    print(" preps", preps, "meas", meas)
    bad = 0; pairs = 0
    for i, cx in enumerate(spec["x_checks"]):
        tx = {a: t for a, t in cx["cnots"]}
        for j, cz in enumerate(spec["z_checks"]):
            tz = {a: t for a, t in cz["cnots"]}
            sh = set(tx) & set(tz)
            if sh:
                pairs += 1
                if sum(1 for a in sh if tx[a] < tz[a]) % 2:
                    bad += 1
    print(" overlapping XZ pairs", pairs, "odd-order pairs (non-commuting measurement)", bad)
    # interleaving: X CNOT time range vs Z CNOT time range
    xt = sorted({t for c in spec["x_checks"] for _, t in c["cnots"]}); zt = sorted({t for c in spec["z_checks"] for _, t in c["cnots"]})
    print(" X cnot layers", xt, " Z cnot layers", zt)
    # per-check label order (time order of the 6 support columns), translation symmetry
    def lab(typ, i, col):
        a, b = divmod(i, M_)
        if typ == "X":
            cand = {((a+9)%L_)*M_+b: "A1", a*M_+(b+1)%M_: "A2", a*M_+(b+2)%M_: "A3",
                    N2+a*M_+b: "B1", N2+((a+2)%L_)*M_+b: "B2", N2+((a+7)%L_)*M_+b: "B3"}
        else:
            cand = {N2+((a-9)%L_)*M_+b: "A1", N2+a*M_+(b-1)%M_: "A2", N2+a*M_+(b-2)%M_: "A3",
                    a*M_+b: "B1", ((a-2)%L_)*M_+b: "B2", ((a-7)%L_)*M_+b: "B3"}
        return cand[col]
    for typ, chk in (("X", spec["x_checks"]), ("Z", spec["z_checks"])):
        sig = collections.Counter(tuple((lab(typ, i, a), t) for a, t in sorted(c["cnots"], key=lambda x: x[1])) for i, c in enumerate(chk))
        print(f" {typ} distinct (label,time) signatures:", len(sig), list(sig)[:2])
    # data-qubit X/Z switches per period
    for q in (0, 45):
        seq = sorted([(t, "X") for c in spec["x_checks"] for a, t in c["cnots"] if a == q] + [(t, "Z") for c in spec["z_checks"] for a, t in c["cnots"] if a == q])
        print(f" data {q} cyclic sequence:", "".join(s for _, s in seq))
    for basis in "ZX":
        for R in (1, 2, 3):
            mine = memory_circuit(spec, basis, R)
            nl = memory_circuit(spec, basis, R, noise=False)
            # determinism: noiseless sampling + DEM construction (stim raises on non-deterministic detectors/obs)
            s = nl.compile_detector_sampler().sample(64, append_observables=True)
            dem_ok = True
            try:
                nl.detector_error_model()
            except Exception as e:
                dem_ok = repr(e)[:200]
            cols, nd, no = dem_matrix(mine)
            # evaluator circuit
            from evaluators.candidate import build_circuits, parse_schedule
            from evaluators.noise import add_noise
            from evaluators.tasks import build_code, get_task
            c, _ = build_code(get_task("bb90-dcirc"), None)
            ev = add_noise(build_circuits(parse_schedule(spec), c, R)[basis], "sd6", 1e-3)
            # compare detector parts as sets; observables compared up to basis change: use evaluator obs mapped via logical span
            ecols, end_, eno = dem_matrix(ev)
            print(f" {basis} R={R}: noiseless det/obs all zero={not s.any()} dem_ok={dem_ok} mine: {len(cols)} errs {nd} dets; evaluator: {len(ecols)} errs {end_} dets;"
                  f" detector-sets equal={collections.Counter(d for d,_ in cols)==collections.Counter(d for d,_ in ecols)}")
