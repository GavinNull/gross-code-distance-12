"""Prop. 3 lower bound for IBM's depth-8 circuit (arXiv:2308.07915 Table 5, interleaved) on a BB code:
d_circ >= d_ext(E_IBM).  Extended code from the IBM per-check CNOT orders, complete DFS with the full translation
group (uniform tiling), plus the Table-I computational check on the evaluator's circuits.

    PYTHONPATH=. uv run python search/experiments/e015/ibm_lower.py --code bb72 --task bb72-dcirc --W 5 6
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import numpy as np  # noqa: E402

from common import OUT, get_code, now  # noqa: E402
from dfsrun import decide  # noqa: E402
from search.codes.schedule import default_schedule  # noqa: E402
from search.noninterleaved.ext import orders_from_schedule  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", default="bb72")
    ap.add_argument("--task", default="bb72-dcirc")
    ap.add_argument("--W", type=int, nargs="+", default=[5])
    ap.add_argument("--table1", action="store_true")
    a = ap.parse_args()
    code = get_code(a.code)
    sched = default_schedule(code)
    xo, zo = orders_from_schedule(sched)
    sym = list(range(code.n2))
    out = {"code": a.code, "schedule": "IBM depth-8 (default_schedule)", "x_order_check0": xo[0], "z_order_check0": zo[0]}
    for W in a.W:
        for kind, orders in (("X", xo), ("Z", zo)):
            r = decide(code, kind, orders, sym, W, stop_on_found=True,
                       inst_path=OUT / f"inst_ibm_{a.code}_{kind}.txt")
            out[f"W{W}_{kind}"] = r
            print(f"[{now()}] IBM {a.code} {kind} W={W}: found_any={r['found_any']} nodes={r['nodes']} "
                  f"cases={r['cases_run']}/{r['info']['orbits']} {r['sec']}s info={r['info']}", flush=True)
    if a.table1:
        from evaluators.tasks import build_code, get_task
        css, _ = build_code(get_task(a.task), None)
        assert (np.asarray(css.HX) == code.HX).all() and (np.asarray(css.HZ) == code.HZ).all()
        from table1 import table1_check
        t0 = time.time()
        out["table1"] = table1_check(sched, css, R=3)
        print("table1", out["table1"], f"{time.time() - t0:.0f}s", flush=True)
    (OUT / f"ibm_lower_{a.code}.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
