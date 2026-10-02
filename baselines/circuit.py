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


# ---------------------------------------------------------------------- pipelined (staggered) cycles
# Added for E-003 (Strikis-Browne-Beverland left-right circuit, arXiv:2603.05481 Fig. 12).
# `memory_circuit` above assumes every check's CNOTs fall inside one listed cycle (only a check's
# *prep* may be pipelined into the previous cycle). In a staggered schedule a check's CNOT window
# itself wraps around the cycle boundary (e.g. X checks of round r overlap Z checks of round r+1),
# so "cycle c of the listed layers" no longer equals "round c of every check". This generator
# unrolls the cyclic schedule per check instead. `memory_circuit` is left unchanged (E-002).

def unroll_schedule(sched: Schedule, rounds: int) -> dict:
    """Absolute layer of every operation of every check instance (round j = 0..rounds-1).

    Each check q has cyclic prep layer tp, CNOT layers t_k and meas layer tm (0..D-1, read cyclically
    from tp as in `Schedule.validate`). Instance j of q: prep at sigma + tp_q + D*(j + w_q), CNOT at
    prep + ((t_k - tp_q) mod D), meas at prep + ((tm - tp_q) mod D). Data qubits are reset at layer 0
    and must not be touched before layer 1. For each global shift sigma in 0..D-1 the per-check offset
    w_q in {-1, 0} is the earliest with prep >= 0; the sigma giving the shortest circuit is used
    (ties -> smallest sigma). For the IBM schedule this reproduces the layout of `memory_circuit`
    (initial layer = data reset + pipelined Z prep).
    """
    D = sched.depth
    data_set = set(sched.data)
    info = {}
    for q in sched.x_checks + sched.z_checks:
        tp = next(t for t, L in enumerate(sched.layers) if q in L.prep_x + L.prep_z)
        tm = next(t for t, L in enumerate(sched.layers) if q in L.meas_x + L.meas_z)
        cn = [((t - tp) % D, pair) for t, L in enumerate(sched.layers) for pair in L.cnots if q in pair]
        info[q] = (tp, (tm - tp) % D, sorted(cn))
    best = None
    for sigma in range(D):
        start = {}
        for q, (tp, dm, cn) in info.items():
            s = sigma + tp - D
            if s < 0:
                s += D
            # first CNOT must come after the data reset at layer 0
            if s + min(d for d, _ in cn) < 1:
                s += D
            start[q] = s
        end = max(start[q] + D * (rounds - 1) + info[q][1] for q in info)
        if best is None or end < best[0]:
            best = (end, sigma, start)
    end, sigma, start = best
    ops = {"prep": [], "cnot": [], "meas": []}   # (layer, ...)
    for q, (tp, dm, cn) in info.items():
        for j in range(rounds):
            s = start[q] + D * j
            ops["prep"].append((s, q, j))
            for d, pair in cn:
                ops["cnot"].append((s + d, pair))
            ops["meas"].append((s + dm, q, j))
    last_data = max(t for t, pair in ops["cnot"] if set(pair) & data_set)
    return {"sigma": sigma, "start": start, "ops": ops, "last_layer": end, "last_data_cnot": last_data}


def pipelined_memory_circuit(sched: Schedule, HX: np.ndarray, HZ: np.ndarray, logicals: np.ndarray,
                             rounds: int, basis: str, p: float, detectors: str = "basis") -> stim.Circuit:
    """Same noise model, detector and observable conventions as `memory_circuit`, but the cycle is
    unrolled per check (see `unroll_schedule`). Layout:
      layer 0               : data reset (basis) + any check preps scheduled there
      layers 0..last_layer  : unrolled check operations; every qubit not touched in a layer idles
      final layer           : data readout (noisy measurement, no idle noise, as in memory_circuit)
    """
    assert basis in ("X", "Z") and detectors in ("basis", "both") and rounds >= 1
    U = unroll_schedule(sched, rounds)
    T = U["last_layer"] + 1
    xset = set(sched.x_checks)
    allq = list(range(sched.num_qubits))
    layers = [{"prep_x": [], "prep_z": [], "cnots": [], "meas_x": [], "meas_z": []} for _ in range(T)]
    for t, q, j in U["ops"]["prep"]:
        layers[t]["prep_x" if q in xset else "prep_z"].append(q)
    for t, pair in U["ops"]["cnot"]:
        layers[t]["cnots"].append(pair)
    meas_round = {}
    for t, q, j in U["ops"]["meas"]:
        layers[t]["meas_x" if q in xset else "meas_z"].append(q)
        meas_round[(t, q)] = j
    for t, L in enumerate(layers):
        qs = [a for c in L["cnots"] for a in c] + L["prep_x"] + L["prep_z"] + L["meas_x"] + L["meas_z"]
        if t == 0:
            qs += list(sched.data)
        if len(qs) != len(set(qs)):
            raise ValueError(f"unrolled layer {t}: a qubit is used twice")
    if any(set(pair) & set(sched.data) for pair in layers[0]["cnots"]):
        raise ValueError("data CNOT in layer 0 (collides with data reset)")

    c = stim.Circuit()
    meas_count = 0
    rec: dict[tuple[int, int], int] = {}

    def reset(qs, b):
        if not qs:
            return
        c.append("R" if b == "Z" else "RX", sorted(qs))
        if p > 0:
            c.append("X_ERROR" if b == "Z" else "Z_ERROR", sorted(qs), p)

    def measure(qs, b, key):
        nonlocal meas_count
        if not qs:
            return
        qs = sorted(qs)
        name = "M" if b == "Z" else "MX"
        c.append(name, qs, p) if p > 0 else c.append(name, qs)
        for q in qs:
            rec[(q, key(q))] = meas_count
            meas_count += 1

    for t, L in enumerate(layers):
        touched = set()
        if t == 0:
            reset(sched.data, basis)
            touched |= set(sched.data)
        reset(L["prep_x"], "X")
        reset(L["prep_z"], "Z")
        if L["cnots"]:
            flat = [a for pair in sorted(L["cnots"]) for a in pair]
            c.append("CX", flat)
            if p > 0:
                c.append("DEPOLARIZE2", flat, p)
        measure(L["meas_z"], "Z", lambda q, t=t: meas_round[(t, q)])
        measure(L["meas_x"], "X", lambda q, t=t: meas_round[(t, q)])
        touched |= set(a for pr in L["cnots"] for a in pr) | set(L["prep_x"] + L["prep_z"] + L["meas_x"] + L["meas_z"])
        if p > 0:
            idle_q = [q for q in allq if q not in touched]
            if idle_q:
                c.append("DEPOLARIZE1", idle_q, p)
        c.append("TICK")

    # detectors (same structure / coordinates as memory_circuit), emitted after all syndrome rounds
    for cyc in range(rounds):
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
    measure(sched.data, basis, lambda q: rounds)
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
