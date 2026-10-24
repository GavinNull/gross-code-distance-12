"""SD6 with the idle channel rescaled (SM S7): model "lam<x>" = SD6 (code/gross12/noise.py) with every idle
DEPOLARIZE1(p) replaced by DEPOLARIZE1(x p) (dropped for x = 0); lam1 is SD6 itself.  Model "si1000cx" (only in the earlier
sampling pooled in data/ler/sd6_lambda_gross/earlier/, not used for any number of the paper): SI1000 coefficients
(arXiv:2108.10457 Table 2) applied to the CX circuit with CX as the native two-qubit gate (DEPOLARIZE2(p) after CX,
reset flip 2p, pre-measurement flip 5p, idle DEPOLARIZE1(p/10), plus DEPOLARIZE1(2p) on the idle qubits of every layer
with a measurement or reset).  The memory circuits contain no
single-qubit gates (only R/RX, CX, M/MX; asserted), so in the SD6 circuit every DEPOLARIZE1 is the idle channel of its
layer; its targets are checked to be exactly the qubits not acted on in that layer.
"""
import sys
from pathlib import Path

import stim

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gross12.noise import add_sd6                       # noqa: E402

ANN = {"DETECTOR", "OBSERVABLE_INCLUDE", "QUBIT_COORDS", "SHIFT_COORDS", "MPAD"}
NOISE = {"DEPOLARIZE1", "DEPOLARIZE2", "X_ERROR", "Z_ERROR", "Y_ERROR"}


def split_layers(circuit: stim.Circuit):
    layers = [[]]
    for inst in circuit.flattened():
        if inst.name == "TICK":
            layers.append([])
        else:
            layers[-1].append(inst)
    return layers


def _qubits(inst):
    return [t.value for t in inst.targets_copy() if t.is_qubit_target]


def rescale_idle(noisy: stim.Circuit, lam: float) -> stim.Circuit:
    layers = split_layers(noisy)
    allq = set()
    for L in layers:
        for i in L:
            if i.name not in ANN and i.name not in NOISE:
                allq.update(_qubits(i))
    out = stim.Circuit()
    for li, L in enumerate(layers):
        if li > 0:
            out.append("TICK")
        touched = set()
        for i in L:
            if i.name not in ANN and i.name not in NOISE:
                touched.update(_qubits(i))
        for i in L:
            if i.name == "DEPOLARIZE1":
                qs = _qubits(i)
                assert set(qs) == allq - touched, "DEPOLARIZE1 that is not the idle channel"
                if lam > 0:
                    out.append("DEPOLARIZE1", qs, lam * i.gate_args_copy()[0])
            else:
                assert i.name != "DEPOLARIZE1"
                out.append(i)
    return out


SI1000_SPEC = {"two_qubit_gate_depolarize2": 1.0, "single_qubit_gate_depolarize1": 0.1, "measurement_flip": 5.0,
               "reset_flip": 2.0, "idle_depolarize1": 0.1, "resonator_idle_depolarize1": 2.0}


def si1000cx(nl: stim.Circuit, p: float) -> stim.Circuit:
    s = SI1000_SPEC
    layers = split_layers(nl)
    allq = set()
    for L in layers:
        for i in L:
            if i.name not in ANN:
                allq.update(_qubits(i))
    out = stim.Circuit()
    for li, L in enumerate(layers):
        if li > 0:
            out.append("TICK")
        touched, mr = set(), set()
        for i in L:
            n = i.name
            if n in ANN:
                out.append(i); continue
            qs = _qubits(i); touched.update(qs)
            if n == "CX":
                out.append(i); out.append("DEPOLARIZE2", qs, s["two_qubit_gate_depolarize2"] * p)
            elif n in ("R", "RX"):
                mr.update(qs); out.append(i)
                out.append("Z_ERROR" if n == "RX" else "X_ERROR", qs, s["reset_flip"] * p)
            elif n in ("M", "MX"):
                mr.update(qs)
                out.append("Z_ERROR" if n == "MX" else "X_ERROR", qs, s["measurement_flip"] * p); out.append(i)
            else:
                raise NotImplementedError(n)
        idle = sorted(allq - touched)
        if idle:
            out.append("DEPOLARIZE1", idle, s["idle_depolarize1"] * p)
            if mr:
                out.append("DEPOLARIZE1", idle, s["resonator_idle_depolarize1"] * p)
    return out


def noisy_from(nl: stim.Circuit, model: str, p: float) -> stim.Circuit:
    for inst in nl.flattened():
        assert inst.name in ANN or inst.name in ("TICK", "R", "RX", "CX", "M", "MX"), inst.name
    if model == "si1000cx":
        return si1000cx(nl, p)
    assert model.startswith("lam"), model
    lam = float(model[3:])
    base = add_sd6(nl, p)
    return base if lam == 1.0 else rescale_idle(base, lam)
