"""Audit E-021 (b7): structural hypotheses for the any-R argument.
(a) round separation: in the unrolled circuit every ancilla of round k is reset at layer s+38k and measured at
    s+38k+37, all its CNOTs strictly between; so round windows [s+38k, s+38k+37] tile the time axis.
(b) periodicity: the noisy SD6 circuit's layers (ops incl. noise, excluding annotations) satisfy
    layer[t+P] == layer[t] for every t in rounds 1..R-2 windows, and the R+1 circuit = R circuit with one block
    inserted (layer lists compared).
(c) detectors = consecutive same-check comparisons + first-round + final (by coordinates).
    PYTHONPATH=.:tests uv run python research/audits/2026-10-10-E-021-scripts/b7_periodic.py
"""
import json, sys
sys.path.insert(0, "research/audits/2026-10-10-E-021-scripts")
from b_common import *
from evaluators.candidate import unroll

spec = load_spec().canonical()
P = spec.period
info = {}
for R in (3, 8):
    U = unroll(spec, code, R)
    preps = sorted(U.preps); meas = sorted(U.meas)
    s0 = preps[0]
    ok = all(t == s0 + P * k for k, t in enumerate(preps)) and all(t == s0 + P * k + P - 1 for k, t in enumerate(meas))
    ok &= all(len(U.preps[t]) == 144 for t in preps) and all(len(U.meas[t]) == 144 for t in meas)
    ok &= all(any(s0 + P * k < t < s0 + P * k + P - 1 for k in range(R)) for t in U.cnots)
    info[f"R{R}_separation"] = {"ok": bool(ok), "first_prep_layer": s0, "num_layers": U.num_layers}


def layers(c):
    out, cur = [], []
    for op in c.flattened():
        if op.name == "TICK":
            out.append("\n".join(sorted(cur))); cur = []
        elif op.name not in ("DETECTOR", "OBSERVABLE_INCLUDE"):
            cur.append(str(op))
    out.append("\n".join(sorted(cur)))
    return out


for basis in "ZX":
    Ls = {R: layers(add_noise(build_circuits(spec, code, R)[basis], "sd6", 1e-3)) for R in (6, 7, 14)}
    s0 = info["R3_separation"]["first_prep_layer"]
    L = Ls[14]
    per = all(L[t] == L[t + P] for t in range(s0 + P, s0 + P * 12))
    # inserting one block of P layers after round 1 maps R=6 onto R=7
    a, b = Ls[6], Ls[7]
    cut = s0 + P * 2
    ins = (b[:cut] == a[:cut]) and (b[cut + P:] == a[cut:]) and (b[cut:cut + P] == a[cut - P:cut])
    info[f"{basis}_periodic_rounds1..12"] = bool(per)
    info[f"{basis}_R7_is_R6_plus_block"] = bool(ins)
    c = build_circuits(spec, code, 5)[basis]
    co = c.get_detector_coordinates()
    info[f"{basis}_det_coords_complete"] = sorted({(int(v[0]), int(v[1])) for v in co.values()}) == \
        [(i, j) for i in range(72) for j in range(6)]
print(json.dumps(info, indent=1))
json.dump(info, open(f"{OUT}/b7_periodic.json", "w"), indent=1)
