"""E-029: re-check ccsearch witnesses on a freshly built DEM (own code).

    PYTHONPATH=.:tests uv run python search/experiments/e029/verify.py CIRCUIT_JSON TASK BASIS R RUNFILE

Rebuilds the DEM through the evaluator's public entry, keeps the same columns as export.py, and checks for every
SOL line: distinct columns, XOR of detector sets empty, XOR of observables nonzero.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export import add_noise, build_circuits, build_code, dem_columns, get_task, parse_schedule  # noqa: E402

path, task, basis, R, run = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
code, _ = build_code(get_task(task), None)
spec = parse_schedule(json.load(open(path)))
_, cols = dem_columns(add_noise(build_circuits(spec.canonical(), code, R)[basis], "sd6", 1e-3))
cols = [c for c in cols if c[0] or c[1]]
for line in open(run):
    if not line.startswith("SOL"):
        continue
    ids = [int(x) for x in line.split(":")[1].split()]
    d, o = set(), set()
    for j in ids:
        d ^= set(cols[j][0]); o ^= set(cols[j][1])
    print(f"weight {len(ids)} distinct={len(set(ids)) == len(ids)} detectors_left={len(d)} observables={sorted(o)}")
