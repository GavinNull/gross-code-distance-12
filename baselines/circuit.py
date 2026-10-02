"""Memory-experiment stim circuits from a `Schedule` (schedule-agnostic).

Noise model "uniform_depolarizing" (standard circuit-level SD6-like, as in arXiv:2308.07915 Sec. 6):
  - after every CNOT:                 DEPOLARIZE2(p) on (control, target)
  - after every reset (R / RX):       X_ERROR(p) / Z_ERROR(p)     (prepares the orthogonal state)
  - every measurement (M / MX):       result flipped with prob. p  (stim `M(p)` / `MX(p)`)
  - every qubit idle in a layer:      DEPOLARIZE1(p)
  - the initial data reset and the final data measurement are noisy in the same way.
Each schedule layer is one TICK. Before the first cycle one extra layer resets all data qubits
and any checks whose prep is pipelined into the previous cycle (paper footnote 2: depth 8Nc+1).

Detectors:
  - basis-type checks (Z checks for basis 'Z'): every cycle, cycle 0 compared to the deterministic
    initial value, later cycles to the previous cycle; plus final detectors built from data readout.
  - opposite-type checks: only when detectors='both' (cycles >= 1). Default 'basis' matches the
    paper's independent decoding of X and Z errors.
Observables: the k logical operators of the basis type (logical Z for basis 'Z').
"""
from __future__ import annotations

import numpy as np
import stim

from baselines.schedule import Schedule


def memory_circuit(sched: Schedule, HX: np.ndarray, HZ: np.ndarray, logicals: np.ndarray,
                   rounds: int, basis: str, p: float, detectors: str = "basis") -> stim.Circuit:
    assert basis in ("X", "Z") and detectors in ("basis", "both") and rounds >= 1
    c = stim.Circuit()
    allq = list(range(sched.num_qubits))
    xset, zset = set(sched.x_checks), set(sched.z_checks)
    wrapped = set(sched.wrapped_checks())

    def reset(qs, b):
        if not qs:
            return
        c.append("R" if b == "Z" else "RX", qs)
        if p > 0:
            c.append("X_ERROR" if b == "Z" else "Z_ERROR", qs, p)

    def idle(touched):
        if p > 0:
            idle_q = [q for q in allq if q not in touched]
            if idle_q:
                c.append("DEPOLARIZE1", idle_q, p)

    meas_count = 0
    rec: dict[tuple[int, int], int] = {}   # (qubit, cycle) -> absolute measurement index

    def measure(qs, b, cyc):
        nonlocal meas_count
        if not qs:
            return
        name = "M" if b == "Z" else "MX"
        if p > 0:
            c.append(name, qs, p)
        else:
            c.append(name, qs)
        for q in qs:
            rec[(q, cyc)] = meas_count
            meas_count += 1

    # ---- initial layer
    reset(sched.data, basis)
    reset(sorted(q for q in wrapped if q in xset), "X")
    reset(sorted(q for q in wrapped if q in zset), "Z")
    touched0 = set(sched.data) | wrapped
    idle(touched0)
    c.append("TICK")

    # ---- cycles
    for cyc in range(rounds):
        for L in sched.layers:
            last = cyc == rounds - 1
            px = [q for q in L.prep_x if not (last and q in wrapped)]
            pz = [q for q in L.prep_z if not (last and q in wrapped)]
            reset(px, "X")
            reset(pz, "Z")
            if L.cnots:
                flat = [a for pair in L.cnots for a in pair]
                c.append("CX", flat)
                if p > 0:
                    c.append("DEPOLARIZE2", flat, p)
            measure(L.meas_z, "Z", cyc)
            measure(L.meas_x, "X", cyc)
            idle(set(L.qubits()) - (set(L.prep_x) - set(px)) - (set(L.prep_z) - set(pz)))
            c.append("TICK")

        # detectors for this cycle
        for checks, typ in ((sched.x_checks, "X"), (sched.z_checks, "Z")):
            is_basis = typ == basis
            if not is_basis and detectors == "basis":
                continue
            for i, q in enumerate(checks):
                cur = rec[(q, cyc)] - meas_count
                if cyc == 0:
                    if is_basis:
                        c.append("DETECTOR", [stim.target_rec(cur)], [i, cyc, 0 if typ == "X" else 1])
                else:
                    prev = rec[(q, cyc - 1)] - meas_count
                    c.append("DETECTOR", [stim.target_rec(cur), stim.target_rec(prev)],
                             [i, cyc, 0 if typ == "X" else 1])

    # ---- final data readout
    measure(sched.data, basis, rounds)
    data_rec = {j: rec[(q, rounds)] - meas_count for j, q in enumerate(sched.data)}
    H = HZ if basis == "Z" else HX
    checks = sched.z_checks if basis == "Z" else sched.x_checks
    for i, q in enumerate(checks):
        targets = [stim.target_rec(data_rec[j]) for j in np.nonzero(H[i])[0]]
        targets.append(stim.target_rec(rec[(q, rounds - 1)] - meas_count))
        c.append("DETECTOR", targets, [i, rounds, 0 if basis == "X" else 1])
    for k, op in enumerate(logicals):
        c.append("OBSERVABLE_INCLUDE", [stim.target_rec(data_rec[j]) for j in np.nonzero(op)[0]], k)
    return c


def check_deterministic(circ_noiseless: stim.Circuit, shots: int = 64) -> dict:
    """Noiseless circuit: every detector & observable must be 0 in every shot, and stim's
    DEM construction must accept a noisy version (it errors on non-deterministic detectors)."""
    circ_noiseless.detector_error_model()   # raises if any detector/observable is non-deterministic
    s = circ_noiseless.compile_detector_sampler()
    det, obs = s.sample(shots, separate_observables=True)
    return {"num_detectors": circ_noiseless.num_detectors,
            "num_observables": circ_noiseless.num_observables,
            "detector_flips": int(det.sum()), "observable_flips": int(obs.sum())}
