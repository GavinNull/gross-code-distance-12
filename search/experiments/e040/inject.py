"""E-040: physical check of a bulk witness: insert its faults as deterministic Pauli errors (X_ERROR(1) for sector X /
Z-basis memory, Z_ERROR(1) for sector Z / X-basis memory) into the NOISELESS evaluator memory circuit
(evaluators.candidate.memory_circuit) of the schedule, in the interior, and require: no detection event, at least one
observable flipped.  Independent of bulk.py's detector arithmetic (stim does the propagation).

Fault placement (my time tau -> circuit layer tau + c, c fixed by the evaluator's unrolling):
  ('d', q, b, r): after the layer of the read of q by reader label b in round r (data qubit q);
  ('h', c, S, j): after the layer of the hook-side CNOT preceding S in instance j (ancilla of check c);
  ('m', c, r):    after the last CNOT of reader check c in round r (ancilla, i.e. just before its measurement).
"""
from __future__ import annotations

import numpy as np
import stim

from evaluators.candidate import layout_for, memory_circuit, parse_schedule, unroll
from search.experiments.e040.bulk import Sector, spec_of
from search.experiments.e040.codes import MOD


def check(code, kind, tX, tZ, P, faults, margin=2):
    C = MOD[code]
    cobj = C.css()
    S = Sector(code, kind, tX, tZ, P)
    spec = parse_schedule(spec_of(code, tX, tZ, P))
    basis = "Z" if kind == "X" else "X"
    lay = layout_for(cobj)
    T = C.table()
    anc = {"X": lay.x_anc, "Z": lay.z_anc}
    hk, rk = ("X", "Z") if kind == "X" else ("Z", "X")
    tH, tR = S.tH, S.tR

    def ev_time(ty, t_my):
        return t_my

    # my time of every fault event
    ev = []
    for f in faults:
        f = tuple(frozenset(x) if isinstance(x, list) else x for x in f)
        if f[0] == "d":
            _, q, b, r = f
            ev.append(("data", q, tR[b] + r * P))
        elif f[0] == "h":
            _, c, Sx, j = f
            o = S.order
            k = min(o.index(m) for m in Sx)
            prev = o[k - 1]
            ev.append(("anc", anc[hk][c], tH[prev] + j * P))
        else:
            _, c, r = f
            ev.append(("anc", anc[rk][c], max(tR) + r * P))
    tmin = min(e[2] for e in ev)
    tmax = max(e[2] for e in ev)
    R = (tmax - tmin) // P + 2 * margin + 3
    U = unroll(spec, cobj, R)
    # offset c: evaluator layer of hook-side instance-0 CNOT of label m on check 0 minus tH[m]
    D = spec.period
    cH = spec.x_checks[0] if hk == "X" else spec.z_checks[0]
    cR = spec.z_checks[0] if hk == "X" else spec.x_checks[0]
    _, offH = cH.offsets(D)
    _, offR = cR.offsets(D)
    colH = {col: o for o, col in offH}
    colR = {col: o for o, col in offR}
    m0 = 0
    LH = U.start[anc[hk][0]] + colH[int(T[hk][0][m0])]
    cc = (LH - tH[m0]) % P
    b0 = 0
    LR = U.start[anc[rk][0]] + colR[int(T[rk][0][b0])]
    assert (LR - tR[b0]) % P == cc, "inconsistent layer offset"
    # shift: place tmin at layer >= margin rounds after both starts
    base = max(U.start.values()) + margin * P
    K = (base - (tmin + cc)) // P + 1
    c = cc + K * P
    layers = [[] for _ in range(U.num_layers + 1)]
    for kindq, q, t in ev:
        L = t + c
        assert 1 <= L < U.num_layers - margin * P, (L, U.num_layers)
        layers[L].append(q)
    circ = memory_circuit(spec, cobj, basis, R)
    out = stim.Circuit()
    layer = 0
    gate = "X_ERROR" if kind == "X" else "Z_ERROR"
    for inst in circ:
        if inst.name == "TICK":
            qs = layers[layer] if layer < len(layers) else []
            # an even number of insertions on one qubit at one layer cancels
            odd = [q for q in sorted(set(qs)) if qs.count(q) % 2]
            if odd:
                out.append(gate, odd, 1.0)
            out.append("TICK")
            layer += 1
        else:
            out.append(inst)
    det, obs = out.compile_detector_sampler().sample(1, separate_observables=True)
    return (not det.any()) and bool(obs.any()), int(det.sum()), int(obs.sum()), R
