"""[[90,8,10]], circuit c16: machine check of the premises of the any-R reduction (every R reduces to R <= 12).

(S) Separation.  In the unrolled circuit every check instance of round j is reset in layer 16j, applies its CNOTs in
    layers 16j+1..16j+12 and is measured in layer 16j+15; the data are reset in layer 0 and read out in layer 16R.
    So round j occupies the block of layers 16j..16j+15 (checked on the unrolled circuits, R = 1..14).
(T) Periodicity.  For R = 4..14 and both bases, the noisy SD6 circuit with R rounds equals the one with R - 1 rounds
    with one fixed block of TICK segments (one round) inserted, at every segment position from 32 (after block 1) to
    16 (R - 1) (up to the end of the last block, before the readout); the block inserted after block 1 is the same
    for every R; detectors and observables map accordingly, the new detectors being the
    translates of the previous round's comparison detectors.
Pen-and-paper part (stated here, used by the README):
  split lemma: if an undetected logical F has an empty block strictly inside the span of its faults, the faults
  before the empty block form an undetected set F1 (they leave only a data error at the end of the block, which
  every later round measures identically and the readout confirms), F2 = F \\ F1 is undetected by linearity, and one
  of F1, F2 flips an observable.  For a minimum-weight undetected logical F of weight w this contradicts minimality,
  so F spans at most w consecutive blocks.  With (T) the blocks after block 1 and before the last one that F does not
  touch can be deleted: F becomes an undetected logical of the same weight with R' <= w + 3 rounds.  For w <= 9:
  R' <= 12, which is covered by code/bb90/lift.py (R = 1..12) and by the direct DEM search (code/dcirc/).

    python code/bb90/premises.py --rmax 14
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common_cli import Verdict                                   # noqa: E402
from bb90 import bbcode, ext as E                                # noqa: E402
from gross12.noise import add_sd6                                # noqa: E402
from gross12.schedule import build_circuits, layout_for, unroll  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--circuit", default="c16")
ap.add_argument("--rmax", type=int, default=14)
a = ap.parse_args()
code = bbcode.load_code()
spec = E.circuit(a.circuit).canonical()
D = spec.period
lay = layout_for(code)
V = Verdict()

# (S) ------------------------------------------------------------------------------------------------------------
bad = []
for R in range(1, a.rmax + 1):
    U = unroll(spec, code, R)
    if U.num_layers != D * R:
        bad.append((R, "layers", U.num_layers))
    for t, lst in U.preps.items():
        if t % D != 0:
            bad.append((R, "reset", t))
    for t, lst in U.meas.items():
        for q, typ, j in lst:
            if t != D * j + D - 1:
                bad.append((R, "meas", q, j, t))
    for t, lst in U.cnots.items():
        for c, tg in lst:
            anc = c if c >= lay.n else tg
            j = (t - U.start[anc]) // D
            if not (D * j < t < D * j + D - 1):
                bad.append((R, "cnot", t))
    if any(s != 0 for s in U.start.values()):
        bad.append((R, "start"))
V(not bad, f"[{a.circuit}] (S) separation, R = 1..{a.rmax}: round j occupies layers {D}j..{D}j+{D - 1} (resets in "
           f"its first layer, CNOTs strictly inside, measurements in its last layer), data reset in layer 0, "
           f"readout after the last block ({len(bad)} violations)")

# (T) ------------------------------------------------------------------------------------------------------------
MEAS = ("M", "MX")


def parse(circ):
    """(TICK segments as sorted tuples of non-annotation instructions, measurements per segment,
    detectors as frozensets of absolute measurement indices, observables likewise)."""
    segs, cnt, seg, c = [], [], [], 0
    dets, obs = [], {}
    nm = 0
    for op in circ.flattened():
        if op.name == "TICK":
            segs.append(tuple(sorted(seg))); cnt.append(c); seg, c = [], 0
            continue
        if op.name in ("SHIFT_COORDS", "QUBIT_COORDS"):
            continue
        if op.name == "DETECTOR":
            dets.append(frozenset(nm + t.value for t in op.targets_copy()))
            continue
        if op.name == "OBSERVABLE_INCLUDE":
            k = int(op.gate_args_copy()[0])
            obs[k] = obs.get(k, frozenset()) ^ frozenset(nm + t.value for t in op.targets_copy())
            continue
        if op.name in MEAS:
            nm += len(op.targets_copy()); c += len(op.targets_copy())
        seg.append((op.name, tuple(str(t) for t in op.targets_copy()), tuple(op.gate_args_copy())))
    segs.append(tuple(sorted(seg))); cnt.append(c)
    return segs, cnt, set(dets), obs


def periodicity(basis, rmax):
    get = lambda R: parse(add_sd6(build_circuits(spec, code, R)[basis]))  # noqa: E731
    prev = get(3)
    blocks, ranges = set(), {}
    for R in range(4, rmax + 1):
        cur = get(R)
        sa, sb = prev[0], cur[0]
        Lb = len(sb) - len(sa)
        okpos = []
        for i in range(0, len(sa) + 1):
            if not (sb[:i] == sa[:i] and sb[i + Lb:] == sa[i:]):
                continue
            ins_m = sum(prev[1][:i]); mb = sum(cur[1][i:i + Lb])
            sh = lambda d: frozenset(x + mb if (max(d) >= ins_m and x >= ins_m - mb) else x for x in d)  # noqa: E731
            shifted = {sh(d) for d in prev[2]}
            if not shifted <= cur[2]:
                continue
            new = cur[2] - shifted
            ref = {frozenset(x + mb for x in d) for d in cur[2]
                   if d and min(d) >= ins_m - 2 * mb and max(d) < ins_m and any(x >= ins_m - mb for x in d)}
            if new != ref or len(new) != 45:
                continue
            if {k: sh(v) for k, v in prev[3].items()} != cur[3]:
                continue
            okpos.append(i)
            if i == 2 * D:
                blocks.add(tuple(sb[i:i + Lb]))
        if not okpos:
            return False, R, ranges, len(blocks)
        ranges[R] = (min(okpos), max(okpos), len(okpos), Lb)
        prev = cur
    return True, None, ranges, len(blocks)


for basis in "ZX":
    ok, badR, ranges, nblocks = periodicity(basis, a.rmax)
    full = ok and all(lo == 2 * D and hi == D * (R - 1) and n == hi - lo + 1 and Lb == D
                      for R, (lo, hi, n, Lb) in ranges.items())
    V(full and nblocks == 1,
      f"[{a.circuit}] (T) periodicity, {basis} basis, R = 4..{a.rmax}: circuit(R) = circuit(R-1) with one "
      f"{D}-segment block inserted, valid at every segment position {2 * D}..{D}(R-1) (after block 1, up to the end of "
      f"the last block), the block inserted at position {2 * D} identical for all R, detectors and observables mapped "
      f"({'first failure at R=' + str(badR) if not ok else str(nblocks) + ' distinct block(s) at position ' + str(2 * D)})")
V(True, f"[{a.circuit}] reduction: a minimum-weight undetected logical of weight w <= 9 spans <= w blocks (split lemma "
        f"with (S)); deleting untouched blocks (T) gives R' <= w + 3 <= 12; lift.py and the direct DEM search cover "
        f"R = 1..12")
V.exit()
