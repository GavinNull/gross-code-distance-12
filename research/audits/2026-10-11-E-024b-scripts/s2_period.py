"""Audit E-024b (s2): layer-level periodicity of the noisy SD6 p18w circuits (own, no detector bookkeeping):
all insertion positions i such that circuit(R+1) layers = circuit(R) layers with an 18-layer block inserted at i.
Detectors are semantic (consecutive same-check comparisons, template code), each 18-layer block holds exactly
one measurement per ancilla, so layer equality is what the translation step needs.
    SPEC=... PYTHONPATH=.:tests uv run python research/audits/2026-10-11-E-024b-scripts/s2_period.py
"""
import json, os, sys
sys.path.insert(0, "tests")
from evaluators.tasks import build_code, get_task
from evaluators.candidate import parse_schedule, build_circuits, unroll
from evaluators.noise import add_noise
code, _ = build_code(get_task("gross-dcirc"), None)
spec = parse_schedule(json.load(open(os.environ["SPEC"]))).canonical(); P = spec.period
def layers(c):
    out, cur = [], []
    for op in c.flattened():
        if op.name == "TICK":
            out.append("\n".join(sorted(cur))); cur = []
        elif op.name not in ("DETECTOR", "OBSERVABLE_INCLUDE", "SHIFT_COORDS", "QUBIT_COORDS"):
            cur.append(str(op))
    out.append("\n".join(sorted(cur)))
    return out
info = {}
for basis in "ZX":
    for R in (6, 12):
        a = layers(add_noise(build_circuits(spec, code, R)[basis], "sd6", 1e-3))
        b = layers(add_noise(build_circuits(spec, code, R + 1)[basis], "sd6", 1e-3))
        assert len(b) - len(a) == P, (len(a), len(b))
        ok = [i for i in range(len(a) + 1) if b[:i] == a[:i] and b[i + P:] == a[i:]]
        # count measurements per inserted block (must be 144 ancilla measurements)
        info[f"{basis}_R{R}"] = {"layers": len(a), "valid_insert_min": min(ok), "valid_insert_max": max(ok),
                                 "contiguous": ok == list(range(min(ok), max(ok) + 1)),
                                 "meas_in_block": sum(l.count(" ") for l in [] ) }
        blk = b[min(ok):min(ok) + P]
        nm = sum(len(s.split()) - 1 for l in blk for s in l.split("\n") if s.split() and s.split()[0] in ("M", "MX"))
        info[f"{basis}_R{R}"]["meas_targets_in_block"] = nm
    U = unroll(spec, code, 6)
    info["first_layers_with_data_reset"] = 0
print(json.dumps(info, indent=1))
json.dump(info, open("results/E-024b-audit/" + os.environ.get("TAG","p18w") + "/s2_period.json", "w"), indent=1)
