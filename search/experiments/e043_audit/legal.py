"""Item (1): legality and T(P) membership of a translation-invariant BB schedule (bb90 or gross).

 a) evaluator validate_schedule + check_l0 (both bases, R = 1, 2, 3)
 b) noiseless circuit: 100 shots, all detectors/observables 0; SD6 DEM buildable
 c) per ancilla exactly R instances, each prep -> 6 CX on exactly its H row -> meas (parsed from stim)
 d) single-qubit injection on every data qubit at every layer boundary of the middle round (R = 3): fired detector
    rows == checks containing q, each once; observable flip == L column of q
 e) step-pairing model == SD6 DEM signature sets (B_audit.dem_check), R = 1, 2
 f) window conditions (Wb)(Wt) and finite/bulk index mismatches for R = 1..Rmax (B_audit.window_test.conds)
 g) delta / pairing (determinism in the bulk), zero-image hooks, strict translation invariance
 h) T(P) membership computed here from the spec alone (own code): one time vector per check type up to translation
    (strict invariance), CNOT times distinct, span <= P - 3, prep before first and meas after last CNOT within one
    period, the 6 CNOTs on every data qubit distinct mod P, every qubit at most one op per layer mod P.

  uv run python -m search.experiments.e043_audit.legal ibm90 [Rmax]
"""
from __future__ import annotations

import sys
from collections import defaultdict

import numpy as np
import stim

from search.experiments.e043_audit.common import code_of, info, jdump, load


def inject_test(spec, code, basis, R=3):
    from evaluators import candidate as cand
    circ = cand.memory_circuit(spec, code, basis, R)
    n = code.n
    H = (np.asarray(code.HZ if basis == "Z" else code.HX) % 2).astype(np.uint8)
    L = (np.asarray(code.LZ if basis == "Z" else code.LX) % 2).astype(np.uint8)
    coords = circ.get_detector_coordinates()
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
    bad = tested = 0
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
            bad += not ok
    return {"tested": tested, "bad": bad, "boundaries": [lo, hi - 1], "layers": nl}


def measured_once(circ, code, R):
    from search.theory.B_audit.dem_check import parse
    n = code.n
    mx = code.HX.shape[0]
    _, inst, _ = parse(circ, n)
    HX = (np.asarray(code.HX) % 2).astype(np.uint8)
    HZ = (np.asarray(code.HZ) % 2).astype(np.uint8)
    bad = 0
    for a, lst in inst.items():
        row = HX[a - n] if a < n + mx else HZ[a - n - mx]
        sup = sorted(np.flatnonzero(row).tolist())
        if len(lst) != R:
            bad += 1
            continue
        for I in lst:
            if I["meas"] is None or sorted(q for _, q in I["cx"]) != sup:
                bad += 1
    return {"ancillas": len(inst), "expected": HX.shape[0] + HZ.shape[0], "bad": bad}


def tp_membership(sd, n):
    """own T(P) check from the raw spec."""
    P = int(sd["period"])
    out = {}
    data_times = defaultdict(list)
    for side in ("x_checks", "z_checks"):
        prof = set()
        bad = 0
        for ch in sd[side]:
            p = int(ch["prep"]) % P
            ts = sorted(p + ((int(t) - p) % P) for _, t in ch["cnots"])
            m = p + ((int(ch["meas"]) - p) % P)
            ok = len(set(ts)) == 6 and ts[0] > p and m > ts[-1] and m < p + P and ts[-1] - ts[0] <= P - 3
            bad += not ok
            prof.add((ts[-1] - ts[0], ts[0] - p, m - ts[-1]))
            for q, t in ch["cnots"]:
                data_times[int(q)].append(int(t) % P)
        out[side] = {"checks": len(sd[side]), "bad": bad, "(span, first-prep, meas-last)": sorted(prof)}
    out["data_qubits"] = len(data_times)
    out["data_qubits_with_6_distinct_mod_P"] = sum(1 for q, l in data_times.items() if len(l) == 6 and len(set(l)) == 6)
    out["n"] = n
    return out


def main():
    name = sys.argv[1]
    Rmax = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    cname, sp, _ = info(name)
    from evaluators import candidate as cand
    from evaluators.l0 import L0Constraints, check_l0
    from evaluators.noise import add_noise
    from search.theory.B_audit.common import Bulk
    from search.theory.B_audit.delta import analyse
    from search.theory.B_audit.dem_check import dem, model
    from search.theory.B_audit.enum_driver import translations
    from search.theory.B_audit.lift import bulk_columns
    from search.theory.B_audit.window_test import conds
    code = code_of(cname)
    sd = load(name)
    spec = cand.parse_schedule(sd)
    rec = {"name": name, "spec": sp, "period": spec.period, "validate_schedule": cand.validate_schedule(spec, code),
           "T(P)": tp_membership(sd, code.n)}
    for R in (1, 2, 3):
        rep = check_l0(cand.build_circuits(spec, code, R), code, "both", L0Constraints(rounds=R))
        rec[f"check_l0_R{R}"] = {"passed": rep.passed,
                                 "nonpass": [(c.name, c.status) for c in rep.checks if c.status != "pass"]}
        for basis in ("Z", "X"):
            circ = cand.memory_circuit(spec, code, basis, R)
            s = circ.compile_detector_sampler().sample(100, append_observables=True)
            try:
                add_noise(circ, "sd6", 1e-3).detector_error_model(approximate_disjoint_errors=True)
                dem_ok = True
            except Exception as e:  # noqa
                dem_ok = repr(e)
            rec[f"det_R{R}{basis}"] = {"all_zero": bool(not s.any()), "dem_built": dem_ok,
                                       "measured": measured_once(circ, code, R)}
    for basis in ("Z", "X"):
        rec[f"inject_{basis}"] = inject_test(spec, code, basis)
    for R in (1, 2):
        for basis in ("Z", "X"):
            circ = cand.memory_circuit(spec, code, basis, R)
            M, _ = model(code, circ, basis)
            D = dem(circ)
            rec[f"model_vs_dem_R{R}{basis}"] = {"model": len(M), "dem": len(D), "equal": M == D}
    w = conds(code, sd, Rmax=Rmax)
    rec["window_all_ok"] = all(v["Wb"] and v["Wt"] and v["index_mismatches"] == 0 for v in w.values())
    rec["window_Rmax"] = Rmax
    rec["window_failures"] = {k: v for k, v in w.items() if not (v["Wb"] and v["Wt"] and v["index_mismatches"] == 0)}
    for basis in ("Z", "X"):
        B = Bulk(sd, code, basis)
        a = analyse(B)
        cols, zero = bulk_columns(B)
        perms = translations(cname, B, sd)
        strict = all(B.wr[cp[c]][1][qp[q]] == t for qp, cp in perms for c in range(len(B.wr))
                     for q, t in B.wr[c][1].items()) and \
            all(B.rd[cp[c]][1][qp[q]] == t for qp, cp in perms for c in range(len(B.rd))
                for q, t in B.rd[c][1].items())
        rec[f"bulk_{basis}"] = {"delta": a, "ncols": len(cols), "zero_key_hooks": len(zero),
                                "translations": len(perms), "strict_invariance": strict}
    jdump(rec, "legal.jsonl")


if __name__ == "__main__":
    main()
