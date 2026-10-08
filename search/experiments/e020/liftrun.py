"""E-020: run E-018's exact lift checker (search/experiments/e018/lift.py, complete per audit 2026-10-08 B) on a
candidate schedule JSON; output to results/E-020-gross-perchk-pipeline/lift_<tag>.json.  Stops a (R, basis) at the
first `max_hits` hits (any hit => that circuit has a weight-11 undetected logical at that R => d_circ <= 11).

    PYTHONPATH=.:tests uv run python -m search.experiments.e020.liftrun CAND.json --R 1 2 3 4 5 6 [--max_hits 1]
"""
from __future__ import annotations

import argparse
import json
import pickle
import time
from pathlib import Path

from evaluators.candidate import parse_schedule
from search.experiments.e018.common import OUT as E18
from search.experiments.e018.lift import KIND_OF_BASIS, build_groups, check_orders, solve

OUT = Path("results/E-020-gross-perchk-pipeline")


def run(spec, Rs, bases="ZX", max_hits=10 ** 9, logicals=None):
    spec = spec.canonical()
    check_orders(spec)
    per = []
    for R in Rs:
        for basis in bases:
            t0 = time.time()
            kind = KIND_OF_BASIS[basis]
            sols = logicals[kind] if logicals else pickle.load(open(E18 / f"w11_all_{kind}.pkl", "rb"))
            groups, stats, _, _ = build_groups(spec, R, basis)
            hits = []
            for S in sols:
                ch, _ = solve(S, groups)
                if ch is not None:
                    hits.append({"S": [int(x) for x in S], "masks": {int(k): int(v) for k, v in ch.items()}})
                    if len(hits) >= max_hits:
                        break
            per.append({"R": R, "basis": basis, "num_logicals": len(sols), "lifting": len(hits),
                        "stopped_early": len(hits) >= max_hits, "sec": round(time.time() - t0, 1), **stats,
                        "hits": hits[:5]})
            print(f"R={R} {basis}: lifting {len(hits)}/{len(sols)}{' (stopped)' if len(hits) >= max_hits else ''} "
                  f"{per[-1]['sec']}s", flush=True)
    return per


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cand")
    ap.add_argument("--R", type=int, nargs="+", default=[1, 2, 3, 4, 5, 6])
    ap.add_argument("--bases", default="ZX")
    ap.add_argument("--max_hits", type=int, default=10 ** 9)
    ap.add_argument("--tag", default=None)
    a = ap.parse_args()
    spec = parse_schedule(json.loads(Path(a.cand).read_text()))
    per = run(spec, a.R, a.bases, a.max_hits)
    tag = a.tag or Path(a.cand).stem
    (OUT / f"lift_{tag}.json").write_text(json.dumps({"cand": a.cand, "per": per}, indent=1))


if __name__ == "__main__":
    main()
