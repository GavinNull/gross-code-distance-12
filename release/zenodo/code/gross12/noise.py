"""SD6 circuit-level noise (Gidney, Newman, Fowler, Broughton, arXiv:2108.10457, Tables 1-2, column SD6).

Applied layer by layer (layers are separated by TICK):
  after every CX                         DEPOLARIZE2(p) on its two qubits
  after every reset R / RX               X_ERROR(p) / Z_ERROR(p)
  before every measurement M / MX        X_ERROR(p) / Z_ERROR(p)
  every qubit not acted on in the layer  DEPOLARIZE1(p)   (qubits = all qubits of the circuit)
The input must be noiseless.  Only the gates of the template (R, RX, M, MX, CX) and annotations occur.
For distance questions p is irrelevant (any 0 < p < 1/2 gives the same set of fault mechanisms).
"""
from __future__ import annotations

import stim

ANNOTATIONS = {"DETECTOR", "OBSERVABLE_INCLUDE", "QUBIT_COORDS", "SHIFT_COORDS"}


def add_sd6(circuit: stim.Circuit, p: float = 1e-3) -> stim.Circuit:
    layers = [[]]
    for inst in circuit.flattened():
        if inst.name == "TICK":
            layers.append([])
        else:
            layers[-1].append(inst)
    qubits = set()
    for layer in layers:
        for inst in layer:
            if inst.name not in ANNOTATIONS:
                qubits.update(t.value for t in inst.targets_copy())
    out = stim.Circuit()
    for li, layer in enumerate(layers):
        if li > 0:
            out.append("TICK")
        touched = set()
        for inst in layer:
            name = inst.name
            if name in ANNOTATIONS:
                out.append(inst)
                continue
            qs = [t.value for t in inst.targets_copy()]
            assert not touched.intersection(qs) and len(qs) == len(set(qs)), f"layer {li}: qubit used twice"
            touched.update(qs)
            if name == "CX":
                out.append(inst)
                out.append("DEPOLARIZE2", qs, p)
            elif name in ("R", "RX"):
                out.append(inst)
                out.append("Z_ERROR" if name == "RX" else "X_ERROR", qs, p)
            elif name in ("M", "MX"):
                assert not inst.gate_args_copy()
                out.append("Z_ERROR" if name == "MX" else "X_ERROR", qs, p)
                out.append(inst)
            else:
                raise NotImplementedError(name)
        idle = sorted(qubits - touched)
        if idle:
            out.append("DEPOLARIZE1", idle, p)
    return out
