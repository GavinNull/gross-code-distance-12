"""Evaluator upper bound (distance.upper_bound, R=3, sd6) for IBM's depth-8 order on a code without a registered task.
    PYTHONPATH=.:tests uv run python search/experiments/e015/ibm_upper.py wmc108
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, "tests")
from assemble import evaluate  # noqa: E402
from common import OUT, get_code  # noqa: E402
from search.codes.schedule import check_schedule, default_schedule  # noqa: E402

key = sys.argv[1]
code = get_code(key)
sched = default_schedule(code)
chk = check_schedule(code, sched)
print("check_schedule", chk, flush=True)
ev = evaluate(key, sched, None, seed=0, trials=1500, workers=1)
(OUT / f"ibm_upper_{key}.json").write_text(json.dumps({"check": chk, "eval": ev}, default=str, indent=1))
