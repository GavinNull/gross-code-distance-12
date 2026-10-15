"""Auditor: is search/experiments/e024a/cs_P18_H24.json the released circuit A? Compare canonical specs and the DEMs."""
import json, sys
sys.path[:0] = ['.', 'tests']
from evaluators.candidate import build_circuits, parse_schedule
from evaluators.noise import add_noise
from evaluators.tasks import build_code, get_task
code, _ = build_code(get_task('gross-dcirc'), None)
a = parse_schedule(json.load(open('search/experiments/e024a/cs_P18_H24.json'))).canonical()
rel = json.load(open('release/zenodo/data/circuits/circuit_A.json'))
try:
    b = parse_schedule(rel).canonical()
except Exception as e:
    print('direct parse failed', e, list(rel)[:10]); b = parse_schedule(rel.get('schedule', rel)).canonical()
print('canonical spec equal:', a == b)
for B in 'ZX':
    for R in (1, 2):
        da = add_noise(build_circuits(a, code, R)[B], 'sd6', 1e-3).detector_error_model(decompose_errors=False)
        db = add_noise(build_circuits(b, code, R)[B], 'sd6', 1e-3).detector_error_model(decompose_errors=False)
        print(B, R, 'DEM equal:', da == db)
