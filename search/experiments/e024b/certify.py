"""E-024b: exact lift of a candidate spec, R in a list, both bases; also legality via evaluator validate_schedule.

    PYTHONPATH=.:tests uv run python -m search.experiments.e024b.certify spec.json --col 3,1,1 --x ... --z ... --R 1 2 ... 14
"""
import argparse
import json
import time

from evaluators.candidate import parse_schedule
from search.experiments.e024b.common import OUT
from search.experiments.e024b.gen import Cls, lift_screen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--col", default="3,1,1")
    ap.add_argument("--x", required=True)
    ap.add_argument("--z", required=True)
    ap.add_argument("--R", type=int, nargs="+", required=True)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    C = Cls(tuple(int(v) for v in a.col.split(",")), a.x, a.z)
    d = json.load(open(a.spec))
    from evaluators.candidate import validate_schedule  # noqa: F401  (public entry)
    from evaluators.tasks import build_code, get_task
    code, _ = build_code(get_task("gross-dcirc"), None)
    spec = parse_schedule(d)
    probs = validate_schedule(spec, code)
    t0 = time.time()
    out = {"spec": a.spec, "period": d["period"], "validate_problems": [str(p) for p in probs] if probs else []}
    per = []
    for R in a.R:
        r = lift_screen(d, C, rlist=[R], stop_first=True)
        per += r.get("per", [])
        print(R, r["status"], [(p["basis"], p["lifting"]) for p in r.get("per", [])], f"{time.time() - t0:.0f}s",
              flush=True)
        if r["status"] != "CERTIFIED":
            break
    out["per"] = per
    out["all_zero"] = all(p["lifting"] == 0 for p in per) and len(per) == 2 * len(a.R)
    tag = a.tag or a.spec.split("/")[-1].replace(".json", "")
    (OUT / f"certify_{tag}.json").write_text(json.dumps(out))
    print("ALL_ZERO", out["all_zero"], out["validate_problems"][:3])


if __name__ == "__main__":
    main()
