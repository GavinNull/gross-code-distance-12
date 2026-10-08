"""E-018: independent confirmation of lifted weight-11 circuit logicals by injection into stim.

For a hit (11 augmented DEM terms, one per column of S), ask stim for one circuit location of each term
(explain_detector_error_model_errors with a dem_filter), rebuild the noisy flattened circuit with every noise
channel removed and the 11 faults inserted as probability-1 Pauli errors at their locations (a flipped measurement
is inserted as the corresponding Pauli just before the measurement), sample once (deterministic) and require
0 detectors fired and >= 1 observable flipped.  Also checks the 11 locations are 11 distinct DEM terms of the
original (un-augmented) DEM.

    PYTHONPATH=.:tests uv run python -m search.experiments.e018.witness --lift results/E-018-gross-interleaved-12/lift_fig12.json --n 20
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import stim

from search.experiments.e018.lift import KIND_OF_BASIS, augmented, spec_of

NOISE = {"DEPOLARIZE1", "DEPOLARIZE2", "X_ERROR", "Y_ERROR", "Z_ERROR", "PAULI_CHANNEL_1", "PAULI_CHANNEL_2", "E",
         "ELSE_CORRELATED_ERROR", "HERALDED_ERASE", "HERALDED_PAULI_CHANNEL_1"}


def locate(aug, terms):
    """terms: list of (detector mask, observable list) of augmented DEM errors -> list of CircuitErrorLocation."""
    txt = []
    for dm, obs in terms:
        t = [f"D{i}" for i in range(dm.bit_length()) if dm >> i & 1] + [f"L{o}" for o in obs]
        txt.append("error(0.1) " + " ".join(t))
    filt = stim.DetectorErrorModel("\n".join(txt))
    ex = aug.explain_detector_error_model_errors(dem_filter=filt, reduce_to_one_representative_error=True)
    by = {}
    for e in ex:
        dm, obs = 0, []
        for t in e.dem_error_terms:
            if t.dem_target.is_relative_detector_id():
                dm ^= 1 << t.dem_target.val
            else:
                obs.append(t.dem_target.val)
        by[(dm, tuple(sorted(obs)))] = e.circuit_error_locations[0]
    return [by[(dm, tuple(sorted(obs)))] for dm, obs in terms]


def inject(noisy, locs):
    ops = list(noisy)
    ins = {}
    for loc in locs:
        k = loc.stack_frames[0].instruction_offset
        if loc.flipped_pauli_product:
            ins.setdefault(k, []).extend(loc.flipped_pauli_product)
        else:
            fm = loc.flipped_measurement
            ins.setdefault(("M", k), []).extend(fm.measured_observable)
    c = stim.Circuit()
    for k, op in enumerate(ops):
        if ("M", k) in ins:
            for gt in ins[("M", k)]:
                q = gt.gate_target.value
                # flip of a Z-basis measurement = X before it; X-basis measurement = Z before it
                c.append("X_ERROR" if gt.gate_target.is_z_target else "Z_ERROR", [q], 1.0)
        if op.name in NOISE:
            pass
        elif op.name in ("M", "MX", "MR", "MRX", "MY") and op.gate_args_copy():
            c.append(op.name, op.targets_copy())
        else:
            c.append(op)
        for gt in ins.get(k, []):
            q = gt.gate_target.value
            nm = "Y_ERROR" if gt.gate_target.is_y_target else ("X_ERROR" if gt.gate_target.is_x_target else "Z_ERROR")
            c.append(nm, [q], 1.0)
    det, obs = c.compile_detector_sampler().sample(1, separate_observables=True)
    return int(det.sum()), int(obs.sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lift", required=True)
    ap.add_argument("--n", type=int, default=20, help="hits checked per (R, basis)")
    a = ap.parse_args()
    res = json.load(open(a.lift))
    spec = spec_of(res["schedule"]).canonical()
    out = []
    for rec in res["per"]:
        if not rec["hits"]:
            continue
        R, basis = rec["R"], rec["basis"]
        noisy, aug, E, H, L, k0 = augmented(spec, R, basis)
        orig = noisy.detector_error_model(decompose_errors=False)
        ok = 0
        for h in rec["hits"][: a.n]:
            terms = []
            for col, dm in h["masks"].items():
                key = E["keys"][int(col)]
                hb = np.frombuffer(key[:H.shape[0]], np.uint8); lb = np.frombuffer(key[H.shape[0]:], np.uint8)
                obs = [i for i in range(k0) if lb[i]] + [k0 + i for i in range(H.shape[0]) if hb[i]] + \
                      [k0 + H.shape[0] + i for i in range(L.shape[0]) if lb[i]]
                terms.append((int(dm), obs))
            locs = locate(aug, terms)
            nd, no = inject(noisy, locs)
            # distinct original DEM terms: (detector mask, evaluator observables) pairwise distinct
            sig = {(dm, tuple(o for o in obs if o < k0)) for dm, obs in terms}
            good = nd == 0 and no > 0 and len(sig) == 11 and len(locs) == 11
            ok += good
            if len(out) < 3 or not good:
                out.append({"R": R, "basis": basis, "S": h["S"], "detectors_fired": nd, "observables_flipped": no,
                            "distinct_terms": len(sig),
                            "locations": [str(l) for l in locs]})
        print(f"R={R} {basis}: injected {min(a.n, len(rec['hits']))} hits, confirmed {ok}", flush=True)
        out.append({"R": R, "basis": basis, "checked": min(a.n, len(rec["hits"])), "confirmed": ok})
    path = a.lift.replace(".json", "_witness.json")
    open(path, "w").write(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
