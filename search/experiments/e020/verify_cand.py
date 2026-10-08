"""E-020: check a CEGAR 'CANDIDATE' schedule independently: (1) legality / determinism via the evaluator's
ScheduleSpec + stim (E-018 gen.legal_spec / deterministic), (2) E-018 frame_model.feasible_general on the
logicals the run modelled, (3) optional exact lift (E-018 lift.py) at given R.

    PYTHONPATH=.:tests uv run python -m search.experiments.e020.verify_cand results/.../cegar_<tag>.json [--R 2 4 6]
"""
from __future__ import annotations

import argparse
import json

from search.experiments.e018.frame_model import abs_tables, feasible_general
from search.experiments.e018.gen import deterministic, legal_spec
from search.experiments.e020.cegar import prep_logicals
from search.experiments.e020.liftrun import run
from search.experiments.e020.xcheck import spec_of_options


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("res")
    ap.add_argument("--R", type=int, nargs="*", default=[])
    ap.add_argument("--orbit_only", action="store_true")
    a = ap.parse_args()
    d = json.load(open(a.res))
    P = d["P"]
    spec = spec_of_options(d["candidate"], P)
    print("legal", legal_spec(spec), "deterministic", deterministic(spec), flush=True)
    L, _ = prep_logicals(d["kinds"], d["types"])
    tabs = {b: abs_tables(spec, b) for b in "ZX"}
    lifted = {}
    for kind, S, cp, _ in L:
        b = "Z" if kind == "X" else "X"
        r = feasible_general(list(S), kind, *tabs[b])
        lifted[(kind, S)] = r
    print("model (E-018 feasible_general): lifting", sum(1 for v in lifted.values() if v), "/", len(lifted), flush=True)
    json.dump(spec.to_dict(), open(a.res.replace(".json", "_spec.json"), "w"))
    if a.R:
        logs = None
        if a.orbit_only:
            blocked = {"X": [S for (k, S), v in lifted.items() if k == "X" and not v],
                       "Z": [S for (k, S), v in lifted.items() if k == "Z" and not v]}
            logs = blocked
        per = run(spec, a.R, "ZX", logicals=logs)
        json.dump(per, open(a.res.replace(".json", "_lift.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
