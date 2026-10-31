"""c2b: the evaluator's own template (public entries memory_circuit + add_noise('sd6')), reset ancillas, R = 1..Rmax,
exact weight <= 3 via the E-039 auditor's min_weight3; also prints the unroll start offsets (sigma).
usage: uv run python -m search.experiments.e041_audit.c2b_eval <Rmax>"""
import json
import sys

from evaluators import candidate as cand
from evaluators.noise import add_noise
from search.experiments.e036.common import code
from search.experiments.e039_audit import fcore as F

SPEC = "search/experiments/e041/bb18_w9_d4_spec.json"


def main():
    Rmax = int(sys.argv[1])
    cd = code("bb18")
    spec = cand.parse_schedule(json.load(open(SPEC)))
    print("validate:", cand.validate_schedule(spec, cd))
    U = cand.unroll(spec, cd, 2)
    print("sigma", U.sigma, "starts", sorted(set(U.start.values())), "layers(R=2)", U.num_layers)
    for basis in "ZX":
        for R in range(1, Rmax + 1):
            c = add_noise(cand.memory_circuit(spec, cd, basis, R), "sd6", 1e-3)
            ms = F.dem_mechs(c)
            r = dict(basis=basis, R=R, mechs=len(ms), minw_le3=F.min_weight3(ms))
            print(json.dumps(r), flush=True)
            with open("results/E-041-audit/c2b_eval.jsonl", "a") as f:
                f.write(json.dumps(r) + "\n")


if __name__ == "__main__":
    main()
