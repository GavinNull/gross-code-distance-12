"""E-017 stage 4: single-noisy-round instance (Shaw-Terhal 2604.09797 Prop. 1: for a two-round morphing circuit
d_circ(T) = d_circ(1) with ideal preparation / readout).

Build a memory circuit with `pad` noiseless rounds, then one noisy round, then `pad` noiseless rounds
(the noiseless rounds play the role of ideal stabiliser measurements). Noise = sd6 restricted to the 8 layers
(reset, 6 CNOT, measure) of the noisy round. Its DEM is the 'extended code' of the morphing circuit:
columns = single-fault images, rows = detectors (+ observables).
"""
from __future__ import annotations

import stim

from evaluators.noise import add_noise
from search.experiments.e017.morph import TWO_GROSS, Morph, check_deterministic

LAYERS_PER_ROUND = 8   # reset, 6 CNOT, measure


NOISE = {"DEPOLARIZE1", "DEPOLARIZE2", "X_ERROR", "Z_ERROR", "Y_ERROR", "PAULI_CHANNEL_1", "PAULI_CHANNEL_2"}


def window_noise(noisy: stim.Circuit, lo_tick: int, hi_tick: int) -> stim.Circuit:
    """Keep noise only in layers lo_tick..hi_tick (layer index = number of TICKs before it)."""
    out = stim.Circuit()
    tick = 0
    for ins in noisy.flattened():
        if ins.name == "TICK":
            tick += 1
            out.append(ins)
            continue
        inside = lo_tick <= tick <= hi_tick
        if ins.name in NOISE:
            if inside:
                out.append(ins)
            continue
        if ins.name in ("M", "MX", "MY") and ins.gate_args_copy() and not inside:
            out.append(stim.CircuitInstruction(ins.name, ins.targets_copy()))
            continue
        out.append(ins)
    return out


def one_round_circuit(hom="x", swap23=False, basis="Z", pad=1, p=1e-3, first_j=1, noisy_round=None):
    M = Morph(TWO_GROSS, hom, swap23=swap23)
    R = 2 * pad + 1
    c = M.memory_circuit(basis, R, first_j=first_j)
    assert all(check_deterministic(c))
    noisy = add_noise(c, "sd6", p)
    r = pad if noisy_round is None else noisy_round      # 0-based round index of the noisy round
    lo = r * LAYERS_PER_ROUND
    hi = lo + LAYERS_PER_ROUND - 1
    return window_noise(noisy, lo, hi), M


if __name__ == "__main__":
    import sys
    for basis in "XZ":
        for first_j in (0, 1):
            c, M = one_round_circuit(basis=basis, first_j=first_j)
            dem = c.detector_error_model(decompose_errors=False)
            ncols = sum(1 for ins in dem.flattened() if ins.type == "error")
            print(basis, first_j, "detectors", c.num_detectors, "DEM columns", ncols, flush=True)
