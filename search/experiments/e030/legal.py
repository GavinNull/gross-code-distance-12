"""E-030: legality of a spec on bb90: validate_schedule, L0 (syntax + semantics, distance skipped) at R = 3 both bases,
determinism (noiseless DEM, allow_gauge_detectors=False) for R = 1..12, translation invariance of the CNOT times.
    PYTHONPATH=.:tests uv run python -m search.experiments.e030.legal SPEC.json
"""
import json
import sys
from pathlib import Path

from evaluators.candidate import build_circuits, parse_schedule, validate_schedule
from evaluators.l0 import L0Constraints, check_l0
from search.experiments.e028 import common as C

path = sys.argv[1]
d = json.load(open(path))
spec = parse_schedule(d).canonical()
code = C.css()
res = {"spec": path, "period": d["period"], "validate": validate_schedule(spec, code)}
rep = check_l0(build_circuits(spec, code, 3), code, "both", L0Constraints(rounds=3))
res["L0"] = {c.name: c.status for c in rep.checks}
res["L0_passed"] = all(c.status in ("pass", "skipped") for c in rep.checks)
for R in range(1, 13):
    for b, c in build_circuits(spec, code, R).items():
        c.detector_error_model(allow_gauge_detectors=False)
res["deterministic_R1_12"] = True
# translation invariance: label -> (time) identical for all checks of a type; prep/meas identical
T = C.table()
inv = True
for ty, key in (("X", "x_checks"), ("Z", "z_checks")):
    ref = None
    for i, c in enumerate(d[key]):
        lab = {C.LAB[list(T[ty][i]).index(q)]: t for q, t in c["cnots"]}
        sig = (c["prep"], c["meas"], tuple(sorted(lab.items())))
        ref = ref or sig
        inv &= sig == ref
    res[f"{ty}_times"] = dict(prep=ref[0], meas=ref[1], cnot=dict(ref[2]),
                             order="".join(k for k, _ in sorted(ref[2], key=lambda kv: (kv[1] - ref[0]) % d["period"])))
res["translation_invariant"] = bool(inv)
print(json.dumps(res))
Path(f"results/E-030-bb90-period-ler/legal_{Path(path).stem}.json").write_text(json.dumps(res, indent=1))
