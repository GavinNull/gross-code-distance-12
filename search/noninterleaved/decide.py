"""Decide / compute d_ext for one uniformly tiled order of one kind.

  PYTHONPATH=. uv run python -m search.noninterleaved.decide --code "[[108,8,10]]" --kind X --order 0 1 2 3 4 5 \
      --solver feas --cap 8 --time-limit 1800
solver feas: is there a logical of weight <= cap (decision); solver milp: exact minimum (with valid cap).
"""
import argparse
import json

from search.noninterleaved.ext import residual_supports
from search.noninterleaved.run import HL, OUT, _solve, dump, get_code, neighbours, tag

ap = argparse.ArgumentParser()
ap.add_argument("--code", required=True)
ap.add_argument("--kind", required=True)
ap.add_argument("--order", type=int, nargs=6, required=True)
ap.add_argument("--solver", default="feas")
ap.add_argument("--cap", type=int, required=True)
ap.add_argument("--time-limit", type=float, default=1800)
a = ap.parse_args()
code, css = get_code(a.code)
H, L = HL(css, a.kind)
sups = [s for i in range(code.n2) for s in residual_supports([neighbours(code, a.kind, i, t) for t in a.order])]
r = _solve({"H": H, "L": L, "sups": sups, "cap": a.cap, "tl": a.time_limit, "solver": a.solver, "key": a.order})
r.update({"code": a.code, "kind": a.kind, "solver": a.solver, "cap": a.cap, "time_limit": a.time_limit})
dump(OUT / f"decide_{tag(a.code)}_{a.kind}_{''.join(map(str, a.order))}_{a.solver}_cap{a.cap}.json", r)
print(json.dumps({k: v for k, v in r.items() if k != "witness"}))
