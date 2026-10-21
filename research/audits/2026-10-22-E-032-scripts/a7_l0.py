"""A7: evaluator public L0 checks (both bases, R = 1, 3) and validate_schedule; freeze status."""
import sys, json
from evaluators.candidate import build_circuits, parse_schedule, validate_schedule
from evaluators.tasks import build_code, get_task
from evaluators.l0 import check_l0
c, _ = build_code(get_task("gross-dcirc"), None)
spec = parse_schedule(json.load(open(sys.argv[1]))).canonical()
print("validate_schedule problems:", validate_schedule(spec, c))
for R in (1, 3):
    for b, circ in build_circuits(spec, c, R).items():
        rep = check_l0(circ, c, b)
        print(R, b, "passed" if getattr(rep, "passed", None) else rep, flush=True)
