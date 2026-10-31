"""E-041: describe the weight <= 3 bulk witnesses of a schedule (e038 model, W rounds): counts by pattern type and
basis, checks involved, window starts.  usage: uv run python -m search.experiments.e041.wits <best.json> [--W 6]"""
import argparse
import collections
import json

import numpy as np

from search.experiments.e038.cegar import pattern_of
from search.experiments.e038.model import bulk_min
from search.experiments.e041.fast import KS, sched_from_tau


def load_tau(path):
    d = json.load(open(path))
    if "tau" in d:
        return np.array(d["tau"], np.int64), d["P"]
    from search.experiments.e038.model import Sched
    from search.experiments.e041.fast import tau_from_sched
    from search.experiments.e041.rand import normalise
    s = Sched.from_json(d)
    return normalise(tau_from_sched(s), s.P), s.P


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--W", type=int, default=6)
    a = ap.parse_args()
    tau, P = load_tau(a.path)
    s = sched_from_tau(tau, P)
    w, wits = bulk_min(s, 3, W=a.W, want_all=True, limit=100000)
    pats = {pattern_of(b, t) for b, t in wits}
    typ = collections.Counter((p[0], "".join(sorted(x[0] for x in p[1]))) for p in pats)
    inv = collections.Counter()
    for p in pats:
        for x in p[1]:
            inv[x[1] if x[0] != "D" else ("q", x[1])] += 1
    print("min weight", w, "witness index tuples", len(wits), "distinct patterns", len(pats))
    print("types", dict(typ))
    print("starts", [int(t.min()) - 1 for t in tau])
    print("involved", inv.most_common(20))
    for p in sorted(pats, key=repr)[:30]:
        print(p)
