"""E-036 common: the Kunlun [[18,4,4]] / [[18,6,3]] codes (Wang et al., Nat. Phys. 2026, arXiv 2505.09684).  experimenter.

Code convention (paper SI Sec. I.1): l = m = 3, x = S3 (x) I3, y = I3 (x) S3, A = x + 1 + y^2, B = y + 1 + x^2,
H_X = [A | B], H_Z = [B^T | A^T].  Index of monomial x^a y^b = 3a + b; data column i < 9 is L^i, 9 + i is R^i;
row j of H_X / H_Z is check X^j / Z^j (the SI 0..8 labels of Fig. S1).

Measured checks:  bb18  : X {0,1,3,4,5,6,7}, Z {0,1,2,5,6,7,8}  (X2, X8, Z3, Z4 removed as redundant; SI Fig. S2)
                  q1863 : additionally X5, Z5 removed            ([[18,6,3]])
                  full  : all 9 + 9 checks (unconstrained: 36 qubits; not the Kunlun chip)

Per-check CNOT orders are given by term labels 0..5 = A1 A2 A3 B1 B2 B3 with A1 = x, A2 = 1, A3 = y^2, B1 = y,
B2 = 1, B3 = x^2 (the paper's a = [1,0,2], b = [1,0,2] order, same as IBM's A = A1 + A2 + A3 convention).
X check (a,b) term t touches  L(a,b)+A_t  for t < 3 and R(a,b)+B_{t-3} for t >= 3.
Z check (a,b) term t touches  R(a,b)-A_t  for t < 3 and L(a,b)-B_{t-3} for t >= 3   (transposes).
"""
from __future__ import annotations

import itertools
import json
import os
import sys
from functools import lru_cache
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np
import stim

ROOT = Path(__file__).resolve().parents[3]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from evaluators import candidate as cand  # noqa: E402
from evaluators.codes import CSSCode, compute_logicals  # noqa: E402
from evaluators.noise import add_noise  # noqa: E402

OUT = ROOT / "results" / "E-036-bb18"
OUT.mkdir(parents=True, exist_ok=True)
L, M = 3, 3
N2 = 9
ASH = [(1, 0), (0, 0), (0, 2)]  # A1 = x, A2 = 1, A3 = y^2
BSH = [(0, 1), (0, 0), (2, 0)]  # B1 = y, B2 = 1, B3 = x^2
TERMS = ["A1", "A2", "A3", "B1", "B2", "B3"]

VARIANTS = {
    "bb18": ([0, 1, 3, 4, 5, 6, 7], [0, 1, 2, 5, 6, 7, 8]),
    "q1863": ([0, 1, 3, 4, 6, 7], [0, 1, 2, 6, 7, 8]),
    "full": (list(range(9)), list(range(9))),
    "q1863full": None,  # not used
}


def idx(a, b):
    return (a % L) * M + (b % M)


def ab(i):
    return divmod(i, M)


def term_col(kind: str, chk: int, t: int) -> int:
    a, b = ab(chk)
    if kind == "X":
        if t < 3:
            da, db = ASH[t]
            return idx(a + da, b + db)
        da, db = BSH[t - 3]
        return N2 + idx(a + da, b + db)
    if t < 3:
        da, db = ASH[t]
        return N2 + idx(a - da, b - db)
    da, db = BSH[t - 3]
    return idx(a - da, b - db)


@lru_cache(maxsize=None)
def full_H():
    HX = np.zeros((9, 18), np.uint8)
    HZ = np.zeros((9, 18), np.uint8)
    for j in range(9):
        for t in range(6):
            HX[j, term_col("X", j, t)] ^= 1
            HZ[j, term_col("Z", j, t)] ^= 1
    return HX, HZ


# SI Fig. S1a transcription (rows X^0..X^8; L block | R block).  Row 0, R block, was read from the image as column 7;
# every column of a BB check matrix has weight 3, which forces column 6 (column 7 would have weight 4) -> corrected.
FIG_S1 = """
101100000 110000100
110010000 011000010
011001000 101000001
000101100 100110000
000110010 010011000
000011001 001101000
100000101 000100110
010000110 000010011
001000011 000001101
"""

# SI Sec. I.1 logical operators
PAPER_LOG = {
    "bb18": {"X": [["L0", "L2", "L4", "L5", "L6", "L7"], ["L1", "L2", "L3", "L4", "L6", "L8"], ["L0", "L1", "L6", "R0"],
                   ["L0", "L1", "L4", "L5", "L6", "R1"]],
             "Z": [["L0", "L2", "L3", "L4", "L8", "R0"], ["L0", "L2", "L4", "L5", "L6", "L7"], ["L1", "L2", "L7", "R1"],
                   ["L0", "L1", "L6", "R0"]]},
    "q1863": {"X": [["L0", "L1", "L3", "L5", "L6"], ["L1", "L2", "L3", "L4", "L7"], ["L0", "L2", "L4", "L5", "L8"],
                    ["L3", "L5", "R0"], ["L3", "L4", "R1"], ["L4", "L5", "R2"]],
              "Z": [["L0", "L3", "L4", "L5", "L8"], ["L0", "L3", "L8", "R0", "R1"], ["L0", "L5", "L8", "R0", "R2"],
                    ["L1", "L4", "L6", "L8", "R0", "R1", "R2"], ["L0", "L1", "L2", "L4", "L7", "L8", "R2"],
                    ["L2", "L4", "R1"]]},
}


def lab2col(s):
    return int(s[1:]) + (0 if s[0] == "L" else N2)


def vec(labels):
    v = np.zeros(18, np.uint8)
    for s in labels:
        v[lab2col(s)] ^= 1
    return v


@lru_cache(maxsize=None)
def checks(variant: str):
    return VARIANTS[variant]


@lru_cache(maxsize=None)
def code(variant: str) -> CSSCode:
    HX, HZ = full_H()
    xs, zs = checks(variant)
    if variant in PAPER_LOG:
        LX = np.array([vec(r) for r in PAPER_LOG[variant]["X"]])
        LZ = np.array([vec(r) for r in PAPER_LOG[variant]["Z"]])
        return CSSCode(HX=HX[xs], HZ=HZ[zs], LX=LX, LZ=LZ, name=f"kunlun-{variant}")
    return CSSCode.from_checks(HX[xs], HZ[zs], name=f"kunlun-{variant}")


# --------------------------------------------------------------------------- schedules
def spec_from_terms(variant: str, xt: dict, zt: dict, period: int, xprep, xmeas, zprep, zmeas) -> cand.ScheduleSpec:
    """xt / zt: {check: [time of term 0..5]} or a single list used for every check; prep/meas: int or {check: int}."""
    xs, zs = checks(variant)
    out = {}
    for kind, lst, tt, pp, mm in (("X", xs, xt, xprep, xmeas), ("Z", zs, zt, zprep, zmeas)):
        rows = []
        for c in lst:
            times = tt[c] if isinstance(tt, dict) else tt
            cn = [[term_col(kind, c, t), int(times[t]) % period] for t in range(6)]
            p = pp[c] if isinstance(pp, dict) else pp
            m = mm[c] if isinstance(mm, dict) else mm
            rows.append({"prep": int(p) % period, "meas": int(m) % period, "cnots": sorted(cn)})
        out[kind] = rows
    return cand.parse_schedule({"format": "qec-schedule/v1", "period": period, "x_checks": out["X"],
                                "z_checks": out["Z"]})


IBM_SX = [None, 1, 4, 3, 5, 0, 2]   # X: -, A2, B2, B1, B3, A1, A3   (baselines.schedule, 2308.07915 Table 5)
IBM_SZ = [0, 2, 3, 4, 5, 1, None]   # Z: A1T, A3T, B1T, B2T, B3T, A2T, -


def slots_to_times(slots, offset):
    t = [None] * 6
    for s, term in enumerate(slots):
        if term is not None:
            t[term] = s + offset
    return t


def kunlun_spec(variant: str) -> cand.ScheduleSpec:
    """Experimental circuit (SI Fig. S3): all checks prepared at layer 0, CNOT layers 1..7 in IBM slot order, all
    measured at layer 8 (period 9 in the project's prep/meas-separate convention)."""
    return spec_from_terms(variant, slots_to_times(IBM_SX, 1), slots_to_times(IBM_SZ, 1), 9, 0, 8, 0, 8)


def ibm_spec(variant: str) -> cand.ScheduleSpec:
    """IBM depth-8 pipelined baseline: X prep 0, CNOT slots at 0..6, X meas 7, Z meas 6, Z prep 7 (wraps)."""
    return spec_from_terms(variant, slots_to_times(IBM_SX, 0), slots_to_times(IBM_SZ, 0), 8, 0, 7, 7, 6)


def load_spec(path) -> cand.ScheduleSpec:
    return cand.parse_schedule(json.loads(Path(path).read_text()))


def noiseless(spec, variant, basis, rounds) -> stim.Circuit:
    return cand.memory_circuit(spec, code(variant), basis, rounds)


def sd6(spec, variant, basis, rounds, p=1e-3) -> stim.Circuit:
    return add_noise(noiseless(spec, variant, basis, rounds), "sd6", p)


def dem_mechs(circ: stim.Circuit):
    """Distinct (detector bitmask, observable bitmask) of single faults (stim merges identical ones)."""
    dem = circ.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    out = {}
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        d = 0
        o = 0
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                d ^= 1 << t.val
            elif t.is_logical_observable_id():
                o ^= 1 << t.val
        if d == 0 and o == 0:
            continue
        out[(d, o)] = out.get((d, o), 0) + inst.args_copy()[0]
    return [k for k in out], dem.num_detectors


def min_weight(mechs, wmax):
    """Exact: smallest w <= wmax such that some w distinct mechanisms have zero detector sum and nonzero observable
    sum; returns (w, witness indices) or (None, None).  Meet-in-the-middle over subsets of size <= 2."""
    D = [m[0] for m in mechs]
    O = [m[1] for m in mechs]
    n = len(mechs)
    # w = 1
    for i in range(n):
        if D[i] == 0 and O[i]:
            return 1, (i,)
    if wmax < 2:
        return None, None
    by = {}
    for i in range(n):
        by.setdefault(D[i], []).append(i)
    for key, lst in by.items():
        os_ = {}
        for i in lst:
            os_.setdefault(O[i], i)
        if len(os_) > 1:
            a, b = list(os_.values())[:2]
            return 2, (a, b)
    if wmax < 3:
        return None, None
    # w = 3: pairs (i<j) vs singles k (k not in {i,j}; k == i or j impossible since that would mean a weight-1 set)
    for i in range(n):
        Di, Oi = D[i], O[i]
        for j in range(i + 1, n):
            key = Di ^ D[j]
            lst = by.get(key)
            if lst:
                oo = Oi ^ O[j]
                for k in lst:
                    if k != i and k != j and O[k] != oo:
                        return 3, (i, j, k)
    if wmax < 4:
        return None, None
    # w = 4: pairs vs pairs, disjoint
    pairs = {}
    for i in range(n):
        for j in range(i + 1, n):
            key = D[i] ^ D[j]
            oo = O[i] ^ O[j]
            ent = pairs.setdefault(key, {})
            if oo not in ent:
                for o2, (a, b) in ent.items():
                    if len({a, b, i, j}) == 4:
                        return 4, (a, b, i, j)
                ent[oo] = (i, j)
            # same oo: no new information for a nonzero-observable 4-set via this pair (kept first rep)
    return None, None


def verify_witness(mechs, wit):
    d = 0
    o = 0
    for i in wit:
        d ^= mechs[i][0]
        o ^= mechs[i][1]
    return d == 0 and o != 0 and len(set(wit)) == len(wit)
