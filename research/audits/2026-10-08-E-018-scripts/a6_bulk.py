"""Audit E-018 (a6_bulk): exact DP restricted to the bulk: drop every augmented DEM term that touches a detector
outside index window [lo*72, (R-hi)*72) (Z basis: 72 detectors per round, in time order).  Shows whether exact lifts
of model-blocked logicals are boundary effects.  argv: schedule json, R, lo, hi"""
import ast, json, sys, pickle, collections
sys.path.insert(0, "research/audits/2026-10-08-E-018-scripts")
from a1_common import xo, zo, xcol, zcol
from a3_model import single_hook_logicals, lifts
from evaluators.candidate import CheckTiming, ScheduleSpec, parse_schedule
from search.experiments.e018.common import ext
from search.experiments.e018.lift import build_groups, solve
res = json.load(open(sys.argv[1])); P = res["P"]; R, lo, hi = map(int, sys.argv[2:5])
sc = {ast.literal_eval(k): v for k, v in res["sched"].items()}
key = (lambda chk: (chk[0], xcol[chk[1]] if chk[0] == "X" else zcol[chk[1]])) if res["mode"] == "sym" else (lambda chk: chk)
sched = {chk: (sc[key(chk)][0], tuple(sc[key(chk)][1])) for chk in [("X", i) for i in range(72)] + [("Z", j) for j in range(72)]}
def mk(chk):
    s, o = sched[chk]; ords = xo[chk[1]] if chk[0] == "X" else zo[chk[1]]
    return CheckTiming(s % P, (s + o[5] + 1) % P, tuple(sorted((int(q), (s + o[k]) % P) for k, q in enumerate(ords))))
spec = parse_schedule(ScheduleSpec(P, tuple(mk(("X", i)) for i in range(72)), tuple(mk(("Z", j)) for j in range(72))).to_dict())
E = ext("X"); idx_of = {}
for S in pickle.load(open("results/E-018-gross-interleaved-12/w11_all_X.pkl", "rb")):
    fr = tuple(sorted(next(s for s in E["col_sups"][j] if len(s) == 1)[0] for j in S if any(len(s) == 1 for s in E["col_sups"][j])))
    hk = [E["col_sups"][j][0] for j in S if not any(len(s) == 1 for s in E["col_sups"][j])]
    if len(fr) == 10 and len(hk) == 1: idx_of[(fr, tuple(sorted(hk[0])))] = S
groups, stats, circ, aug = build_groups(spec.canonical(), R, "Z")
nd = circ.num_detectors
win = 0
for i in range(lo * 72, min(nd, (R - hi) * 72)): win |= 1 << i
bulk = {j: [mk_ for mk_ in g if mk_ & ~win == 0] for j, g in groups.items()}
cnt = collections.Counter()
for L in single_hook_logicals("X"):
    S = idx_of[(tuple(sorted(L[0])), tuple(sorted(L[2])))]
    cnt[(lifts(sched, P, L, "Z"), solve(S, groups)[0] is not None, solve(S, bulk)[0] is not None)] += 1
print(json.dumps({"file": sys.argv[1], "R": R, "window_rounds": [lo, R - hi], "detectors": nd,
                  "(model, exact_full, exact_bulk_window)": {str(k): v for k, v in cnt.items()}}))
