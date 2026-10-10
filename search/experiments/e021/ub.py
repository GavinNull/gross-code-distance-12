"""E-021: evaluator upper bound (public entry evaluators.distance.upper_bound) on a candidate schedule, plus an
interleaving count (data qubits whose cyclic X/Z CNOT sequence has more than 2 switches).

    PYTHONPATH=.:tests uv run python -m search.experiments.e021.ub spec.json R basis trials workers max_sec
"""
import json
import sys

from evaluators.candidate import build_circuits, parse_schedule
from evaluators.distance import upper_bound
from evaluators.noise import add_noise
from search.experiments.e018.common import css

spec = parse_schedule(json.load(open(sys.argv[1]))).canonical()
R, basis, trials, workers, msec = int(sys.argv[2]), sys.argv[3], int(sys.argv[4]), int(sys.argv[5]), float(sys.argv[6])
seq = {}
for ty, chk in (("X", spec.x_checks), ("Z", spec.z_checks)):
    for c in chk:
        for q, t in c.cnots:
            seq.setdefault(q, []).append((t % spec.period, ty))
sw = []
for q, s in seq.items():
    s = [ty for _, ty in sorted(s)]
    sw.append(sum(1 for i in range(len(s)) if s[i] != s[i - 1]))
print("switch histogram", {k: sw.count(k) for k in sorted(set(sw))}, flush=True)
circ = add_noise(build_circuits(spec, css(), R)[basis], "sd6", 1e-3)
res = upper_bound(circ, seed=20261010, bposd_trials=trials, num_workers=workers, max_seconds=msec,
                  stim_search_timeout_s=300)
print("R", R, "basis", basis, "upper bound", getattr(res, "distance", res), flush=True)
print(res)
