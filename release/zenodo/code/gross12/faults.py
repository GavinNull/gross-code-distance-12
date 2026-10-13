"""Explicit circuit faults: location format and injection.

A fault is one Pauli component of one noise channel of the SD6 circuit returned by
gross12.ext.noisy_circuit(spec, code, R, basis) (flattened):
    {"op": instruction index in that circuit (a DEPOLARIZE1/2, X_ERROR or Z_ERROR instruction),
     "tick": number of TICKs before it (= layer), "gate": its name, "qubits": the targets of the channel component,
     "paulis": e.g. ["X12", "Z148"]}
Injection removes all noise channels and inserts the listed Paulis with probability 1 at the same places.
"""
from __future__ import annotations

import numpy as np
import stim


def fault_from_location(loc: stim.CircuitErrorLocation) -> dict:
    assert len(loc.stack_frames) == 1
    rng = loc.instruction_targets
    paulis = []
    for p in loc.flipped_pauli_product:
        t = p.gate_target
        paulis.append(("X" if t.is_x_target else "Y" if t.is_y_target else "Z") + str(t.value))
    assert loc.flipped_measurement is None or loc.flipped_measurement.record_index is None or paulis
    return {"op": int(loc.stack_frames[0].instruction_offset), "tick": int(loc.tick_offset), "gate": rng.gate,
            "qubits": [t.gate_target.value for t in rng.targets_in_range], "paulis": paulis}


NOISE = {"DEPOLARIZE1", "DEPOLARIZE2", "X_ERROR", "Y_ERROR", "Z_ERROR"}


def inject(noisy: stim.Circuit, faults: list[dict]) -> stim.Circuit:
    by_op = {}
    for f in faults:
        inst = noisy[f["op"]]
        assert inst.name == f["gate"] and inst.name in NOISE, (f, inst.name)
        tg = {t.value for t in inst.targets_copy()}
        assert set(f["qubits"]) <= tg and all(int(p[1:]) in f["qubits"] for p in f["paulis"]), f
        by_op.setdefault(f["op"], []).append(f)
    out = stim.Circuit()
    for i, inst in enumerate(noisy):
        if inst.name in NOISE:
            for f in by_op.get(i, []):
                for p in f["paulis"]:
                    out.append(f"{p[0]}_ERROR", [int(p[1:])], 1.0)
            continue
        out.append(inst)
    return out


def outcome(circ: stim.Circuit):
    det, obs = circ.compile_detector_sampler(seed=0).sample(4, separate_observables=True)
    assert (det == det[0]).all() and (obs == obs[0]).all(), "injected circuit is not deterministic"
    return np.flatnonzero(det[0]).tolist(), np.flatnonzero(obs[0]).tolist()
