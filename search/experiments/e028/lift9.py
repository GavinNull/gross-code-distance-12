"""E-028: exact test "is there an undetected circuit logical of weight <= 9" for a circuit whose side has d_ext = 8.

Case analysis (template identity + Table I, as in lift.py): the images of an undetected logical F (|F| <= 9) are 0 or
single extended columns, and their sum (after cancelling equal pairs and dropping zeros) is an extended logical of
weight >= 8.  With |F| = 8: 8 distinct non-zero images (weight-8 list).  With |F| = 9: either 9 distinct non-zero images
(weight-9 extended logical; every weight-9 extended logical is syndrome-minimal when d_ext = 8 and no column is a
logical by itself, so the W=9 DFS list is complete) or exactly one zero-image fault + 8 distinct non-zero images
(weight-8 list + one zero-image DEM term).  The second case is decided by the same frontier DP with an extra optional
group = {no fault} + {zero-image detector masks contained in the union of the 8 groups' supports} (a zero-image term
flipping a detector outside that union cannot be cancelled).

    PYTHONPATH=.:tests uv run python -m search.experiments.e028.lift9 SPEC.json --R 1 2 3 --xo ... --zo ...
"""
from __future__ import annotations

import argparse
import json
import time

from evaluators.candidate import parse_schedule
from search.experiments.e018.lift import solve
from search.experiments.e028 import common as C
from search.experiments.e028.cegar import load_class
from search.experiments.e028.lift import KIND_OF_BASIS, build_groups, label_orders, reindex


def test(spec, R, basis, l8, l9, cs8, stop_first=True):
    lo = label_orders(spec)
    k = KIND_OF_BASIS[basis]
    E = C.ext_general(k, lo[k], group=[(0, 0)])
    s8, cs = reindex(E, l8)
    assert cs == cs8
    s9, _ = reindex(E, l9)
    zeros = set()
    groups, st = build_groups(spec, R, basis, E, zeros=zeros)
    out = {"R": R, "basis": basis, "w8": 0, "w8z": 0, "w9": 0, "n8": len(s8), "n9": len(s9), "zero_terms": len(zeros),
           **st}
    for S in s8:
        if solve(S, groups)[0] is not None:
            out["w8"] += 1
            if stop_first:
                return out
    ZID = -1
    for S in s8:
        sup = 0
        for j in S:
            for m in groups[j]:
                sup |= m
        g = groups.copy()
        g[ZID] = [0] + [z for z in zeros if z & ~sup == 0]
        if solve(tuple(S) + (ZID,), g)[0] is not None:
            out["w8z"] += 1
            if stop_first:
                return out
    for S in s9:
        if solve(S, groups)[0] is not None:
            out["w9"] += 1
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
        l8, cs8 = load_class(k, sub, o, 8)
        l9, _ = load_class(k, sub, o, 9)
        lists[k] = (l8, l9, cs8)
    for R in a.R:
        for b in a.bases:
            t0 = time.time()
            r = test(spec, R, b, *lists[KIND_OF_BASIS[b]], stop_first=not a.all)
            r["sec"] = round(time.time() - t0, 1)
            print(json.dumps(r), flush=True)
            with open(C.OUT / "lift9.jsonl", "a") as f:
                f.write(json.dumps({"spec": a.spec, **r}) + "\n")


if __name__ == "__main__":
    main()
