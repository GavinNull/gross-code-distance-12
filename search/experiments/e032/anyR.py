"""E-028 (port of e021/anyR.py to [[90,8,10]], 72 -> 45 checks): premises of the any-R argument for a non-wrapping frame candidate (audit 2026-10-05 B7 style).

Argument (my adaptation of B7 to cand1; d_circ >= d_ext = 11 for every R by Prop. 3 + Table I):
 (S) Separation: in the unrolled circuit every CNOT of round j precedes every CNOT of round j+1, and between the
     last CNOT of round j and the first of round j+1 all ancillas of round j are measured.  Then the B7 split lemma
     holds verbatim: a weight-11 undetected logical F with an empty round r strictly inside its round span splits
     into two undetected parts, one of which is a logical with < 11 faults -- impossible.  So F spans <= 11
     consecutive rounds.
 (T) Time periodicity: the noisy (R+1)-round circuit equals the R-round circuit with one fixed instruction block
     inserted at a fixed position (DETECTOR coordinates ignored).  Then F (span <= 11 rounds) can be moved to a
     circuit with <= 11 + 2 = 13 rounds keeping one fault-free round on each interior side, with identical detector
     and observable effect.
 (L) Exact lift (lift21) for R = 1..13, both bases: 0 lifting  =>  d_circ >= 12 for every R.
This script checks (S) on unroll() for R = 2..6 and (T) on the flattened noisy circuits for R = 2..14.

    PYTHONPATH=.:tests uv run python -m search.experiments.e032.anyR search/experiments/e028/c16_spec.json
"""
import json
import sys

from evaluators.candidate import build_circuits, parse_schedule, unroll
from evaluators.noise import add_noise
from search.experiments.e032.common import css


def separation(spec, R):
    U = unroll(spec, css(), R)
    D = spec.period
    rnd = {}
    for q, s in U.start.items():
        for j in range(R):
            rnd[(q, s + D * j)] = j
    lo, hi, mlo, mhi = {}, {}, {}, {}
    for t, lst in U.cnots.items():
        for c, tg in lst:
            anc = c if c in U.start else tg
            # round of this CNOT: instance whose window contains t
            s0 = U.start[anc]
            j = (t - s0) // D
            lo[j] = min(lo.get(j, 10 ** 9), t); hi[j] = max(hi.get(j, -1), t)
    for t, lst in U.meas.items():
        for q, typ, j in lst:
            mlo[j] = min(mlo.get(j, 10 ** 9), t); mhi[j] = max(mhi.get(j, -1), t)
    ok = all(hi[j] < lo[j + 1] and mhi[j] < lo[j + 1] and mlo[j] > hi[j] for j in range(R - 1))
    return ok, [(lo[j], hi[j], mlo[j], mhi[j]) for j in range(R)]


MEAS = ("M", "MX", "MR", "MRX", "MZ", "MY")


def parse(circ):
    """(segments of non-annotation ops [sorted per TICK segment], measurement count per segment,
    detectors as frozensets of absolute measurement indices, observables likewise)."""
    segs, cnt, seg, c = [], [], [], 0
    dets, obs = [], {}
    nm = 0
    for op in circ.flattened():
        if op.name == "TICK":
            segs.append(tuple(sorted(seg))); cnt.append(c); seg, c = [], 0; continue
        if op.name in ("SHIFT_COORDS", "QUBIT_COORDS"):
            continue
        if op.name == "DETECTOR":
            dets.append(frozenset(nm + t.value for t in op.targets_copy())); continue
        if op.name == "OBSERVABLE_INCLUDE":
            k = int(op.gate_args_copy()[0])
            obs[k] = obs.get(k, frozenset()) ^ frozenset(nm + t.value for t in op.targets_copy()); continue
        if op.name in MEAS:
            nm += len(op.targets_copy()); c += len(op.targets_copy())
        seg.append((op.name, tuple(str(t) for t in op.targets_copy()), tuple(op.gate_args_copy())))
    segs.append(tuple(sorted(seg))); cnt.append(c)
    return segs, cnt, set(dets), obs


def periodicity(spec, basis, Rmax):
    """for R = 2..Rmax-1: circuit(R+1) = circuit(R) with one block of TICK segments inserted at the same segment
    index; the block is the same every time; detectors/observables of R map to those of R+1 by the measurement
    index shift; the new detectors are the +mb translates of the preceding round's comparison detectors."""
    c = css()
    get = lambda R: parse(add_noise(build_circuits(spec, c, R)[basis], "sd6", 1e-3))  # noqa: E731
    prev = get(3)
    blocks, pos = set(), set()
    for R in range(4, Rmax + 1):
        cur = get(R)
        a, b = prev[0], cur[0]
        L = len(b) - len(a)
        ok_i = None
        okall = []
        for i in range(0, len(a) + 1):
            if not (b[:i] == a[:i] and b[i + L:] == a[i:]):
                continue
            ins_m = sum(prev[1][:i]); mb = sum(cur[1][i:i + L])
            # a detector reaching past the insertion point compares its later round with the round before it, which
            # after insertion is the inserted round: shift every index >= ins_m - mb (one round back) in that case
            sh = lambda d: frozenset(x + mb if (max(d) >= ins_m and x >= ins_m - mb) else x for x in d)  # noqa: E731
            Dp, Dc = prev[2], cur[2]
            shifted = {sh(d) for d in Dp}
            if not shifted <= Dc:
                continue
            new = Dc - shifted
            ref = {frozenset(x + mb for x in d) for d in Dc
                   if d and min(d) >= ins_m - 2 * mb and max(d) < ins_m and any(x >= ins_m - mb for x in d)}
            if new != ref or len(new) != 45:
                continue
            if {k: sh(v) for k, v in prev[3].items()} != cur[3]:
                continue
            ok_i = i if ok_i is None else ok_i
            okall.append(i)
            blocks.add(tuple(b[i:i + L]))
        pos.add((R, tuple(okall)))
        if ok_i is None:
            return False, f"no valid block insertion at R={R}"
        prev = cur
    # valid insertion segment ranges per R (inserted round index = position // P)
    return True, {R: (min(v) , max(v)) for R, v in sorted(pos)}


def main():
    spec = parse_schedule(json.load(open(sys.argv[1]))).canonical()
    res = {}
    for R in (2, 3, 6):
        ok, iv = separation(spec, R)
        print("separation R", R, ok, iv[:3], flush=True)
        res[f"sep_R{R}"] = ok
    for b in "ZX":
        r = periodicity(spec, b, 14)
        print("periodicity", b, r, flush=True)
        res[f"per_{b}"] = r[0]
    print(json.dumps(res))


if __name__ == "__main__":
    main()
