"""E-024a certification lift: the AUDITOR's implementation (research/audits/2026-10-10-E-021-scripts: b_common.dem_groups,
b_common.audit018_lists = E-018 audit's own complete 4224 list, and b3_lift.lifts copied verbatim below) applied to a
given spec, basis and list of R.  Exact: 0 lifting at R  <=>  no undetected logical of weight <= 11 at that R
(telescoping + Table I + d_ext = 11; the image-key set is asserted equal to the extended code's 360 columns).

    PYTHONPATH=.:tests uv run python -m search.experiments.e024a.certify SPEC.json Z 1 2 3 ...
"""
import json
import os
import sys
import time
from pathlib import Path

os.environ["TAG"] = "../E-024a-gross12-period/audit_lib_out"   # b_common makes this dir; we write our own output
sys.path.insert(0, "research/audits/2026-10-10-E-021-scripts")
import b_common as B  # noqa: E402
from ortools.sat.python import cp_model  # noqa: E402

OUT = Path("results/E-024a-gross12-period")


def lifts(S, groups):   # verbatim from b3_lift.py (auditor)
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


def main():
    path, basis, Rs = sys.argv[1], sys.argv[2], [int(x) for x in sys.argv[3:]]
    kind = {"Z": "X", "X": "Z"}[basis]
    spec = B.load_spec(path)
    xo, zo = B.orders(spec.canonical())
    lists, kb = B.audit018_lists(kind)
    assert len(lists) == 4224
    assert set(B.ext_keys(kind, xo, zo)) == set(kb), "extended code differs from Fig. 12's"
    tag = Path(path).stem
    of = OUT / f"cert_{tag}_{basis}.jsonl"
    for R in Rs:
        t0 = time.time()
        groups, st = B.dem_groups(spec, R, basis)
        assert set(groups) == set(kb) and st["bad_obs"] == 0 and st["telescoping_bad"] == 0, st
        hits = [i for i, S in enumerate(lists) if lifts(S, groups)]
        rec = {"spec": path, "basis": basis, "R": R, "lifting": len(hits), "of": len(lists), **st,
               "sec": round(time.time() - t0, 1), "hits_first": hits[:20]}
        print(rec, flush=True)
        with open(of, "a") as f:
            f.write(json.dumps(rec) + "\n")


if __name__ == "__main__":
    main()
