"""E-038 audit: re-run E-038's own LER pipeline (search.experiments.e036.ler.run_one, unchanged) with a NEW seed, to
separate sampling noise from pipeline dependence of the x0.1 ratios.  Output appended to results/E-038-audit/b6c.jsonl.
usage: PYTHONPATH=.:tests uv run python -m search.experiments.e038_audit.b6c_theirs CIRCUIT BASIS SCALE SHOTS SEED"""
import json
import sys

from search.experiments.e036.ler import run_one

circ, basis, scale, shots, seed = sys.argv[1], sys.argv[2], float(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
r = run_one("bb18", circ, basis, 6, shots, scale, seed)
print(json.dumps(r), flush=True)
with open("results/E-038-audit/b6c.jsonl", "a") as f:
    f.write(json.dumps(r) + "\n")
