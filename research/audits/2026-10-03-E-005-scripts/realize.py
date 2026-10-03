"""Realise an extended-code logical as an explicit set of circuit faults in the project's own memory circuit
(baselines.circuit.pipelined_memory_circuit, noiseless) and verify by injection: 0 detectors fire, >=1 observable
flips.  Independent of the evaluator's DEM machinery.

Fault vocabulary (one fault each, all are single components of SD6 channels):
  data error  : Pauli P on data qubit q at the end of layer t (after that layer's CNOTs) -> component of the
                DEPOLARIZE2 after a CNOT on q, or DEPOLARIZE1 idle, or reset error at t=0;
  hook error  : P on the ancilla of check c, instance j, right after its (l-1)-th CNOT (component I(x)P of the
                DEPOLARIZE2 after that CNOT).
P = X for X-type (Z-basis memory), Z for Z-type (X-basis memory).
Choice of times/rounds is a small exact search (CP-SAT over XOR signatures)."""
from __future__ import annotations
import numpy as np
import stim
from baselines.circuit import pipelined_memory_circuit, unroll_schedule


def _with_errors(base: stim.Circuit, errs):
    """errs: list of (tick, pauli, qubit) -> new circuit with deterministic errors at the end of that tick."""
    by = {}
    for t, P, q in errs:
        by.setdefault(t, []).append((P, q))
    c = stim.Circuit()
    tick = 0
    for ins in base:
        if ins.name == "TICK":
            for P, q in by.get(tick, []):
                c.append(f"{P}_ERROR", [q], 1.0)
            tick += 1
        c.append(ins)
    return c


def signature(base, errs):
    c = _with_errors(base, errs)
    s = c.compile_detector_sampler()
    d, o = s.sample(1, separate_observables=True)
    return np.concatenate([d[0], o[0]]).astype(np.uint8), base.num_detectors


def realize(sched, code, err_type, data_cols, hooks, rounds=3, time_limit=60):
    """data_cols: data column indices; hooks: list of (check_row, l) meaning residual suffix starting at position l
    (0-based; error after the l-th CNOT, i.e. on the qubits order[l:]) of a check of type err_type.
    Returns dict with feasible flag and the chosen fault list."""
    from ortools.sat.python import cp_model
    basis = "Z" if err_type == "X" else "X"
    L = code.LZ if basis == "Z" else code.LX     # observables measured in `basis`
    base = pipelined_memory_circuit(sched, code.HX, code.HZ, L, rounds, basis, 0.0, "basis")
    U = unroll_schedule(sched, rounds)
    T = U["last_layer"] + 1
    D = sched.depth
    checks = sched.x_checks if err_type == "X" else sched.z_checks
    # per check: sorted offsets of its CNOTs from its prep (cyclic)
    cand = []   # (group id, errs)
    groups = []
    for gi, col in enumerate(data_cols):
        q = sched.data[col]
        groups.append([(t, ) for t in range(T)])
        for t in range(T):
            cand.append((gi, [(t, err_type, q)]))
    for hi, (row, l) in enumerate(hooks):
        q = checks[row]
        tp = next(t for t, Lr in enumerate(sched.layers) if q in Lr.prep_x + Lr.prep_z)
        offs = sorted(((t - tp) % D) for t, Lr in enumerate(sched.layers) for a, b in Lr.cnots if q in (a, b))
        for j in range(rounds):
            t_cnot = U["start"][q] + D * j + offs[l - 1]
            cand.append((len(data_cols) + hi, [(t_cnot, err_type, q)]))
    sigs = np.array([signature(base, e)[0] for _, e in cand])
    nd = base.num_detectors
    md = cp_model.CpModel()
    v = [md.NewBoolVar(f"v{i}") for i in range(len(cand))]
    ng = len(data_cols) + len(hooks)
    for g in range(ng):
        md.AddExactlyOne([v[i] for i, (gg, _) in enumerate(cand) if gg == g])
    one = md.NewBoolVar("one"); md.Add(one == 1)
    for d in range(nd):
        idx = np.nonzero(sigs[:, d])[0]
        if len(idx):
            md.AddBoolXOr([v[i] for i in idx] + [one])
    obs = []
    for o in range(nd, sigs.shape[1]):
        idx = np.nonzero(sigs[:, o])[0]
        b = md.NewBoolVar(f"o{o}")
        md.AddBoolXOr([v[i] for i in idx] + [b.Not()])
        obs.append(b)
    md.AddBoolOr(obs)
    s = cp_model.CpSolver(); s.parameters.max_time_in_seconds = time_limit; s.parameters.num_workers = 1
    st = s.Solve(md)
    out = {"weight": ng, "status": s.StatusName(st), "candidates": len(cand)}
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        chosen = [cand[i][1][0] for i in range(len(cand)) if s.Value(v[i])]
        # independent re-check by direct injection of all chosen faults together
        sig, _ = signature(base, chosen)
        out.update(feasible=True, faults=[[int(t), P, int(q)] for t, P, q in chosen],
                   detectors_fired=int(sig[:nd].sum()), observables_flipped=int(sig[nd:].sum()))
        assert out["detectors_fired"] == 0 and out["observables_flipped"] > 0
    else:
        out["feasible"] = False
    return out
