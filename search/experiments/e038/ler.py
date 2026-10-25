"""E-038: LER of the d_circ = 4 schedule vs the Kunlun circuit, with E-036's pipeline unchanged
(search.experiments.e036.ler.run_one: Tab. S1 'kl' noise mapping on the CNOT template, BP-OSD min-sum 100 iters
OSD-CS 7, Jeffreys 95%).  Pre-registered (experiments/E-038-bb18-d4.yaml): 200,000 shots, R = 6, scale 1 and 0.1.
Both circuits are re-sampled here with seed 20261026 (no reuse of E-036 samples).  Output: results/E-038-bb18-d4/ler.jsonl
usage: uv run python -m search.experiments.e038.ler <circuit> <basis> <scale>"""
import json
import sys

from search.experiments.e036.ler import run_one

if __name__ == "__main__":
    circ, basis, scale = sys.argv[1], sys.argv[2], float(sys.argv[3])
    r = run_one("bb18", circ, basis, 6, 200000, scale, 20261026)
    print(json.dumps(r), flush=True)
    with open("results/E-038-bb18-d4/ler.jsonl", "a") as f:
        f.write(json.dumps(r) + "\n")
