"""Circuits of Table I (SM S3, S4, S8): membership in the class T(P), the timings of Tables II and S1, and the
round-offset cochain delta of Table S3.

For each circuit file: every check of a type uses the same reset step, the same CNOT step per term label A1..B3 and the
same measurement step (modulo P); the six steps are distinct and span <= P - 3 with reset before and measurement after
(cyclically); the six CNOTs on every data qubit fall on distinct steps modulo P; determinism
floor((tX(Ai) - tZ(Bj)) / P) = floor((tX(Bj) - tZ(Ai)) / P) =: G(i, j) for all i, j (times unwrapped from the reset);
CNOT orders and steps equal Table II / S1; G - delta(Table S3) is constant; the stim memory circuits (R = 1, 2, both
bases) are deterministic (code/gross12/schedule.py validation and a noiseless sample).

    python code/tclass/check_circuits.py [NAME ...]      (default: all nine circuits of Table I)
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from codes import code                      # noqa: E402
from gross12 import schedule as PS          # noqa: E402
from p11 import common as C                 # noqa: E402
from bb90 import bbcode                     # noqa: E402

LAB = ["A1", "A2", "A3", "B1", "B2", "B3"]
# name: (family, file, X (reset, order, steps, meas), Z (...), delta rows A1..A3 / columns B1..B3)  -- Tables II, S1, S3
TABLE = {
    "g10": ("gross", "g10", (9, "A1A2B1A3B2B3", (0, 1, 2, 3, 4, 7), 8), (8, "B3B2A3B1A2A1", (9, 2, 3, 4, 5, 6), 7),
            [[0, 0, 1], [0, 0, 1], [0, 1, 1]]),
    "c11": ("bb90", "bb90_c11", (0, "B1B3B2A3A1A2", (1, 2, 3, 4, 5, 9), 10), (10, "A2A1A3B2B3B1", (0, 4, 5, 6, 7, 8), 9),
            [[-1, -1, -1], [0, 0, 0], [-1, -1, -1]]),
    "ibm_gross": ("gross", "ibm_gross_depth8", (7, "A2B2B1B3A1A3", (0, 1, 2, 3, 4, 5), 6),
                  (6, "A1A3B1B2B3A2", (7, 0, 1, 2, 3, 4), 5), [[1, 1, 1], [0, 0, 0], [1, 1, 1]]),
    "g8": ("gross", "g8", (7, "A2A1B2B3B1A3", (0, 1, 2, 3, 4, 5), 6), (0, "A3B1B3B2A1A2", (1, 2, 3, 4, 5, 6), 7),
           [[1, 1, 1], [1, 1, 1], [2, 2, 2]]),
    "g9": ("gross", "g9", (8, "A1B1A2A3B2B3", (0, 1, 2, 3, 4, 6), 7), (7, "B3B2A3A2B1A1", (8, 1, 2, 3, 4, 5), 6),
           [[0, 0, 1], [0, 1, 1], [0, 1, 1]]),
    "u11": ("gross", "u11", (0, "A2A1A3B3B2B1", (1, 2, 3, 4, 5, 9), 10), (10, "B1B2B3A3A1A2", (0, 4, 5, 6, 7, 8), 9),
            [[0, -1, -1], [0, -1, -1], [0, -1, -1]]),
    "ibm90": ("bb90", "bb90_ibm_depth8", (7, "A2B2B1B3A1A3", (0, 1, 2, 3, 4, 5), 6),
              (6, "A1A3B1B2B3A2", (7, 0, 1, 2, 3, 4), 5), [[1, 1, 1], [0, 0, 0], [1, 1, 1]]),
    "b9": ("bb90", "bb90_b9", (8, "A1A2B2B3A3B1", (0, 2, 3, 4, 5, 6), 7), (0, "B1A3B2B3A2A1", (1, 2, 3, 4, 5, 7), 8),
           [[1, 1, 1], [2, 1, 1], [2, 2, 2]]),
    "b10": ("bb90", "bb90_b10", (9, "A1A2B2A3B3B1", (0, 1, 2, 3, 4, 7), 8), (8, "B1B3A3B2A1A2", (9, 2, 3, 4, 5, 6), 7),
            [[1, 0, 0], [1, 0, 0], [1, 0, 1]]),
}


def side(chks, T, P):
    """common (reset, {label: unwrapped time}, meas) of one check type, or raise."""
    common = None
    for i, c in enumerate(chks):
        lab = {int(T[i][k]): k for k in range(6)}
        prep = c["prep"]
        t = {lab[q]: prep + ((s - prep) % P) for q, s in c["cnots"]}
        assert sorted(t) == list(range(6)), "check acts on the wrong qubits"
        key = (prep % P, tuple(t[k] for k in range(6)), c["meas"] % P)
        assert common is None or key == common, "timing differs between checks"
        common = key
    return common


def check(name):
    fam, fname, tx_exp, tz_exp, delta = TABLE[name]
    d = json.load(open(ROOT / "data" / "circuits" / f"{fname}.json"))
    P = d["period"]
    Cd = code(fam)
    out = []
    (px, TX, mx) = side(d["x_checks"], Cd["T"]["X"], P)
    (pz, TZ, mz) = side(d["z_checks"], Cd["T"]["Z"], P)
    ok = True
    for (p, t, m), (pe, oe, se, me) in (((px, TX, mx), tx_exp), ((pz, TZ, mz), tz_exp)):
        order = "".join(LAB[k] for k in np.argsort(t))
        steps = tuple(t[LAB.index(oe[2 * i:2 * i + 2])] % P for i in range(6))
        span = max(t) - min(t)
        ok &= order == oe and steps == se and p == pe and m == me and len(set(t)) == 6 and span <= P - 3
        out.append(f"{order} steps {','.join(map(str, steps))} span {span}")
    A, B = (0, 1, 2), (3, 4, 5)
    distinct = all((TX[a] - TZ[b]) % P and (TX[b] - TZ[a]) % P for a in A for b in B)
    G = np.array([[(TX[a] - TZ[b]) // P for b in B] for a in A])
    GR = np.array([[(TX[b] - TZ[a]) // P for b in B] for a in A])
    det = (G == GR).all()
    diff = G - np.array(delta)
    ok &= distinct and det and len(set(diff.ravel().tolist())) == 1
    spec = PS.parse_schedule(d)
    cobj = C.load_gross() if fam == "gross" else bbcode.load_code()
    ok &= not PS.validate_schedule(spec, cobj)
    for R in (1, 2):
        for b, c in PS.build_circuits(spec.canonical(), cobj, R).items():
            ok &= not c.compile_detector_sampler().sample(4).any()
    print("PASS" if ok else "FAIL", f"{name} (P = {P}): X {out[0]}; Z {out[1]}; distinct mod P {distinct}; "
          f"deterministic {det}; delta = {np.array(delta).tolist()} (G - delta = {int(diff.ravel()[0])}); "
          "legal, noiseless R = 1, 2 detectors silent")
    return ok


if __name__ == "__main__":
    names = sys.argv[1:] or list(TABLE)
    sys.exit(0 if all([check(n) for n in names]) else 1)
