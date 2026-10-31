"""Item (4): does an undetectable logical found in the R0-round experiment stay an undetectable logical for every
larger R?  Empirical check in stim, independent of the step model.

 1. witness = list of DEM terms (detector set, observable set) of the evaluator's SD6 R0-round DEM, taken from
    direct.jsonl (found by the auditor's own direct DEM search); verify it on the R0 DEM (distinct terms, detectors
    cancel, observable != 0).
 2. for each term, stim's explain_detector_error_model_errors gives one representative physical fault (a Pauli
    product at one noise instruction).  Its position is converted to a TICK boundary b of the R0 circuit: a gate
    noise / reset noise / idle noise sits after the gate (b = layer + 1), a measurement-flip noise sits before the
    measurement (b = layer).  Nothing else acts on those qubits between the noise channel and that boundary, so
    the Pauli at the boundary is the same fault.
 3. into the NOISELESS evaluator circuit with R rounds, insert all Paulis (probability-1 X/Y/Z_ERROR) at boundary
    b + k P (k = time shift in rounds, R >= R0 + k), sample once: all detectors must be 0 and the observable flips
    must equal the witness' observable set.  Control: dropping any single fault makes some detector fire.

k = 0 places the witness at the start of a longer experiment (the E-043 claim); k > 0 places it in the middle.

  uv run python -m search.experiments.e043_audit.persist ibmg Z 1 10 1,2,3,5,8,12,20,30 --shifts 0,1,3
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import stim

from search.experiments.e043_audit.common import OUT, code_of, info, jdump, load

NOISE = {"DEPOLARIZE1", "DEPOLARIZE2", "X_ERROR", "Y_ERROR", "Z_ERROR", "PAULI_CHANNEL_1", "PAULI_CHANNEL_2"}
ANN = {"TICK", "DETECTOR", "OBSERVABLE_INCLUDE", "QUBIT_COORDS", "SHIFT_COORDS"}


def circuits(name, basis, R):
    from evaluators import candidate as cand
    from evaluators.noise import add_noise
    cname = info(name)[0]
    clean = cand.memory_circuit(cand.parse_schedule(load(name)), code_of(cname), basis, R).flattened()
    noisy = add_noise(clean, "sd6", 1e-3).flattened()
    return clean, noisy


def dem_terms(noisy):
    out = {}
    for e in noisy.detector_error_model(approximate_disjoint_errors=True, flatten_loops=True).flattened():
        if e.type != "error":
            continue
        ds, os_ = set(), set()
        for t in e.targets_copy():
            if t.is_relative_detector_id():
                ds ^= {t.val}
            elif t.is_logical_observable_id():
                os_ ^= {t.val}
        out[frozenset(ds)] = frozenset(os_)
    return out


def locate(noisy, witness):
    """witness: list of (dets, obs) -> list of (boundary, {qubit: pauli})."""
    filt = stim.DetectorErrorModel()
    for ds, os_ in witness:
        filt.append("error", 1.0, [stim.target_relative_detector_id(d) for d in ds] +
                    [stim.target_logical_observable_id(o) for o in os_])
    ex = noisy.explain_detector_error_model_errors(dem_filter=filt, reduce_to_one_representative_error=True)
    ops = list(noisy)
    tick_before = []
    t = 0
    for op in ops:
        tick_before.append(t)
        if op.name == "TICK":
            t += 1
    res = {}
    for e in ex:
        key = frozenset(x.dem_target.val for x in e.dem_error_terms if x.dem_target.is_relative_detector_id())
        loc = e.circuit_error_locations[0]
        off = loc.stack_frames[0].instruction_offset
        assert ops[off].name in NOISE, ops[off].name
        lay = tick_before[off]
        assert lay == loc.tick_offset
        paulis = {}
        for g in loc.flipped_pauli_product:
            gt = g.gate_target
            p = "X" if gt.is_x_target else "Y" if gt.is_y_target else "Z"
            paulis[gt.value] = p
        qs = set(paulis)
        # gate on these qubits in the same layer: before or after the noise instruction?
        lo = off
        while lo > 0 and ops[lo - 1].name != "TICK":
            lo -= 1
        hi = off
        while hi < len(ops) and ops[hi].name != "TICK":
            hi += 1
        before = after = False
        for i in range(lo, hi):
            op = ops[i]
            if op.name in NOISE or op.name in ANN:
                continue
            tq = {x.value for x in op.targets_copy() if x.is_qubit_target}
            if tq & qs:
                if i < off:
                    before = True
                else:
                    after = True
        assert not (before and after), "ambiguous layer"
        b = lay if after else lay + 1
        res[key] = (b, paulis, ops[off].name)
    return [res[frozenset(ds)] for ds, _ in witness]


def inject(clean, faults, shift_ticks, drop=None):
    layers, cur = [], stim.Circuit()
    for op in clean:
        if op.name == "TICK":
            layers.append(cur)
            cur = stim.Circuit()
        else:
            cur.append(op)
    layers.append(cur)
    at = {}
    for i, (b, paulis, _) in enumerate(faults):
        if i == drop:
            continue
        at.setdefault(b + shift_ticks, []).append(paulis)
    assert max(at) <= len(layers) - 1 or not at, "boundary beyond circuit"
    c = stim.Circuit()
    for li, lay in enumerate(layers):
        for paulis in at.get(li, []):
            for q, p in paulis.items():
                c.append(f"{p}_ERROR", [q], 1.0)
        c += lay
        if li < len(layers) - 1:
            c.append("TICK")
    s = c.compile_detector_sampler().sample(1, append_observables=True)[0]
    nd = c.num_detectors
    return int(s[:nd].sum()), np.flatnonzero(s[nd:]).tolist()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("basis")
    ap.add_argument("R0", type=int)
    ap.add_argument("W", type=int)
    ap.add_argument("Rs")
    ap.add_argument("--shifts", default="0")
    a = ap.parse_args()
    P = int(load(a.name)["period"])
    recs = [json.loads(l) for l in open(OUT / "direct.jsonl")]
    recs = [r for r in recs if r["spec"] == a.name and r["basis"] == a.basis and r["R"] == a.R0
            and r.get("witness_terms") and r["found_check"]["weight"] == a.W]
    assert recs, "no witness in direct.jsonl"
    witness = [(frozenset(d), frozenset(o)) for d, o in recs[-1]["witness_terms"]]
    clean0, noisy0 = circuits(a.name, a.basis, a.R0)
    T = dem_terms(noisy0)
    dx, ox = set(), set()
    for ds, os_ in witness:
        assert T[ds] == os_
        dx ^= ds
        ox ^= os_
    assert not dx and ox and len(set(witness)) == len(witness)
    faults = locate(noisy0, witness)
    rec = {"name": a.name, "basis": a.basis, "R0": a.R0, "weight": len(witness), "obs": sorted(ox),
           "faults": [[b, {str(q): p for q, p in pa.items()}, g] for b, pa, g in faults], "runs": []}
    for k in [int(x) for x in a.shifts.split(",")]:
        for R in [int(x) for x in a.Rs.split(",")]:
            if R < a.R0 + k:
                continue
            clean, _ = circuits(a.name, a.basis, R)
            nfire, obs = inject(clean, faults, k * P)
            ctl = [inject(clean, faults, k * P, drop=i)[0] for i in range(len(faults))]
            rec["runs"].append({"shift_rounds": k, "R": R, "detectors_fired": nfire, "obs": obs,
                                "ok": nfire == 0 and obs == sorted(ox),
                                "drop_one_min_fired": min(ctl)})
    rec["all_ok"] = all(r["ok"] and r["drop_one_min_fired"] > 0 for r in rec["runs"])
    jdump(rec, "persist.jsonl")


if __name__ == "__main__":
    main()
