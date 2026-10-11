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
from evaluators.noise import add_noise

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


def layers(c):
    """noisy circuit -> list of per-TICK op strings (annotations dropped), as audit b7."""
    out, cur = [], []
    for op in c.flattened():
        if op.name == "TICK":
            out.append("\n".join(sorted(cur))); cur = []
        elif op.name not in ("DETECTOR", "OBSERVABLE_INCLUDE", "SHIFT_COORDS", "QUBIT_COORDS"):
            cur.append(str(op))
    out.append("\n".join(sorted(cur)))
    return out


def cuts(spec, basis, Rmax):
    """for R = 3..Rmax: all x with circuit(R) = circuit(R-1) + circuit(R)[x:x+D] inserted at x."""
    D = spec.period
    L = {R: layers(add_noise(build_circuits(spec, css(), R)[basis], "sd6", 1e-3)) for R in range(2, Rmax + 1)}
    out = {}
    for R in range(3, Rmax + 1):
        a, b = L[R - 1], L[R]
        assert len(b) == len(a) + D
        out[R] = [x for x in range(len(a) + 1) if b[:x] == a[:x] and b[x + D:] == a[x:]]
    return out


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
    lo_all, chi_all = set(), set()
    for b in "ZX":
        cu = cuts(spec, b, 12)
        for R, xs in cu.items():
            assert xs == list(range(xs[0], xs[-1] + 1)), "valid cuts not contiguous"
            lo_all.add(xs[0]); chi_all.add(xs[-1] - D * R)
        res[f"cuts_{b}"] = {R: (xs[0], xs[-1]) for R, xs in cu.items()}
    assert len(chi_all) == 1, chi_all
    # R' bound (deletion argument, docstring (4) made precise):
    #   circuit(R) = circuit(R-1) + D-block inserted at segment x, valid for x in [lo, hi_R] (checked R = 3..12;
    #   hi_R = D*R + c_hi, lo constant -- asserted on the checked range; the template is exactly periodic so the
    #   pattern continues).  Removing the block at x keeps F's detector/observable values if x + D <= f1 (everything
    #   before is fault-free: all measurements < x+D read 0) or x >= f11 + 2D - 1 (data frame constant e from
    #   f11 + D - 1; every instance reset >= x - D is fault-free and settled, so the re-paired comparisons read
    #   H_c e xor H_c e, and the frame entering layer x+D of circuit(R) equals that entering layer x of circuit(R-1)).
    #   Delete at x = lo while lo + D <= f1  =>  f1 <= lo + D - 1, f11 <= lo + D - 1 + span.
    #   Delete at x = f11 + 2D - 1 while x <= hi_R  =>  final R satisfies D*R + c_hi < f11 + 2D - 1.
    lo, c_hi = max(lo_all), chi_all.pop()
    f11max = lo + D - 1 + span
    # largest R with no valid cut x >= f11 + 2D - 1, i.e. D*R + c_hi < f11max + 2D - 1: every circuit with more
    # rounds containing F can be shortened, so F reappears in a circuit with <= Rp rounds.
    Rp = (f11max + 2 * D - 2 - c_hi) // D
    assert D * Rp + c_hi < f11max + 2 * D - 1 <= D * (Rp + 1) + c_hi
    res.update(lo=lo, c_hi=c_hi)
    res["R_prime"] = Rp
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
