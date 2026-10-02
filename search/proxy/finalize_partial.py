"""Finalize an L2 run that was stopped (by me, to save budget) before its original stop rule was met.

  PYTHONPATH=. uv run python -m search.proxy.finalize_partial --tag G-perm6__full__r12__paper__s1 --cand G-perm6 \
      --rounds 12 --decoder full --seed 1 --min-sector-errors 100 --batch-size 25

sample_l2's official result = the shortest prefix of batches 0,1,2,... (batch b seeded SeedSequence([seed, b]))
that satisfies the stop rule.  The batch files on disk are exactly what sample_l2 computes, so the prefix for a
*smaller* stop rule (min_sector_errors=100) is bit-identical to what sample_l2(seed, batch_size, StopRule(100)) would
return.  This script takes that prefix (it must be contiguous from 0) and writes the same JSON layout as run_l2,
flagged e004.reconstructed = True.  Intervals use evaluators.stats.binomial_interval and evaluators.l2.per_round.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluators.l2 import StopRule, per_round
from evaluators.stats import DEFAULT_LIKELIHOOD_FACTOR, binomial_interval
from search.proxy import candidates as C

OUT = Path("results/E-004-proxy-fidelity")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--cand", required=True)
    ap.add_argument("--rounds", type=int, required=True)
    ap.add_argument("--decoder", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--min-sector-errors", type=int, required=True)
    ap.add_argument("--max-shots", type=int, default=10 ** 9)
    ap.add_argument("--batch-size", type=int, default=25)
    a = ap.parse_args()
    C.load_bad(OUT / "bad_schedules.json")
    cand = C.get(a.cand)
    bdir = OUT / "batches" / a.tag
    batches = {}
    for f in bdir.glob("batch_*.json"):
        r = json.loads(f.read_text())
        batches[r["index"]] = r
    stop = StopRule(max_shots=a.max_shots, max_errors=a.min_sector_errors, min_sector_errors=a.min_sector_errors,
                    batch_size=a.batch_size)
    shots = fz = fx = fa = fb = 0
    need = None
    b = 0
    while b in batches:
        r = batches[b]
        shots += r["shots"]; fz += r["fail_Z"]; fx += r["fail_X"]; fa += r["fail_any"]; fb += r["fail_both"]
        b += 1
        if stop.satisfied(shots, fa, fz, fx):
            need = b
            break
    if need is None:
        print(f"WARNING: stop rule not reached in the contiguous prefix ({b} batches); using all of it")
        need = b
    lf = DEFAULT_LIKELIHOOD_FACTOR
    rates, pr = {}, {}
    for key, e in (("P_Z", fz), ("P_X", fx), ("P_any", fa)):
        iv = binomial_interval(e, shots, lf)
        rates[key] = {"errors": e, "shots": shots, "best": iv.best, "low": iv.low, "high": iv.high, "label": iv.label()}
        pr[key] = {"best": per_round(iv.best, a.rounds), "low": per_round(iv.low, a.rounds),
                   "high": per_round(iv.high, a.rounds)}
    per_batch = [{k: batches[i][k] for k in ("index", "shots", "fail_Z", "fail_X", "fail_any", "fail_both", "cpu_s")}
                 for i in sorted(batches)]
    cpu_used = sum(batches[i]["cpu_s"] for i in range(need))
    d = {"inputs": {"seed": a.seed, "num_workers": 4, "rounds": a.rounds, "p": 0.004, "boundary": "paper",
                    "stop": {"max_shots": a.max_shots, "max_errors": a.min_sector_errors,
                             "min_sector_errors": a.min_sector_errors, "batch_size": a.batch_size}},
         "counts": {"shots": shots, "fail_Z": fz, "fail_X": fx, "fail_any": fa, "fail_both": fb, "batches_used": need},
         "rates": rates, "per_round": pr,
         "e004": {"candidate": {**cand.__dict__, "Q": cand.Q, "kd2_n": cand.kd2_n}, "decoder_preset": a.decoder,
                  "tag": a.tag, "rounds": a.rounds, "reconstructed": True,
                  "reconstructed_note": "run stopped early by experimenter to save budget; result = batch prefix "
                                        "satisfying the reduced stop rule (bit-identical to sample_l2 with that rule)",
                  "cpu_s_per_shot_used": cpu_used / max(1, shots),
                  "cpu_s_all_batches": sum(x["cpu_s"] for x in per_batch),
                  "B_per_logical_per_round": pr["P_any"]["best"] / cand.k, "per_batch": per_batch}}
    (OUT / "l2" / f"{a.tag}.json").write_text(json.dumps(d, indent=1, default=str))
    print(json.dumps({"tag": a.tag, "shots": shots, "fail_Z": fz, "fail_X": fx, "batches_used": need,
                      "batches_on_disk": len(batches), "B": pr["P_any"]["best"] / cand.k}))


if __name__ == "__main__":
    main()
