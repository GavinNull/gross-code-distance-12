"""E-040: stim injection (inject.check) of every witness pattern of a sweep on the schedule it was found on, plus
`--extra` random other signatures (of the same P) on which vec.test says the pattern applies (transfer check).

    PYTHONPATH=.:tests uv run python -m search.experiments.e040.inject_all --code bb90 --P 8 --kind X --tag sweep_bb90_P8_X_W9 --extra 2
"""
from __future__ import annotations

import argparse
import json
import random

import numpy as np

from search.experiments.e040 import vec
from search.experiments.e040.bulk import Sector
from search.experiments.e040.codes import OUT
from search.experiments.e040.inject import check
from search.experiments.e040.sweep import groups


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--kind", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--extra", type=int, default=2)
    ap.add_argument("--seed", type=int, default=20261029)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    rows, keys, g = groups(a.P, a.kind)
    reps = [rows[g[k][0]] for k in keys]
    allrows = rows
    tH = np.array([(r["tx"] if a.kind == "X" else r["tz"]) for r in allrows])
    tR = np.array([(r["tz"] if a.kind == "X" else r["tx"]) for r in allrows])
    S0 = Sector(a.code, a.kind, rows[0]["tx"], rows[0]["tz"], a.P)
    n = bad = nx = 0
    weights = {}
    for l in open(OUT / f"{a.tag}_witnesses.jsonl"):
        w = json.loads(l)
        r = reps[w["found_on"]]
        ok = check(a.code, a.kind, r["tx"], r["tz"], a.P, w["faults"])[0]
        n += 1
        bad += not ok
        weights[w["weight"]] = weights.get(w["weight"], 0) + 1
        f = [tuple(x) for x in w["faults"]]
        m = np.flatnonzero(vec.test(S0, f, tH, tR, a.P))
        for idx in rng.sample(list(m), min(a.extra, len(m))):
            rr = allrows[int(idx)]
            ok2 = check(a.code, a.kind, rr["tx"], rr["tz"], a.P, w["faults"])[0]
            nx += 1
            bad += not ok2
            if not ok2:
                print("BAD transfer", w["k"], idx, flush=True)
        if not ok:
            print("BAD", w["k"], flush=True)
    res = {"code": a.code, "P": a.P, "kind": a.kind, "tag": a.tag, "patterns": n, "transfer_checks": nx, "bad": bad,
           "weights": weights}
    print(json.dumps(res))
    with open(OUT / "inject_summary.jsonl", "a") as fo:
        fo.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    main()
