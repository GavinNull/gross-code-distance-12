"""Stage 1: literal-text build (illegal), corrected build, legality, determinism (own circuits), interleaving,
gate-by-gate comparison with lead's assemble.py schedule, evaluator validate."""
import sys, json; sys.path.insert(0, "research/audits/2026-10-05-E-013-scripts"); sys.path.insert(0, "tests")
import numpy as np, stim
from aud13 import *

out = {}
c, s_text = build()
out["literal_text_conflicts"] = len(legality(c, s_text))
Z_EVEN_FIX = [3, 4, 5, 2, 1, 0]   # lead's ((2,1,0),(0,1,2)) = (pi_A, sigma_B) -> B(0,1,2) then A(2,1,0)
c, s = build(ze=Z_EVEN_FIX)
out["fixed_conflicts"] = legality(c, s)
spec = to_spec(s)
from evaluators.tasks import get_task, build_code
from evaluators.candidate import validate_schedule, memory_circuit
task = get_task("bb108-dcirc")
css, _ = build_code(task, None)
assert (css.HX == c.HX).all() and (css.HZ == c.HZ).all(), "row/column convention mismatch"
out["evaluator_validate"] = validate_schedule(spec, css)
# determinism, own circuits
det = {}
for basis in "ZX":
    for R in (1, 2, 3, 4):
        circ = memory(c, s, basis, R)
        try:
            dem = circ.detector_error_model(allow_gauge_detectors=False)
            ok = True
        except Exception as e:
            ok = str(e)[:200]
        # noiseless sample
        nl = circ.without_noise()
        smp = nl.compile_detector_sampler().sample(64, append_observables=True)
        det[f"{basis}{R}"] = dict(deterministic=ok, noiseless_any_flip=bool(smp.any()),
                                  detectors=circ.num_detectors, observables=circ.num_observables)
out["own_circuit_determinism"] = det
out["interleave"] = interleave_tests(c, s, rounds=6)
out["interleave_text_literal_ignored"] = "illegal anyway"
# gate-by-gate vs lead
from search.noninterleaved.colour_search import order_terms
from search.noninterleaved.schedules import build_schedule
from search.noninterleaved.two_colour import M, ctx
from schedule_helpers import from_baseline
cx, cz = ctx("X"), ctx("Z")
xb = [cx["ok"][2], cx["ok"][14]]; zb = [cz["ok"][12], cz["ok"][0]]
x_spec = [(0, order_terms("X", *xb[(i % M) % 2])) for i in range(c.n2)]
z_spec = [(4, order_terms("Z", *zb[(i % M) % 2])) for i in range(c.n2)]
lead = from_baseline(build_schedule(c, x_spec, z_spec))
out["lead_term_orders"] = {"X_even": x_spec[0][1], "X_odd": x_spec[1][1], "Z_even": z_spec[0][1], "Z_odd": z_spec[1][1]}
out["identical_to_lead_spec"] = (lead.period == spec.period and lead.x_checks == spec.x_checks and lead.z_checks == spec.z_checks)
out["identical_hash"] = lead.hash() == spec.hash()
diffs = 0
for a, b in zip(lead.x_checks + lead.z_checks, spec.x_checks + spec.z_checks):
    diffs += (a != b)
out["n_check_diffs"] = diffs
# text-literal vs lead differences
st = to_spec(s_text)
out["literal_vs_lead_check_diffs"] = sum(a != b for a, b in zip(lead.z_checks, st.z_checks)) + sum(a != b for a, b in zip(lead.x_checks, st.x_checks))
json.dump(spec.to_dict(), open("results/E-013-audit/spec_auditor.json", "w"))
print(json.dumps(out, indent=1, default=str))
json.dump(out, open("results/E-013-audit/s2_legal.json", "w"), indent=1, default=str)
