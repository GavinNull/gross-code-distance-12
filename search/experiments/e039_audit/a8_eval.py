"""E-039 audit a8: my finite-R circuit (fcore, reset and no-reset) vs the FROZEN evaluator template
(evaluators.candidate.memory_circuit + evaluators.noise.add_noise('sd6'), public entry points, read-only) on random
legal N7 schedules: exact min weight (<= 3) must agree for R = 1, 2 in both bases; also records whether every sampled
schedule has weight <= 3 in at least one basis (the claim) for reset and no-reset ancillas.
usage: uv run python -m search.experiments.e039_audit.a8_eval --n 40"""
import argparse
import json

from evaluators import candidate as cand
from evaluators.noise import add_noise
from search.experiments.e036.common import code
from search.experiments.e039_audit import fcore as F
from search.experiments.e039_audit.samp import Sampler


def spec_of(tau, S):
    out = {"format": "qec-schedule/v1", "period": S + 2}
    for nm, t in (("x_checks", "X"), ("z_checks", "Z")):
        out[nm] = [{"prep": 0, "meas": S + 1, "cnots": sorted([[F.SUPP[k][a], tau[(k, a)]] for a in range(6)])}
                   for k in F.KS if k[0] == t]
    return out


def ev_min(tau, S, b, R):
    sp = cand.parse_schedule(spec_of(tau, S))
    cd = code("bb18")
    assert not cand.validate_schedule(sp, cd)
    c = add_noise(cand.memory_circuit(sp, cd, b, R), "sd6", 1e-3)
    return F.min_weight3(F.dem_mechs(c))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=2027)
    a = ap.parse_args()
    sp = Sampler(7, seed=a.seed)
    tot = {"n": 0, "agree": 0, "disagree": 0, "claim_holds_reset": {1: 0, 2: 0, 3: 0}, "claim_holds_noreset": {1: 0, 2: 0, 3: 0}}
    for i in range(a.n):
        tau = sp.sample()
        tot["n"] += 1
        for R in (1, 2, 3):
            wr = {b: F.dist(tau, 7, b, R) for b in "ZX"}
            wn = {b: F.dist(tau, 7, b, R, reset=False) for b in "ZX"}
            if R <= 2:
                for b in "ZX":
                    we = ev_min(tau, 7, b, R)
                    if we == wr[b]:
                        tot["agree"] += 1
                    else:
                        tot["disagree"] += 1
                        print("EVAL MISMATCH", i, R, b, we, wr[b], flush=True)
            tot["claim_holds_reset"][R] += any(w is not None for w in wr.values())
            tot["claim_holds_noreset"][R] += any(w is not None for w in wn.values())
    print(json.dumps(tot))
    with open("results/E-039-audit/a8_eval.jsonl", "a") as f:
        f.write(json.dumps(tot) + "\n")
