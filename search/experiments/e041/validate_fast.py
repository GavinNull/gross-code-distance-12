"""E-041: validate fast.count / fast.viol against the audited e038 model (Bulk.mechs, legal / legal2.legal_any).
For random W9 / Mg8 schedules: (n1, n2, n3) from fast.count(W) must equal a pure-python count over the deduplicated
Bulk.mechs(W) mechanism set; legality must agree with legal2.legal_any.
usage: uv run python -m search.experiments.e041.validate_fast --n 40"""
import argparse
import itertools
import json

import numpy as np

from search.experiments.e038.model import Bulk
from search.experiments.e039.legal2 import legal_any
from search.experiments.e041.fast import count, sched_from_tau, viol
from search.experiments.e041.rand import random_legal


def ref_count(s, W):
    out = [0, 0, 0]
    for b in ("Z", "X"):
        ms = {(d, o) for d, o, _ in Bulk(s, b, W).mechs()}
        ms = sorted(m for m in ms if m != (0, 0))
        out[0] += sum(1 for d, o in ms if d == 0 and o)
        ms = [m for m in ms if m[0] != 0]
        by = {}
        for i, (d, o) in enumerate(ms):
            by.setdefault(d, []).append(i)
        for lst in by.values():
            out[1] += sum(1 for a, c in itertools.combinations(lst, 2) if ms[a][1] != ms[c][1])
        for i in range(len(ms)):
            for j in range(i + 1, len(ms)):
                x = ms[i][0] ^ ms[j][0]
                if x == 0:
                    continue
                oo = ms[i][1] ^ ms[j][1]
                out[2] += sum(1 for k in by.get(x, []) if k > j and ms[k][1] != oo)
    return tuple(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=5)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    res = {"ok": 0, "bad": 0, "legal_mismatch": 0, "illegal_tested": 0}
    for it in range(a.n):
        P, merged = (9, False) if it % 2 == 0 else (8, True)
        tau = random_legal(rng, P)
        if tau is None:
            continue
        s = sched_from_tau(tau, P)
        if not legal_any(s, merged)[0]:
            res["legal_mismatch"] += 1
            print("legal mismatch", legal_any(s, merged))
        for W in (3, 4):
            c1, c2 = count(tau, P, W), ref_count(s, W)
            if c1 == c2:
                res["ok"] += 1
            else:
                res["bad"] += 1
                print("MISMATCH", P, W, c1, c2)
        # perturbed (possibly illegal) schedule: viol == 0  <=>  legal_any
        t2 = tau.copy()
        k = int(rng.integers(14))
        a_, b_ = rng.choice(6, 2, replace=False)
        t2[k, a_], t2[k, b_] = t2[k, b_], t2[k, a_]
        s2 = sched_from_tau(t2, P)
        res["illegal_tested"] += 1
        if (viol(t2, P) == 0) != legal_any(s2, merged)[0]:
            res["legal_mismatch"] += 1
            print("legal mismatch (perturbed)", viol(t2, P), legal_any(s2, merged))
        print(it, P, count(tau, P, 4), flush=True)
    print(json.dumps(res))
    with open("results/E-041-bb18-p9/validate_fast.jsonl", "a") as f:
        f.write(json.dumps({**res, "n": a.n, "seed": a.seed}) + "\n")
