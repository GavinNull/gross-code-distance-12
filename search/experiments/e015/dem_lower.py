"""Exact circuit-level check on the DEM (evaluator `distance.lower_bound`, CP-SAT): is there an undetected logical
fault set of weight <= target-1 in the R-round SD6 memory circuit?  Used for IBM's interleaved circuit, where the
Prop. 3 extended-code bound is not tight.  Valid only for the tested R.

    PYTHONPATH=.:tests uv run python search/experiments/e015/dem_lower.py --code bb72 --task bb72-dcirc --target 6 --R 1 2 3
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, "tests")
import numpy as np  # noqa: E402

from common import OUT, get_code, now  # noqa: E402
from evaluators.candidate import build_circuits, parse_schedule  # noqa: E402
from evaluators.distance import lower_bound  # noqa: E402
from evaluators.noise import add_noise  # noqa: E402
from evaluators.tasks import build_code, get_task  # noqa: E402
from schedule_helpers import from_baseline  # noqa: E402
from search.codes.schedule import default_schedule  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", default="bb72")
    ap.add_argument("--task", default="bb72-dcirc")
    ap.add_argument("--target", type=int, default=6)
    ap.add_argument("--R", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--bases", default="ZX")
    ap.add_argument("--tl", type=float, default=3600)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--method", default="cpsat")
    a = ap.parse_args()
    code = get_code(a.code)
    css, _ = build_code(get_task(a.task), None)
    assert (np.asarray(css.HX) == code.HX).all()
    spec = parse_schedule(from_baseline(default_schedule(code))).canonical()
    res = []
    for R in a.R:
        for b in a.bases:
            circ = add_noise(build_circuits(spec, css, R)[b], "sd6", 1e-3)
            t0 = time.time()
            r = lower_bound(circ, method=a.method, time_limit_s=a.tl, target=a.target, num_workers=a.workers)
            rec = {"R": R, "basis": b, "status": r.status, "lb": r.lower_bound, "ub": r.upper_bound,
                   "sec": round(time.time() - t0, 1), "cols": r.num_columns, "dets": r.num_detectors,
                   "msg": r.message}
            print(f"[{now()}] IBM {a.code} R={R} {b}: {rec}", flush=True)
            res.append(rec)
            (OUT / f"dem_lower_ibm_{a.code}_T{a.target}_{a.method}.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
