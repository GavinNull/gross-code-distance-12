"""E-020 classical control: random legal + deterministic per-check schedules (period P), scored by the number of
modelled weight-11 logicals (both kinds, d10 r21 single-hook; or all modelled types) that lift in the bulk frame
model.  Sampler: SAT for a first legal schedule (lazy determinism), then a random walk: pick a random check, a random
option; accept if the schedule stays legal and deterministic (checked directly).  No objective-guided moves.

    PYTHONPATH=.:tests uv run python -m search.experiments.e020.control --P 9 --sec 3600
"""
from __future__ import annotations

import argparse
import json
import random
import time

from pysat.solvers import Cadical153

from search.experiments.e020.cegar import bellman_ford, prep_logicals, schedule_times
from search.experiments.e020.plegal import build, checks

OUT = "results/E-020-gross-perchk-pipeline"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--P", type=int, default=9)
    ap.add_argument("--sec", type=float, default=3600)
    ap.add_argument("--seed", type=int, default=20261008)
    ap.add_argument("--types", default="single")
    a = ap.parse_args()
    rng = random.Random(a.seed)
    P = a.P
    L, _ = prep_logicals("XZ", a.types)
    C, O, x, cnf, pool = build(P, lazy_det=True)
    dett = pool.det_table
    t0 = time.time()
    # start: a legal deterministic schedule from the SAT enumeration (plegal_P<P>.json) if available
    import os
    start = f"{OUT}/plegal_P{P}.json"
    if os.path.exists(start):
        sols = json.load(open(start))["sols"]
        idx = {tuple(o): k for k, o in enumerate(O)}
        sv = [idx[tuple(o)] for o in rng.choice(sols)]
    with Cadical153(bootstrap_with=cnf) as S:
        while not os.path.exists(start):
            assert S.solve()
            pos = set(l for l in S.get_model() if l > 0)
            sv = [next(k for k in range(len(O)) if x[ci][k] in pos) for ci in range(len(C))]
            T = schedule_times(sv, O)
            bad = 0
            for (ca, cc), (ga, gc, (pau, pav, pcu, pcv), _) in dett.items():
                g1 = (T[(ca, pau)], T[(ca, pav)]); g2 = (T[(cc, pcu)], T[(cc, pcv)])
                if (g1[0] - g2[0]) // P != (g1[1] - g2[1]) // P:
                    S.add_clause([-ga[g1], -gc[g2]]); bad += 1
            if not bad:
                break
    print(f"first legal det schedule {time.time() - t0:.0f}s", flush=True)
    chk = checks()
    on = [[] for _ in range(144)]
    for ci, (_, _, o) in enumerate(chk):
        for p, q in enumerate(o):
            on[q].append((ci, p))
    pairs_of = {}
    for (ca, cc), v in dett.items():
        pairs_of.setdefault(ca, []).append((ca, cc, v[2])); pairs_of.setdefault(cc, []).append((ca, cc, v[2]))

    def ok_change(sv, ci, k):
        old = sv[ci]; sv[ci] = k
        good = True
        for p, q in enumerate(chk[ci][2]):
            ts = [O[sv[cj]][pj] % P for cj, pj in on[q]]
            if len(set(ts)) != 6:
                good = False; break
        if good:
            for ca, cc, (pau, pav, pcu, pcv) in pairs_of[ci]:
                oa, oc = O[sv[ca]], O[sv[cc]]
                if (oa[pau] - oc[pcu]) // P != (oa[pav] - oc[pcv]) // P:
                    good = False; break
        if not good:
            sv[ci] = old
        return good

    best, hist, nev, acc = None, [], 0, 0
    while time.time() - t0 < a.sec:
        for _ in range(200):
            ci = rng.randrange(len(C)); k = rng.randrange(len(O))
            acc += ok_change(sv, ci, k)
        T = schedule_times(sv, O)
        nl = sum(bellman_ford(cons, T, P) is not None for _, _, _, cons in L)
        nev += 1
        hist.append(nl)
        if best is None or nl < best[0]:
            best = (nl, [list(O[k]) for k in sv])
            print(f"eval {nev}: lifting {nl}/{len(L)} (best) accepted moves {acc} {time.time() - t0:.0f}s", flush=True)
    res = {"P": P, "types": a.types, "modelled": len(L), "evals": nev, "accepted_moves": acc, "best": best[0],
           "best_sched": best[1], "hist_min_mean_max": [min(hist), sum(hist) / len(hist), max(hist)]}
    print({k: v for k, v in res.items() if k != "best_sched"}, flush=True)
    json.dump(res, open(f"{OUT}/control_P{P}.json", "w"))


if __name__ == "__main__":
    main()
