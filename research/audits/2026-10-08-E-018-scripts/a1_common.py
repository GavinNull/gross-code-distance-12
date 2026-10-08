"""Audit E-018 shared: evaluator code matrices, Fig. 12 spec/orders/colours (read from the evaluator-format spec)."""
import sys
import numpy as np
sys.path.insert(0, "tests")
from schedule_helpers import from_baseline
from baselines.bb_code import gross_code
from baselines.strikis import strikis_fig12
from evaluators.tasks import build_code, get_task

code, _ = build_code(get_task("gross-dcirc"), None)
HX, HZ, LX, LZ = [np.asarray(m, np.uint8) % 2 for m in (code.HX, code.HZ, code.LX, code.LZ)]
sched, meta = strikis_fig12(gross_code())
SPEC = from_baseline(sched)
P0 = SPEC.period


def order(c, P=P0):
    return [col for _, col in sorted(((t - c.prep) % P, col) for col, t in c.cnots)]


xo = [order(c) for c in SPEC.x_checks]
zo = [order(c) for c in SPEC.z_checks]
xcol = ["RGB".index(meta["check_colour"][q]) for q in sched.x_checks]
zcol = ["RGB".index(meta["check_colour"][q]) for q in sched.z_checks]


def tr(a, b):
    return [((i // 6 + a) % 12) * 6 + (i % 6 + b) % 6 for i in range(72)]
