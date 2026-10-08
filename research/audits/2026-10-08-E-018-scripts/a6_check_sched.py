"""Audit E-018 (a6): check a schedule found by a5 (positive control): legal (evaluator parse_schedule), stim-deterministic,
own-model block count over all 360 Z-side single-hook logicals, and the experimenter's exact DP (lift.py, augmented
DEM) on the model-blocked logicals at several R.
    PYTHONPATH=.:tests uv run python research/audits/2026-10-08-E-018-scripts/a6_check_sched.py FILE.json R1 R2 ...
"""
import ast, json, sys
sys.path.insert(0, "research/audits/2026-10-08-E-018-scripts")
from a1_common import xo, zo, xcol, zcol, code
from a3_model import single_hook_logicals, lifts
from evaluators.candidate import CheckTiming, ScheduleSpec, build_circuits, parse_schedule

res = json.load(open(sys.argv[1])); P = res["P"]
Rs = [int(x) for x in sys.argv[2:]] or [2, 4]
sc = {ast.literal_eval(k): v for k, v in res["sched"].items()}
key = (lambda chk: (chk[0], xcol[chk[1]] if chk[0] == "X" else zcol[chk[1]])) if res["mode"] == "sym" else (lambda chk: chk)
sched = {chk: (sc[key(chk)][0], tuple(sc[key(chk)][1])) for chk in [("X", i) for i in range(72)] + [("Z", j) for j in range(72)]}
def mk(chk):
    s, o = sched[chk]; ords = xo[chk[1]] if chk[0] == "X" else zo[chk[1]]
    return CheckTiming(s % P, (s + o[5] + 1) % P, tuple(sorted((int(q), (s + o[k]) % P) for k, q in enumerate(ords))))
spec = ScheduleSpec(P, tuple(mk(("X", i)) for i in range(72)), tuple(mk(("Z", j)) for j in range(72)))
spec = parse_schedule(spec.to_dict())          # evaluator's strict parser (raises if illegal)
for b, c in build_circuits(spec, code, 2).items():
    c.detector_error_model()                    # raises on non-deterministic detectors
LOG = single_hook_logicals("X")
blocked = [L for L in LOG if not lifts(sched, P, L, "Z")]
out = {"file": sys.argv[1], "legal_and_deterministic": True, "model_blocked": len(blocked), "of": len(LOG)}
# exact DP on the blocked ones (map back to the experimenter's column indices)
from search.experiments.e018.common import ext
from search.experiments.e018.lift import build_groups, solve
import pickle
E = ext("X")
idx_of = {}
for S in pickle.load(open("results/E-018-gross-interleaved-12/w11_all_X.pkl", "rb")):
    free = tuple(sorted(next(s for s in E["col_sups"][j] if len(s) == 1)[0] for j in S if any(len(s) == 1 for s in E["col_sups"][j])))
    hk = [E["col_sups"][j][0] for j in S if not any(len(s) == 1 for s in E["col_sups"][j])]
    if len(free) == 10 and len(hk) == 1:
        idx_of.setdefault((free, tuple(sorted(hk[0]))), []).append(S)
for R in Rs:
    groups, stats, _, _ = build_groups(spec.canonical(), R, "Z")
    nl = 0
    for L in blocked:
        Ss = idx_of[(tuple(sorted(L[0])), tuple(sorted(L[2])))]
        assert len(Ss) == 1
        nl += any(solve(S, groups)[0] is not None for S in Ss)
    out[f"exact_lift_R{R}_among_model_blocked"] = nl
print(json.dumps(out))
