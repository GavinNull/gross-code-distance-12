"""E-018 stage c: time-shift interleavings of Fig. 12 (Strikis Theorem 1 family).

Every Fig. 12 check occupies a full window of 8 consecutive steps (prep, 6 CNOTs, meas) in period 8, so with period 8
and the per-check CNOT orders fixed, a candidate is exactly a start-time shift delta_c in Z_8 per check (144 checks);
all times of check c move by delta_c.  Legal iff no data qubit has two CNOTs at the same step (mod 8); determinism is
decided by stim (non-deterministic detectors raise when the DEM is built) and by the evaluator's screen.

Colour-uniform family: delta depends only on (type, colour) -> 6 parameters; preserves the 24-element symmetry.
"""
from __future__ import annotations

import itertools
import json

import numpy as np

from evaluators.candidate import CheckTiming, ScheduleSpec, parse_schedule
from search.experiments.e018.common import fig12

D = 8


def base():
    import sys
    sys.path.insert(0, "tests")
    from schedule_helpers import from_baseline
    sched, meta = fig12()
    spec = parse_schedule(from_baseline(sched))
    cc = meta["check_colour"]
    xcol = np.array(["RGB".index(cc[q]) for q in sched.x_checks])
    zcol = np.array(["RGB".index(cc[q]) for q in sched.z_checks])
    return spec, xcol, zcol


SPEC0, XCOL, ZCOL = base()
# CNOT time table: data column -> list of (kind, check index, base time)
_T = []
for kind, chk in (("X", SPEC0.x_checks), ("Z", SPEC0.z_checks)):
    for i, c in enumerate(chk):
        for col, t in c.cnots:
            _T.append((col, 0 if kind == "X" else 1, i, t))
_T = np.array(_T)
NDATA = 144


def legal(dx, dz):
    """dx, dz: int arrays (72,) of shifts.  True iff every data qubit's 6 CNOT times are distinct mod 8."""
    sh = np.where(_T[:, 1] == 0, dx[_T[:, 2]], dz[_T[:, 2]])
    t = (_T[:, 3] + sh) % D
    key = _T[:, 0] * D + t
    return len(np.unique(key)) == len(key)


def offsets_of(c):
    """(meas offset, [(cnot offset, col) ...]) of a Fig. 12 check relative to its prep (period 8)."""
    return c.offsets(D)


def spec_P(sx, sz, P, name="", gaps=None):
    """Period-P schedule: check i starts (prep) at s_i (mod P), keeps Fig. 12's CNOT offsets (1..6) and meas offset 7,
    optionally with extra per-check gaps: gaps[kind][i] = list of 6 non-negative ints added cumulatively before
    each CNOT (order preserved)."""
    def mk(c, s, g):
        dm, offs = c.offsets(D)
        add = np.cumsum(g) if g is not None else np.zeros(6, int)
        cn = tuple(sorted((col, int((s + o + add[k]) % P)) for k, (o, col) in enumerate(offs)))
        return CheckTiming(int(s % P), int((s + dm + add[-1]) % P), cn)
    gx = gaps["X"] if gaps else [None] * 72
    gz = gaps["Z"] if gaps else [None] * 72
    return ScheduleSpec(P, tuple(mk(c, s, g) for c, s, g in zip(SPEC0.x_checks, sx, gx)),
                        tuple(mk(c, s, g) for c, s, g in zip(SPEC0.z_checks, sz, gz)), name=name)


def legal_spec(spec):
    """Data-conflict-free check on any ScheduleSpec."""
    seen = set()
    for chk in (spec.x_checks, spec.z_checks):
        for c in chk:
            for col, t in c.cnots:
                if (col, t) in seen:
                    return False
                seen.add((col, t))
    return True


def deterministic(spec):
    from evaluators.candidate import build_circuits
    from search.experiments.e018.common import css
    try:
        for b, circ in build_circuits(spec, css(), 2).items():
            circ.detector_error_model()
        return True
    except ValueError:
        return False


def prep_starts():
    """Fig. 12 prep times (period 8) of X and Z checks."""
    return np.array([c.prep for c in SPEC0.x_checks]), np.array([c.prep for c in SPEC0.z_checks])


def spec_of(dx, dz, name=""):
    def mv(c, s):
        return CheckTiming((c.prep + s) % D, (c.meas + s) % D, tuple(sorted((a, (t + s) % D) for a, t in c.cnots)))
    return ScheduleSpec(D, tuple(mv(c, int(s)) for c, s in zip(SPEC0.x_checks, dx)),
                        tuple(mv(c, int(s)) for c, s in zip(SPEC0.z_checks, dz)), name=name)


def colour_shifts(p):
    """p = (xR, xG, xB, zR, zG, zB) -> (dx, dz)."""
    p = np.asarray(p)
    return p[:3][XCOL], p[3:][ZCOL]


def pattern(dx, dz):
    """Per-data-qubit cyclic X/Z pattern counts (diagnostic)."""
    from collections import Counter
    sh = np.where(_T[:, 1] == 0, dx[_T[:, 2]], dz[_T[:, 2]])
    t = (_T[:, 3] + sh) % D
    seq = [["."] * D for _ in range(NDATA)]
    for (col, k, _, _), tt in zip(_T, t):
        seq[col][tt] = "XZ"[k]
    return Counter("".join(s) for s in seq)


if __name__ == "__main__":
    n = 0
    legal_list = []
    for p in itertools.product(range(D), repeat=6):
        if p[0] != 0:
            continue
        dx, dz = colour_shifts(p)
        if legal(dx, dz):
            legal_list.append(p)
    print(f"colour-uniform shift vectors (xR = 0 fixed): {D ** 5}, legal (data-conflict-free): {len(legal_list)}")
    json.dump(legal_list, open("results/E-018-gross-interleaved-12/colour_legal.json", "w"))
