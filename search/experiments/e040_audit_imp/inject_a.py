"""E-040 impossibility audit (independent code): physical check of a bulk fault pattern with stim.

Builds the evaluator's NOISELESS memory circuit (public entry evaluators.candidate.memory_circuit) for the T(P)
schedule (tX, tZ), parses it (layers = TICK-separated; CX pairs; measurements), identifies each ancilla's check by its
data support, recovers the global layer offset (asserted consistent for every CX), and inserts every fault as an
X_ERROR(1) / Z_ERROR(1) (noise, so stim's reference sample is the noiseless one) after the layer of
   data ('d', q, b, r): the CX reading q by reader label b in instance r   (asserted to exist)
   hook ('h', c, S, j): the CX of check c on the label just before S in instance j (asserted to exist)
   meas ('m', c, r):    the last CX of reader check c in instance r (asserted; the measurement follows)
Returns (#fired detectors, observables flipped, model detector set == stim detector set mapped to (check, instance)).
"""
import numpy as np
import stim

from evaluators.candidate import memory_circuit, parse_schedule

from search.experiments.e040_audit_imp.bulk_a import dets_one


def spec(C, tX, tZ, P):
    T = C["T"]
    out = {"format": "qec-schedule/v1", "period": P, "x_checks": [], "z_checks": []}
    for ty, t, key in (("X", tX, "x_checks"), ("Z", tZ, "z_checks")):
        for i in range(C["N2"]):
            out[key].append({"prep": int((min(t) - 1) % P), "meas": int((max(t) + 1) % P),
                             "cnots": [[int(T[ty][i][k]), int(t[k] % P)] for k in range(6)]})
    return out


def parse(circ, C):
    n = C["NQ"]
    layer = 0
    cx, meas = [], []
    for ins in circ:
        if ins.name == "TICK":
            layer += 1
        elif ins.name == "CX":
            ts = [t.value for t in ins.targets_copy()]
            for a, b in zip(ts[0::2], ts[1::2]):
                cx.append((layer, a, b))
        elif ins.name in ("M", "MX"):
            for t in ins.targets_copy():
                if t.value >= n:
                    meas.append((layer, t.value))
    return cx, meas, layer


def build(C, tX, tZ, P, basis, R):
    sp = parse_schedule(spec(C, tX, tZ, P))
    circ = memory_circuit(sp, C["css"], basis, R)
    cx, meas, nl = parse(circ, C)
    n = C["NQ"]
    supp = {}
    for L, a, b in cx:
        anc, dq, ty = (a, b, "X") if a >= n else (b, a, "Z")
        supp.setdefault(anc, (ty, set()))[1].add(dq)
    rowof = {ty: {frozenset(int(v) for v in C["T"][ty][i]): i for i in range(C["N2"])} for ty in "XZ"}
    anc_of = {"X": {}, "Z": {}}
    check_of = {}
    for anc, (ty, s) in supp.items():
        i = rowof[ty][frozenset(s)]
        anc_of[ty][i] = anc
        check_of[anc] = (ty, i)
    t = {"X": tX, "Z": tZ}
    offs = set()
    cxset = set()
    for L, a, b in cx:
        anc, dq = (a, b) if a >= n else (b, a)
        ty, i = check_of[anc]
        lab = list(C["T"][ty][i]).index(dq)
        offs.add((L - t[ty][lab]) % P)
        cxset.add((anc, dq, L))
    assert len(offs) == 1, offs
    return circ, anc_of, check_of, offs.pop(), cxset, meas, nl


def check(C, sector, tX, tZ, P, faults, margin=3, compare_model=True):
    basis = "Z" if sector == "X" else "X"
    hk, rk = ("X", "Z") if sector == "X" else ("Z", "X")
    tH, tR = (tX, tZ) if sector == "X" else (tZ, tX)
    T = C["T"]
    # bulk times of the events
    ev = []
    for f in faults:
        if f[0] == "d":
            _, q, b, r = f
            c2 = [c for c in range(C["N2"]) if T[rk][c][b] == q][0]
            ev.append(("d", q, rk, c2, b, tR[b] + r * P))
        elif f[0] == "h":
            _, c, S, j = f
            rest = [m for m in range(6) if m not in S]
            p = max(rest, key=lambda m: tH[m])
            assert min(tH[m] for m in S) > tH[p]
            ev.append(("a", None, hk, c, p, tH[p] + j * P))
        else:
            _, c2, r = f
            p = max(range(6), key=lambda m: tR[m])
            ev.append(("a", None, rk, c2, p, tR[p] + r * P))
    tmin, tmax = min(e[5] for e in ev), max(e[5] for e in ev)
    R = (tmax - tmin) // P + 2 * margin + 4
    circ, anc_of, check_of, off, cxset, meas, nl = build(C, tX, tZ, P, basis, R)
    # choose shift K*P so that the earliest event is >= margin rounds after layer P+1 (all ancillas started)
    K = -((tmin + off - (margin + 2) * P) // P)
    sh = off + K * P
    ins = {}
    for kind, q, ty, c, lab, tb in ev:
        L = tb + sh
        anc = anc_of[ty][c]
        dq = int(T[ty][c][lab])
        assert (anc, dq, L) in cxset, ("missing CX", kind, ty, c, lab, L)
        assert L < nl - margin * P
        tgt = q if kind == "d" else anc
        ins.setdefault(L, []).append(tgt)
    gate = "X_ERROR" if sector == "X" else "Z_ERROR"
    out = stim.Circuit()
    layer = 0
    for inst in circ:
        if inst.name == "TICK":
            qs = ins.get(layer, [])
            odd = sorted(q for q in set(qs) if qs.count(q) % 2)
            if odd:
                out.append(gate, odd, 1.0)
            layer += 1
        out.append(inst)
    det, obs = out.compile_detector_sampler().sample(1, separate_observables=True)
    fired = set(np.flatnonzero(det[0]).tolist())
    same = None
    if compare_model:
        # map stim detector (coords i, j) -> model (check i, instance s); instance from the measurement layer
        coords = out.get_detector_coordinates()
        mlay = {}
        for L, a in meas:
            mlay.setdefault(a, []).append(L)
        mx = max(tR)
        stim_set = set()
        for d in fired:
            i, j = int(coords[d][0]), int(coords[d][1])
            a = anc_of[rk][i]
            if j >= len(mlay[a]):
                stim_set.add(("final", i))
                continue
            Lm = mlay[a][j]
            s = (Lm - 1 - sh - mx)
            assert s % P == 0
            stim_set.add((i, s // P))
        model = dets_one(C, sector, faults, tH, tR, P)
        same = stim_set == model
    return len(fired), bool(obs.any()), same
