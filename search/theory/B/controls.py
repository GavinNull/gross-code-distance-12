"""Write the control schedules (circuits known to stop short of d) as qec-schedule/v1 JSON in results/theoryB/specs/.
  uv run python -m search.theory.B.controls
"""
import json, sys
from search.theory.B.bulk import ROOT
for p in (str(ROOT), str(ROOT / "tests")):
    sys.path.insert(0, p)
from schedule_helpers import from_baseline
from baselines.bb_code import BBCode
from baselines.schedule import ibm_depth8
from search.experiments.e036.common import kunlun_spec

out = ROOT / "results/theoryB/specs"
out.mkdir(parents=True, exist_ok=True)
for name, (l, m, A, B) in {"ibm8_gross": (12, 6, ["x^3", "y", "y^2"], ["y^3", "x", "x^2"]),
                           "ibm8_bb90": (15, 3, ["x^9", "y", "y^2"], ["x^0", "x^2", "x^7"]),
                           "ibm8_bb72": (6, 6, ["x^3", "y", "y^2"], ["y^3", "x", "x^2"]),
                           "ibm8_bb108": (9, 6, ["x^3", "y", "y^2"], ["y^3", "x", "x^2"])}.items():
    s = from_baseline(ibm_depth8(BBCode(l, m, A, B))).canonical()
    json.dump(s.to_dict(), open(out / f"{name}.json", "w"))
json.dump(kunlun_spec("bb18").to_dict(), open(out / "kunlun_bb18.json", "w"))
print("ok")
