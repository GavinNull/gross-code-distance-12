"""Prop. 3 key step (Strikis 2603.05481 Table I), checked computationally on evaluator memory circuits
(adapted from research/audits/2026-10-05-E-013-scripts/s7_table1.py, generalised to any schedule / code):
every single SD6 fault mechanism, Pauli-frame propagated to the end, has a data X (Z) part whose [H; L] vector is
0 or exactly one column of the X- (Z-) type extended code built from the schedule's per-check CNOT orders.
"""
from __future__ import annotations

import numpy as np

from evaluators.candidate import build_circuits, parse_schedule
from evaluators.noise import add_noise
from search.noninterleaved.ext import extended_matrices, orders_from_schedule, residual_supports

NOISE = {"DEPOLARIZE1", "DEPOLARIZE2", "X_ERROR", "Z_ERROR", "Y_ERROR"}


def table1_check(sched, css, R=3):
    """css: evaluator CSSCode whose HX/HZ row/column order matches `sched` (check before calling)."""
    import sys
    sys.path.insert(0, "tests")
    from schedule_helpers import from_baseline
    spec = parse_schedule(from_baseline(sched)).canonical()
    xo, zo = orders_from_schedule(sched)
    n = css.n
    cols = {}
    for kind, H, L, orders in (("X", css.HZ, css.LZ, xo), ("Z", css.HX, css.LX, zo)):
        He, Le, _ = extended_matrices(H, L, [s for o in orders for s in residual_supports(o)])
        S = {He[:, j].tobytes() + Le[:, j].tobytes() for j in range(He.shape[1])}
        cols[kind] = (S, np.asarray(H, np.int64), np.asarray(L, np.int64), set())
    out = {}
    for basis in "ZX":
        circ = add_noise(build_circuits(spec, css, R)[basis], "sd6", 1e-3).flattened()
        nq = circ.num_qubits
        ops = []
        for inst in circ:
            if inst.name == "TICK":
                continue
            ops.append((inst.name, [q.value for q in inst.targets_copy() if q.is_qubit_target]))

        def propagate(start, qubit, which):
            x = np.zeros(nq, bool); z = np.zeros(nq, bool)
            (x if which == "X" else z)[qubit] = True
            for name, t in ops[start:]:
                if name in ("CX", "CNOT"):
                    c = np.array(t[0::2]); g = np.array(t[1::2])
                    x[g] ^= x[c]; z[c] ^= z[g]
                elif name in ("R", "RX", "RZ"):
                    x[t] = False; z[t] = False
                elif name in NOISE or name.startswith("M") or name in ("DETECTOR", "OBSERVABLE_INCLUDE"):
                    pass
                else:
                    raise ValueError(name)
            return x[:n].copy(), z[:n].copy()
        bad = {"X": 0, "Z": 0}; total = 0
        for k in "XZ":
            cols[k][3].clear()
        for i, (name, t) in enumerate(ops):
            if name not in NOISE:
                continue
            groups = [t[k:k + 2] for k in range(0, len(t), 2)] if name == "DEPOLARIZE2" else [[q] for q in t]
            for grp in groups:
                for kind in "XZ":
                    effs = [propagate(i + 1, q, kind)[0 if kind == "X" else 1] for q in grp]
                    combos = effs + ([effs[0] ^ effs[1]] if len(effs) == 2 else [])
                    S, H, L, used = cols[kind]
                    for v in combos:
                        total += 1
                        hv = (H @ v) % 2; lv = (L @ v) % 2
                        if not hv.any() and not lv.any():
                            continue
                        key = hv.astype(np.uint8).tobytes() + lv.astype(np.uint8).tobytes()
                        if key in S:
                            used.add(key)
                        else:
                            bad[kind] += 1
        out[basis] = {"rounds": R, "fault_parts": total, "not_a_column": bad,
                      "columns_used": {k: f"{len(cols[k][3])}/{len(cols[k][0])}" for k in "XZ"}}
    return out
