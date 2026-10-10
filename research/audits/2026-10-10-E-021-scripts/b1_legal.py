"""Audit E-021 (b1): legality / validity of cand1 with own checks + evaluator public entries.
    PYTHONPATH=.:tests uv run python research/audits/2026-10-10-E-021-scripts/b1_legal.py
"""
import json, sys, itertools
import numpy as np
import stim
sys.path.insert(0, "tests")
from evaluators.tasks import build_code, get_task
from evaluators.candidate import parse_schedule, validate_schedule, build_circuits
from evaluators.l0 import check_l0
from evaluators.pipeline import _l0_constraints

import os
SPEC = os.environ.get("SPEC", "search/experiments/e021/cand1_spec.json")
OUT = "results/E-021-audit" + (f"/{os.environ['TAG']}" if os.environ.get("TAG") else "")
os.makedirs(OUT, exist_ok=True)
raw = json.load(open(SPEC))
info = {}

# --- own gross code from polynomials (arXiv:2308.07915): l=12, m=6, A=x^3+y+y^2, B=y^3+x+x^2 ---
l, m = 12, 6
def mono(p, q, transpose=False):
    M = np.zeros((72, 72), np.uint8)
    for a in range(l):
        for b in range(m):
            i = a * m + b; j = ((a + p) % l) * m + (b + q) % m
            if transpose: M[j, i] = 1
            else: M[i, j] = 1
    return M
code, _ = build_code(get_task("gross-dcirc"), None)
HX, HZ = np.asarray(code.HX) % 2, np.asarray(code.HZ) % 2
for tr in (False, True):
    A = (mono(3, 0, tr) + mono(0, 1, tr) + mono(0, 2, tr)) % 2
    B = (mono(0, 3, tr) + mono(1, 0, tr) + mono(2, 0, tr)) % 2
    hx = np.hstack([A, B]); hz = np.hstack([B.T, A.T])
    info[f"own_poly_eq_evaluator_transpose={tr}"] = bool((hx == HX).all() and (hz == HZ).all())
def rk(M):
    M = M.copy() % 2; r = 0
    for c in range(M.shape[1]):
        p = np.nonzero(M[r:, c])[0]
        if len(p) == 0: continue
        p = p[0] + r; M[[r, p]] = M[[p, r]]
        for i in np.nonzero(M[:, c])[0]:
            if i != r: M[i] ^= M[r]
        r += 1
        if r == M.shape[0]: break
    return r
info["n"] = 144; info["k"] = int(144 - rk(HX) - rk(HZ)); info["HXHZt0"] = bool(((HX @ HZ.T) % 2 == 0).all())
info["LX,LZ shapes"] = [list(np.asarray(code.LX).shape), list(np.asarray(code.LZ).shape)]

# --- own spec checks ---
P = raw["period"]; probs = []
use = {}
for ty, key, H in (("X", "x_checks", HX), ("Z", "z_checks", HZ)):
    assert len(raw[key]) == 72
    for i, c in enumerate(raw[key]):
        cols = [a for a, _ in c["cnots"]]; ts = [t for _, t in c["cnots"]]
        if sorted(cols) != sorted(np.nonzero(H[i])[0].tolist()): probs.append(f"{ty}{i} support")
        if len(cols) != 6 or len(set(cols)) != 6: probs.append(f"{ty}{i} not 6 distinct")
        if len(set(ts)) != 6: probs.append(f"{ty}{i} ancilla time clash")
        offs = [(t - c["prep"]) % P for t in ts]; dm = (c["meas"] - c["prep"]) % P
        if not all(0 < o < dm for o in offs): probs.append(f"{ty}{i} window")
        for a, t in c["cnots"]:
            use.setdefault((t % P, a), []).append(f"{ty}{i}")
probs += [f"data {a} t{t} {w}" for (t, a), w in use.items() if len(w) > 1]
info["own_spec_problems"] = probs
info["preps"] = sorted({c["prep"] for k in ("x_checks", "z_checks") for c in raw[k]})
info["meas"] = sorted({c["meas"] for k in ("x_checks", "z_checks") for c in raw[k]})
info["period"] = P
spec = parse_schedule(raw)
info["evaluator_validate_problems"] = validate_schedule(spec, code)
# non-wrapping: all CNOT times strictly between prep 0 and meas 37 => each round is [reset, 6 CNOT, meas] in one period

# interleaving: per data qubit cyclic sequence of X/Z types
seq = {}
for ty, key in (("X", "x_checks"), ("Z", "z_checks")):
    for c in raw[key]:
        for a, t in c["cnots"]:
            seq.setdefault(a, []).append((t, ty))
sw = []
for a, s in seq.items():
    s = [ty for _, ty in sorted(s)]
    sw.append(sum(s[i] != s[i - 1] for i in range(len(s))))
info["switch_hist"] = {int(k): sw.count(k) for k in sorted(set(sw))}

# determinism: noiseless circuits, DEM construction (raises on non-determinism) + sampler all-zero + L0
det = {}
for R in (1, 2, 3, 6):
    cs = build_circuits(spec.canonical(), code, R)
    for b, c in cs.items():
        c.detector_error_model()  # raises if a detector/observable is non-deterministic
        s = c.compile_detector_sampler(seed=1).sample(64, append_observables=True)
        det[f"R{R}{b}"] = {"dets": c.num_detectors, "obs": c.num_observables, "any_fire_noiseless": bool(s.any()),
                           "nqubits": c.num_qubits}
info["determinism"] = det
l0 = {}
for R in (2, 3):
    cons = _l0_constraints(get_task("gross-dcirc"), code, R, with_distance=False)
    cs = build_circuits(spec.canonical(), code, R)
    for b, c in cs.items():
        rep = check_l0(c, code, b, cons)
        l0[f"R{R}{b}"] = {"passed": bool(rep.passed), "failed": [r.name for r in rep.failures]}
info["L0"] = l0
print(json.dumps(info, indent=1))
json.dump(info, open(f"{OUT}/b1_legal.json", "w"), indent=1)
