"""E-028 positive control: a segmentable (non-interleaved) circuit with given uniform orders: X block (prep 0, CNOTs
1..6 in order, meas 7) then Z block (prep 7, CNOTs 8..13, meas 14), period 16.  By Cor. 1 its d_circ = d_ext = 8, so
the exact lift must find lifting weight-8 extended logicals.
    PYTHONPATH=.:tests uv run python -m search.experiments.e028.segctl A1A2A3B2B1B3 A1A2A3B2B1B3
"""
import json
import sys

from evaluators.candidate import parse_schedule, validate_schedule
from search.experiments.e028 import common as C
from search.experiments.e028.cegar import load_class
from search.experiments.e028.lift import lift_screen

xo, zo = C.parse_order(sys.argv[1]), C.parse_order(sys.argv[2])
T = C.table()
d = {"format": "qec-schedule/v1", "period": 16, "x_checks": [], "z_checks": []}
for i in range(C.N2):
    d["x_checks"].append({"prep": 0, "meas": 7, "cnots": [[int(T["X"][i][l]), 1 + k] for k, l in enumerate(xo)]})
    d["z_checks"].append({"prep": 7, "meas": 14, "cnots": [[int(T["Z"][i][l]), 8 + k] for k, l in enumerate(zo)]})
assert not validate_schedule(parse_schedule(d), C.css())
lists, cs = {}, {}
for k, o in (("X", sys.argv[1]), ("Z", sys.argv[2])):
    lists[k], cs[k] = load_class(k, "all", o, 8)
for R in (1, 2, 3):
    r = lift_screen(d, lists, cs, rlist=[R], stop_first=False)
    print(R, json.dumps(r["per"] if "per" in r else r))
(C.OUT / f"segctl_{sys.argv[1]}_{sys.argv[2]}.json").write_text(json.dumps(d))
