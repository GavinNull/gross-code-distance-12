"""E-017 stage 2/3: circuit-distance upper bounds of the morphing circuit with the evaluator's upper_bound (read-only use).

Usage:
  uv run python -m search.experiments.e017.ub --hom x --basis Z --rounds 2 --seed 0 [--swap23] \
      [--trials 1500 --osd 2 --lns 96 --workers 4] --out results/E-017-gross-morphing-scoping/ub/...json
Noise: sd6 (evaluator default; uniform depolarizing incl. idle) at p = 1e-3 (p does not affect the distance).
Every reported weight is the evaluator's injection-verified witness. The witness faults are saved.
"""
from __future__ import annotations

import argparse
import json
import os
import time

from evaluators.distance import upper_bound
from evaluators.noise import add_noise
from search.experiments.e017.morph import TWO_GROSS, Morph, check_deterministic


def build(hom, swap23, basis, rounds, first_j=1, p=1e-3):
    M = Morph(TWO_GROSS, hom, swap23=swap23)
    c = M.memory_circuit(basis, rounds, first_j=first_j)
    det_ok, obs_ok = check_deterministic(c)
    assert det_ok and obs_ok
    return add_noise(c, "sd6", p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hom", default="x")
    ap.add_argument("--swap23", action="store_true")
    ap.add_argument("--basis", default="Z")
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--first_j", type=int, default=1)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--trials", type=int, default=1500)
    ap.add_argument("--osd", type=int, default=2)
    ap.add_argument("--lns", type=int, default=96)
    ap.add_argument("--hops", type=int, default=1)
    ap.add_argument("--lns_det_time", type=float, default=1.0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--stim_search", action="store_true")
    ap.add_argument("--oneround", action="store_true", help="1 noisy round between noiseless rounds (Prop. 1 instance)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    t0 = time.time()
    if a.oneround:
        from search.experiments.e017.oneround import one_round_circuit
        noisy, _ = one_round_circuit(hom=a.hom, swap23=a.swap23, basis=a.basis, first_j=a.first_j)
    else:
        noisy = build(a.hom, a.swap23, a.basis, a.rounds, a.first_j)
    methods = ("graphlike", "stim_search", "bposd") if a.stim_search else ("graphlike", "bposd")
    r = upper_bound(noisy, seed=a.seed, methods=methods, bposd_trials=a.trials, bposd_osd_order=a.osd,
                    lns_starts=a.lns, lns_hops=a.hops, lns_det_time=a.lns_det_time, num_workers=a.workers,
                    stim_search_timeout_s=600.0)
    d = r.to_dict()
    d["config"] = vars(a)
    d["wall_s"] = round(time.time() - t0, 1)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(d, open(a.out, "w"), indent=1, default=str)
    print(a.hom, a.swap23, a.basis, a.rounds, a.seed, "->", r.weight, r.summary() if hasattr(r, "summary") else "",
          f"{time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
