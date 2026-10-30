"""Item (1): legality of a gross schedule.

 a) evaluator validate_schedule + check_l0 (both bases, R = 1, 2, 3; determinism, logical injection, coverage)
 b) independent determinism: stim detector/observable samples of the noiseless circuit are all 0 (100 shots), and
    the DEM can be built (stim raises on non-deterministic detectors)
 c) every check actually measured: per round each ancilla has exactly one prep, 6 CX on exactly its H row, one meas
    (parsed from the stim circuit, not from the spec)
 d) single-qubit injection: X (Z basis) / Z (X basis) on each data qubit q at a mid-circuit layer boundary, R = 3;
    the set of checks whose detectors fire must equal {checks whose support contains q} (each exactly once, at one
    round), observable flip = L column of q.  Done at every layer boundary of the middle round.
 e) step-pairing model == SD6 DEM signature sets (B_audit.dem_check), R = 1, 2
 f) window conditions (Wb)(Wt) and finite/bulk index mismatches, R = 1..3 (B_audit.window_test.conds)
 g) delta cochain / pairing violations (B_audit.delta), zero-image hooks, translation invariance

  uv run python -m search.experiments.e040_audit_circ.legal g10
"""
from __future__ import annotations

import sys
from collections import defaultdict

import numpy as np
import stim

from search.experiments.e040_audit_circ.common import gross, jdump, load, spec_path


def inject_test(spec, code, basis, R=3):
    from evaluators import candidate as cand
    circ = cand.memory_circuit(spec, code, basis, R)
    n = code.n
    H = (np.asarray(code.HZ if basis == "Z" else code.HX) % 2).astype(np.uint8)
    L = (np.asarray(code.LZ if basis == "Z" else code.LX) % 2).astype(np.uint8)
    coords = circ.get_detector_coordinates()
    # split into layers at TICKs
    layers, cur = [], stim.Circuit()
    for op in circ:
        if op.name == "TICK":
            layers.append(cur)
            cur = stim.Circuit()
        else:
            cur.append(op)
    tail = cur
    nl = len(layers)
    per = spec.period
    lo, hi = nl // 2 - per // 2, nl // 2 + per // 2 + 1
    gate = "X_ERROR" if basis == "Z" else "Z_ERROR"
    bad = 0
    tested = 0
    for b in range(lo, hi):
        for q in range(n):
            c = stim.Circuit()
            for i, lay in enumerate(layers):
                c += lay
                if i == b:
                    c.append(gate, [q], 1.0)
                c.append("TICK")
            c += tail
            s = c.compile_detector_sampler().sample(1, append_observables=True)[0]
            dets = np.flatnonzero(s[:-L.shape[0]])
            obs = s[-L.shape[0]:].astype(np.uint8)
            rows = defaultdict(int)
            for d in dets:
                rows[int(coords[int(d)][0])] += 1
            want = set(np.flatnonzero(H[:, q]).tolist())
            ok = set(rows) == want and all(v == 1 for v in rows.values()) and np.array_equal(obs, L[:, q])
            tested += 1
            if not ok:
                bad += 1
    return {"tested": tested, "bad": bad, "boundaries": [lo, hi - 1], "layers": nl}


def measured_once(circ, code, basis, R):
    """per ancilla: R instances, each prep -> 6 CX on one H row (X checks HX, Z checks HZ) -> meas."""
    from search.theory.B_audit.dem_check import parse
    n = code.n
    mx = code.HX.shape[0]
    _, inst, kind = parse(circ, n)
    HX = (np.asarray(code.HX) % 2).astype(np.uint8)
    HZ = (np.asarray(code.HZ) % 2).astype(np.uint8)
    bad = 0
    for a, lst in inst.items():
        row = (HX[a - n] if a < n + mx else HZ[a - n - mx])
        sup = sorted(np.flatnonzero(row).tolist())
        if len(lst) != R:
            bad += 1
            continue
        for I in lst:
            if I["meas"] is None or sorted(q for _, q in I["cx"]) != sup:
                bad += 1
    return {"ancillas": len(inst), "expected": HX.shape[0] + HZ.shape[0], "bad": bad}


def main():
    name = sys.argv[1]
    sp = spec_path(name)
    from evaluators import candidate as cand
    from evaluators.l0 import L0Constraints, check_l0
    from search.theory.B_audit.common import Bulk
    from search.theory.B_audit.delta import analyse
    from search.theory.B_audit.dem_check import dem, model
    from search.theory.B_audit.enum_driver import translations
    from search.theory.B_audit.lift import bulk_columns
    from search.theory.B_audit.window_test import conds
    code = gross()
    sd = load(name)
    spec = cand.parse_schedule(sd)
    rec = {"spec": sp, "period": spec.period, "validate_schedule": cand.validate_schedule(spec, code)}
    for R in (1, 2, 3):
        rep = check_l0(cand.build_circuits(spec, code, R), code, "both", L0Constraints(rounds=R))
        rec[f"check_l0_R{R}"] = {"passed": rep.passed,
                                 "nonpass": [(c.name, c.status) for c in rep.checks if c.status not in ("pass",)]}
        for basis in ("Z", "X"):
            circ = cand.memory_circuit(spec, code, basis, R)
            s = circ.compile_detector_sampler().sample(100, append_observables=True)
            noisy_ok = True
            try:
                from evaluators.noise import add_noise
                add_noise(circ, "sd6", 1e-3).detector_error_model(approximate_disjoint_errors=True)
            except Exception as e:  # noqa
                noisy_ok = repr(e)
            rec[f"det_R{R}{basis}"] = {"all_zero": bool(not s.any()), "dem_built": noisy_ok,
                                       "measured": measured_once(circ, code, basis, R)}
    for basis in ("Z", "X"):
        rec[f"inject_{basis}"] = inject_test(spec, code, basis)
    for R in (1, 2):
        for basis in ("Z", "X"):
            circ = cand.memory_circuit(spec, code, basis, R)
            M, _ = model(code, circ, basis)
            D = dem(circ)
            rec[f"model_vs_dem_R{R}{basis}"] = {"model": len(M), "dem": len(D), "equal": M == D}
    rec["window"] = conds(code, sd, Rmax=3)
    for basis in ("Z", "X"):
        B = Bulk(sd, code, basis)
        a = analyse(B)
        cols, zero = bulk_columns(B)
        perms = translations("gross", B, sd)
        # strict translation invariance: same absolute times for translated checks
        strict = all(B.wr[cp[c]][1][qp[q]] == t for qp, cp in perms for c in range(len(B.wr))
                     for q, t in B.wr[c][1].items()) and \
            all(B.rd[cp[c]][1][qp[q]] == t for qp, cp in perms for c in range(len(B.rd))
                for q, t in B.rd[c][1].items())
        rec[f"bulk_{basis}"] = {"delta": a, "ncols": len(cols), "zero_key_hooks": len(zero),
                                "translations": len(perms), "strict_invariance": strict,
                                "writer_order_check0": B.wr[0][0]}
    jdump(rec, "legal.jsonl")


if __name__ == "__main__":
    main()
