"""Audit E-021 (b3): independent exact lift with CP-SAT (not the experimenter's DP) and the E-018 AUDIT's own
complete weight-11 list. For each weight-11 extended logical S (11 column keys): exists one DEM term per column
whose detector sets XOR to zero?  (Exact: a weight-11 undetected circuit logical has 11 distinct non-zero images
forming a weight-11 extended logical, by telescoping + d_ext = 11; checked in b2.)
    PYTHONPATH=.:tests uv run python research/audits/2026-10-11-E-024b-scripts/b3_lift.py cand|fig12 basis R [R ...]
"""
import json, sys, time
sys.path.insert(0, "research/audits/2026-10-11-E-024b-scripts")
from b_common import *
from ortools.sat.python import cp_model

which, basis, Rs = sys.argv[1], sys.argv[2], [int(x) for x in sys.argv[3:]]
kind = {"Z": "X", "X": "Z"}[basis]
spec = load_spec() if which == "cand" else parse_schedule(A1.SPEC.to_dict())
lists, kb = audit018_lists(kind)
assert len(lists) == 4224, len(lists)


def lifts(S, groups):
    M = cp_model.CpModel()
    one = M.NewConstant(1)
    det_lits = {}
    for key in S:
        vs = []
        for dets in groups[key]:
            v = M.NewBoolVar("")
            vs.append(v)
            for d in dets:
                det_lits.setdefault(d, []).append(v)
        M.AddExactlyOne(vs)
    for d, ls in det_lits.items():
        M.AddBoolXOr(ls + [one])     # XOR(ls) xor 1 = 1  <=>  XOR(ls) = 0
    s = cp_model.CpSolver(); s.parameters.num_workers = 1; s.parameters.random_seed = 7
    st = s.Solve(M)
    assert st in (cp_model.OPTIMAL, cp_model.INFEASIBLE, cp_model.FEASIBLE), s.StatusName(st)
    return st != cp_model.INFEASIBLE


res = []
for R in Rs:
    t0 = time.time()
    groups, st = dem_groups(spec, R, basis)
    assert set(groups) == set(kb)
    hits = [i for i, S in enumerate(lists) if lifts(S, groups)]
    rec = {"which": which, "basis": basis, "R": R, "lifting": len(hits), "of": len(lists), **st,
           "sec": round(time.time() - t0, 1), "hits_first": hits[:20]}
    print(rec, flush=True)
    res.append(rec)
    json.dump(res, open(f"{OUT}/b3_{which}_{basis}_{'-'.join(map(str, Rs))}.json", "w"), indent=1)
