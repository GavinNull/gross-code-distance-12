"""E-032: exact test "is there an undetected circuit logical of weight <= d_ext + 1" for a gross circuit whose side
has d_ext = 10 (generalisation of e028/lift9.py, which is the d_ext = 8 case; audited E-028).

Case analysis (journal, "generalised Lemma 2"): an undetected logical F with w faults has z zero-image faults and
c cancelling pairs of equal non-zero images; the odd-multiplicity columns x form an extended logical with
|x| = w - z - 2c >= d_ext (Lemma 1).  With d_ext = 10:  w = 10 -> z = c = 0 (10 distinct columns: weight-10 list);
w = 11 -> (z, c) = (0, 0) (weight-11 list) or (1, 0) (weight-10 list + exactly one zero-image DEM term).
Completeness of the W = 11 DFS list: a weight-11 extended logical with d_ext = 10 has no proper zero-syndrome subset
(a zero-syndrome subset of size k with zero L part leaves a logical of weight 11 - k >= 10 -> k <= 1 -> a zero column,
which does not exist (dropped); one with non-zero L part is a logical of weight >= 10, leaving one column with zero
H part, i.e. a weight-1 logical or a zero column -- impossible).  So every weight-11 extended logical is printed.
The zero-image case uses the same frontier DP (e018/lift.solve, audited) with one extra group
{zero-image detector masks contained in the union of the 10 groups' supports}.

    PYTHONPATH=.:tests uv run python -m search.experiments.e032.lift10 SPEC.json --R 1 2 3 --xo ... --zo ...
"""
from __future__ import annotations

import argparse
import json
import time

from evaluators.candidate import parse_schedule
from search.experiments.e018.lift import solve
from search.experiments.e032 import common as C
from search.experiments.e032.cegar import load_class
from search.experiments.e032.lift import KIND_OF_BASIS, build_groups, label_orders, reindex

DE = 10


def test(spec, R, basis, lA, lB, csA, stop_first=True):
    """lA: weight-DE list (keys), lB: weight-(DE+1) list."""
    lo = label_orders(spec)
    k = KIND_OF_BASIS[basis]
    E = C.ext_general(k, lo[k], group=[(0, 0)])
    sA, cs = reindex(E, lA)
    assert cs == csA, "circuit's extended code differs from the class"
    sB, _ = reindex(E, lB)
    zeros = set()
    groups, st = build_groups(spec, R, basis, E, zeros=zeros)
    out = {"R": R, "basis": basis, "w10": 0, "w10z": 0, "w11": 0, "n10": len(sA), "n11": len(sB),
           "zero_terms": len(zeros), **st}
    for S in sA:
        if solve(S, groups)[0] is not None:
            out["w10"] += 1
            if stop_first:
                return out
    ZID = -1
    for S in sA:
        sup = 0
        for j in S:
            for m in groups[j]:
                sup |= m
        g = groups.copy()
        g[ZID] = [0] + [z for z in zeros if z & ~sup == 0]
        if len(g[ZID]) > 1 and solve(tuple(S) + (ZID,), g)[0] is not None:
            out["w10z"] += 1
            if stop_first:
                return out
    for S in sB:
        if solve(S, groups)[0] is not None:
            out["w11"] += 1
            if stop_first:
                return out
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--R", type=int, nargs="+", default=[1])
    ap.add_argument("--bases", default="ZX")
    ap.add_argument("--xo", required=True)
    ap.add_argument("--zo", required=True)
    ap.add_argument("--xsub", default="all")
    ap.add_argument("--zsub", default="all")
    ap.add_argument("--all", type=int, default=0, help="count all lifting logicals (no early stop)")
    a = ap.parse_args()
    spec = parse_schedule(json.load(open(a.spec))).canonical()
    lists = {}
    for k, sub, o in (("X", a.xsub, a.xo), ("Z", a.zsub, a.zo)):
        lA, csA = load_class(k, sub, o, DE)
        lB, _ = load_class(k, sub, o, DE + 1)
        lists[k] = (lA, lB, csA)
    for R in a.R:
        for b in a.bases:
            t0 = time.time()
            r = test(spec, R, b, *lists[KIND_OF_BASIS[b]], stop_first=not a.all)
            r["sec"] = round(time.time() - t0, 1)
            print(json.dumps(r), flush=True)
            with open(C.OUT / "lift10.jsonl", "a") as f:
                f.write(json.dumps({"spec": a.spec, **r}) + "\n")


if __name__ == "__main__":
    main()
