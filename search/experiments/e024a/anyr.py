"""E-024a: premises and the finite R' of the any-R argument for PIPELINED (wrapping) schedules.

Argument (mine; adapts audit 2026-10-10 E-021 §6 / E-015 B7, whose "empty round" needs strict round separation,
which wrapping schedules do not have).  Notation from the evaluator template (unroll): period D, check q has start
s_q (R-independent: the global shift sigma minimises max_q(s_q + dm_q) + D(R-1), whose argmin does not depend on R),
instance j resets at s_q + jD, CNOTs at s_q + jD + off, measures at s_q + jD + dm_q (dm_q <= D-1); data readout at
the final layer END.  Detectors: (c,0) = m(c,0); (c,j) = m(c,j) xor m(c,j-1); (c,R) = H_c.readout xor m(c,R-1).
Faults are attached to a layer (gate/reset/idle faults act after that layer's ops; measurement flips act on that
layer's measurement).
 (1) No weight <= 10 at any R (Table I + telescoping + d_ext = 11; asserted at every computed R).
 (2) Settling: if all faults of F_< are at layers <= a, the data frame is constant (= e) from layer a+D-1 on (only an
     ancilla fault can later change data, through its own instance's remaining CNOTs, all <= a+D-2; fresh ancillas
     never push errors onto data: an X-check ancilla only picks up Z from data, a Z-check ancilla only X); an instance
     reset at r >= a+D-1 is fault-free and measures H_c e.
     If all faults of F_> are at layers >= b, measurements at layers < b are unaffected.
 (3) Split: if b - a >= G := max(2D + dm_max - 1, D + S + dm_max), S = max_q s_q - min_q s_q, then the syndromes of F_<
     and F_> have disjoint supports (comparison (c,j): F_< needs s(c,j-1) < a+D-1, F_> needs meas(c,j) >= b, but
     meas(c,j) = s(c,j-1) + D + dm_c <= a + 2D + dm_max - 2; first-round analogous; final (c,R): F_< needs
     s(c,R-1) < a+D-1, but b <= END <= s(c,R-1) + S + dm_max + 1 <= a + D + S + dm_max - 1), so both are undetected and
     one is a logical with < 11 faults, contradicting (1).  Hence a weight-11 undetected logical has all consecutive
     fault-layer gaps <= G-1, span <= 10(G-1).
 (4) Translation: the noisy circuit is D-periodic in the bulk; a D-layer block [x, x+D) at a valid cut can be removed
     without changing any detector/observable value of F if all instances reset in [x-D, x+D) measure 0 (x+2D <= first
     fault layer) or are all settled (x - D >= last fault layer + D - 1): the re-paired comparison detectors compare
     two zeros / two H_c e.  So F is reproduced in a circuit with R' <= B0 + ceil((10(G-1) + margins)/D) + B1 rounds.
This script checks the structural premises (starts R-independent, dm <= D-1, detector structure by parsing the
circuit, periodicity via e021.anyR.periodicity) and prints G and the resulting R'.

    PYTHONPATH=.:tests uv run python -m search.experiments.e024a.anyr SPEC.json
"""
import json
import math
import sys

from evaluators.candidate import build_circuits, layout_for, parse_schedule, unroll
from search.experiments.e018.common import css
from search.experiments.e021.anyR import periodicity

MEAS = ("M", "MX", "MR", "MRX", "MZ")


def structure(spec, R):
    c = css()
    U = unroll(spec, c, R)
    D = spec.period
    lay = layout_for(c)
    dm = {}
    for t, lst in U.meas.items():
        for q, typ, j in lst:
            assert t == U.start[q] + D * j + (dm.setdefault(q, t - U.start[q] - D * j))
    assert all(0 < v <= D - 1 for v in dm.values())
    for t, lst in U.preps.items():
        for q, typ in lst:
            assert (t - U.start[q]) % D == 0 and 0 <= (t - U.start[q]) // D < R
    # detectors by parsing (absolute measurement index -> (qubit, k-th measurement of that qubit))
    out = {}
    for basis in "ZX":
        circ = build_circuits(spec, c, R)[basis]
        meas_of, cnt, nm, dets = [], {}, 0, []
        for op in circ.flattened():
            if op.name in MEAS:
                for tg in op.targets_copy():
                    k = cnt.get(tg.value, 0); cnt[tg.value] = k + 1
                    meas_of.append((tg.value, k)); nm += 1
            elif op.name == "DETECTOR":
                dets.append((frozenset(meas_of[nm + t.value] for t in op.targets_copy()) if False else
                             frozenset(nm + t.value for t in op.targets_copy()), tuple(op.gate_args_copy())))
        anc = lay.z_anc if basis == "Z" else lay.x_anc
        H = (c.HZ if basis == "Z" else c.HX)
        import numpy as np
        want = set()
        for i, q in enumerate(anc):
            want.add(frozenset({(q, 0)}))
            for j in range(1, R):
                want.add(frozenset({(q, j), (q, j - 1)}))
            want.add(frozenset({(int(d), 0) for d in np.flatnonzero(np.asarray(H[i]) % 2)} | {(q, R - 1)}))
        got = {frozenset(meas_of[x] for x in d) for d, _ in dets}
        out[basis] = (got == want and len(dets) == len(want))
    return U, dm, out


def main():
    spec = parse_schedule(json.load(open(sys.argv[1]))).canonical()
    D = spec.period
    starts = None
    res = {"spec": sys.argv[1], "D": D}
    for R in (2, 3, 5, 9):
        U, dm, det_ok = structure(spec, R)
        if starts is None:
            starts = dict(U.start)
        assert U.start == starts, "starts depend on R"
        res[f"det_structure_R{R}"] = det_ok
    S = max(starts.values()) - min(starts.values())
    dmax = max(dm.values())
    G = max(2 * D + dmax - 1, D + S + dmax)
    span = 10 * (G - 1)
    res.update(S=S, dm_max=dmax, min_start=min(starts.values()), G=G, span_max=span)
    per = {}
    for b in "ZX":
        ok, iv = periodicity(spec, b, 12)
        per[b] = ok
        res[f"periodic_{b}"] = ok
        res[f"insert_ranges_{b}"] = iv if ok else str(iv)
    # R' bound: rounds touched by [first fault - 3D, last fault + 3D] plus boundary rounds (first 2, last 2 rounds
    # are never removed): conservative.
    Rp = 2 + math.ceil((span + 6 * D) / D) + 2
    res["R_prime"] = Rp
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
