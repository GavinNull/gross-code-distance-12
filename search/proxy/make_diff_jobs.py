"""Write rounds-difference partner jobs (full decoder, rounds d/2, seed 2, max_shots = half the gold shots, rounded
to the batch size) for every finished gold run.  PYTHONPATH=. uv run python -m search.proxy.make_diff_jobs > jobs_diff.txt"""
import json
from pathlib import Path

OUT = Path("results/E-004-proxy-fidelity")
print("# rounds-difference partner: full decoder, rounds d/2, paper, seed 2, max_shots = gold shots / 2")
for f in sorted((OUT / "l2").glob("*__full__*__s1.json")):
    d = json.loads(f.read_text())
    c = d["e004"]["candidate"]
    if d["e004"]["rounds"] != c["d"]:
        continue
    n = max(25, 25 * round(d["counts"]["shots"] / 2 / 25))
    print(f"{c['name']} full h 2 1000000 {n}")
