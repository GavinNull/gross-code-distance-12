"""Sanity check of Prop. 3 direction (d_circ >= d_ext(E) for ANY circuit, interleaved included):
d_ext of the IBM (interleaved) circuit's residual set must be <= the IBM circuit's known d_circ upper bound
(<= 8 for [[90,8,10]] / [[108,8,10]], E-004).  Not a test of Corollary 1 (IBM is interleaved).

  PYTHONPATH=. uv run python -m search.noninterleaved.sanity_ibm "[[90,8,10]]"
"""
import json
import sys

from baselines.schedule import IBM_SX, IBM_SZ, bb_term_schedule
from search.noninterleaved.ext import d_ext, orders_from_schedule
from search.noninterleaved.run import OUT, get_code, tag, CODE_D, dump
from search.noninterleaved.schedules import interleaving

name = sys.argv[1]
code, css = get_code(name)
sched = bb_term_schedule(code, IBM_SX, IBM_SZ, "ibm_depth8")
xo, zo = orders_from_schedule(sched)
r = d_ext(css.HX, css.HZ, css.LX, css.LZ, xo, zo, max_weight=CODE_D[name], time_limit=1800)
r["interleaving"] = interleaving(sched)
dump(OUT / f"sanity_ibm_{tag(name)}.json", r)
print(json.dumps({k: (v if k not in ("X", "Z") else {kk: vv for kk, vv in v.items() if kk != "witness"})
                  for k, v in r.items()}, indent=1, default=str))
