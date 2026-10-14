"""E-026b: idle-noise sensitivity of the gross LER comparison (p18 vs Fig. 12 vs IBM).  experimenter.

Noise is produced WITHOUT touching evaluators/: we take the evaluator's sd6 circuit (evaluators.noise.add_noise
"sd6", read-only use) and post-process it.

  model "lam<x>"   (e.g. lam0, lam0.1, lam0.3, lam1): SD6 with the idle DEPOLARIZE1 strength scaled to x*p.
      The three memory circuits contain NO single-qubit gates (only R/RX, CX, M/MX; checked in assert_no_1q), so in
      the sd6 output EVERY DEPOLARIZE1 instruction is the per-layer idle channel.  We additionally check that its
      targets are exactly the qubits not acted on in that layer.  lam1 == sd6 (identity, asserted in validate.py).
  model "si1000cx": SI1000 coefficients (arXiv:2108.10457 Table 2, as in evaluators.noise.SI1000_SPEC) applied to
      the CX circuit with CX treated as the native two-qubit gate (DEPOLARIZE2(p) after CX), reset flip 2p,
      pre-measurement flip 5p, idle DEPOLARIZE1(p/10), plus ResonatorIdle DEPOLARIZE1(2p) on qubits idle in any layer
      that contains a measurement or reset (default evaluator convention: not on gate qubits).
      NOT the standard SI1000: the evaluator's si1000 refuses CX (native gate is CZ, N2 issue), and compiling
      CX -> H.CZ.H would add single-qubit layers.  This is the "CX-native SI1000" reference.
"""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")

import stim

from search.experiments.e026.common import noiseless, PERIOD, CIRCS, DCIRC, ROOT  # noqa: F401
from evaluators.noise import add_noise, split_layers, SI1000_SPEC

OUT = ROOT / "results" / "E-026b-idle-sensitivity"
LAMS = (0.0, 0.1, 0.3, 1.0)
MODELS = ("lam0", "lam0.1", "lam0.3", "lam1", "si1000cx")
ANN = {"DETECTOR", "OBSERVABLE_INCLUDE", "QUBIT_COORDS", "SHIFT_COORDS", "MPAD"}
NOISE = {"DEPOLARIZE1", "DEPOLARIZE2", "X_ERROR", "Z_ERROR", "Y_ERROR"}


def _qubits(inst):
    return [t.value for t in inst.targets_copy() if t.is_qubit_target]


def assert_no_1q(circ: stim.Circuit):
    for inst in circ.flattened():
        n = inst.name
        if n in ANN or n == "TICK":
            continue
        assert n in ("R", "RX", "CX", "M", "MX"), n


def rescale_idle(noisy: stim.Circuit, lam: float) -> stim.Circuit:
    """sd6 circuit -> same with every idle DEPOLARIZE1(p) replaced by DEPOLARIZE1(lam*p) (dropped if lam == 0)."""
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


def model_lam(model: str):
    return float(model[3:]) if model.startswith("lam") else None


def noisy_from(nl: stim.Circuit, model: str, p: float) -> stim.Circuit:
    assert_no_1q(nl)
    if model == "si1000cx":
        return si1000cx(nl, p)
    lam = model_lam(model)
    base = add_noise(nl, "sd6", p)
    return base if lam == 1.0 else rescale_idle(base, lam)


def noisy(name: str, basis: str, rounds: int, p: float, model: str) -> stim.Circuit:
    return noisy_from(noiseless(name, basis, rounds), model, p)
