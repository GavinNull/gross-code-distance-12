"""E-041 simulated annealing for a bulk d_circ = 4 schedule in W9 (P = 9) / Mg8 (P = 8): each check's 6 CNOTs inside
7 consecutive layers (span <= 6).  Penalty formulation: cost = A * #legality violations + B * n2 + n3, with n2 / n3 the
numbers of weight-2 / weight-3 bulk undetectable logicals (both bases, fault rounds 0..W-1; fast.py, validated against
e038.model).  Illegal intermediate states are allowed (penalised).  Cycles of geometric cooling T0 -> T1; each new cycle
restarts from the best state (prob. p_best) or keeps the current one.  A state with cost 0 is re-checked with W = 6 (fast)
and e038.model.bulk_min(W = 12) and written to results/E-041-bb18-p9/found_*.json.  Heuristic only.
usage: uv run python -m search.experiments.e041.sa --P 9 --start random --seed 1 --hours 1"""
import argparse
import json
import math
import os
import time

import numpy as np

from search.experiments.e041.fast import NK, SUP, TABLES, count_both, sched_from_tau, viol
from search.experiments.e041.rand import mutate, normalise, random_legal

OUT = "results/E-041-bb18-p9"


def start_state(name, P, rng):
    from search.experiments.e036_audit.core import checks, kunlun_schedule, support
    if name == "random":
        return random_legal(rng, P)
    if name == "kunlun":
        T, _ = kunlun_schedule("bb18")
        return np.array([T[k] for k in checks("bb18")], np.int64)
    if name.startswith("n8merge"):   # N8 (layers 1..8) with layers c, c+1 merged -> 7 layers, then repaired by SA
        c = int(name[7:]) if len(name) > 7 else int(rng.integers(1, 8))
        d = json.load(open("search/experiments/e038/bb18_n8_d4_spec.json"))
        tau = []
        for kind, key in (("X", "x_checks"), ("Z", "z_checks")):
            for row, k in zip(d[key], [k for k in checks("bb18") if k[0] == kind]):
                lay = {q: t for q, t in row["cnots"]}
                assert sorted(lay) == sorted(support(k))
                tau.append([lay[q] - (1 if lay[q] > c else 0) for q in support(k)])
        return np.array(tau, np.int64)
    d = json.load(open(name))
    from search.experiments.e038.model import Sched
    from search.experiments.e041.fast import tau_from_sched
    return normalise(tau_from_sched(Sched.from_json(d)), P)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--P", type=int, default=9)
    ap.add_argument("--start", default="random")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--hours", type=float, default=1.0)
    ap.add_argument("--W", type=int, default=3)
    ap.add_argument("--A", type=float, default=20.0)
    ap.add_argument("--B", type=float, default=20.0)
    ap.add_argument("--T0", type=float, default=4.0)
    ap.add_argument("--T1", type=float, default=0.3)
    ap.add_argument("--cycle", type=int, default=200000)
    ap.add_argument("--p_best", type=float, default=0.5)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    P, win = a.P, 7
    rng = np.random.default_rng(a.seed)
    tz, tx = TABLES["Z"], TABLES["X"]
    tag = f"sa_P{P}_{os.path.basename(a.start).replace('.json', '')}_s{a.seed}{a.tag}"
    log = open(f"{OUT}/{tag}.log", "a")

    def cost(t):
        v = viol(t, P, win - 1)
        n1, n2, n3 = count_both(t, P, a.W, tz, tx, SUP)
        return a.A * v + a.B * n2 + n3 + 1e6 * n1, v, n2, n3

    tau = start_state(a.start, P, rng)
    cur = cost(tau)
    best, btau = cur, tau.copy()
    log.write(json.dumps({"start": a.start, "args": vars(a), "cost": cur}) + "\n")
    t0 = time.time()
    it = 0
    cyc = 0
    while time.time() - t0 < a.hours * 3600:
        frac = (it % a.cycle) / a.cycle
        if it % a.cycle == 0 and it:
            cyc += 1
            if rng.random() < a.p_best:
                tau, cur = btau.copy(), best
            log.write(json.dumps({"cycle": cyc, "it": it, "best": best[1:], "bestc": best[0], "cur": cur[0],
                                  "sec": round(time.time() - t0)}) + "\n")
            log.flush()
        T = a.T0 * (a.T1 / a.T0) ** frac
        it += 1
        k = int(rng.integers(NK))
        old = tau[k].copy()
        mutate(tau, k, rng, win)
        k2 = -1
        if rng.random() < 0.15:
            k2 = int(rng.integers(NK))
            old2 = tau[k2].copy()
            mutate(tau, k2, rng, win)
        normalise(tau, P)   # canonical instance labelling (window start in 1..P): the counter needs it
        new = cost(tau)
        dc = new[0] - cur[0]
        if dc <= 0 or rng.random() < math.exp(-dc / T):
            cur = new
            if new[0] < best[0]:
                best, btau = new, normalise(tau.copy(), P)
                log.write(json.dumps({"it": it, "best": best[1:], "sec": round(time.time() - t0)}) + "\n")
                log.flush()
                json.dump({"P": P, "tau": btau.tolist(), "cost": best}, open(f"{OUT}/{tag}_best.json", "w"))
                if best[0] == 0:
                    c6 = count_both(btau, P, 6, tz, tx, SUP)
                    from search.experiments.e038.model import bulk_min
                    w12 = bulk_min(sched_from_tau(btau, P), 3, W=12)[0]
                    log.write(json.dumps({"zero": True, "W6": c6, "bulk_min_W12": w12}) + "\n")
                    if c6[1] == 0 and c6[2] == 0 and w12 is None:
                        json.dump(sched_from_tau(btau, P).to_json(), open(f"{OUT}/found_{tag}.json", "w"))
                        log.write(json.dumps({"result": "FOUND", "it": it}) + "\n")
                        log.flush()
                        print("FOUND", tag, flush=True)
                        return
        else:
            if k2 >= 0:
                tau[k2] = old2
            tau[k] = old
    log.write(json.dumps({"result": "END", "best": best, "it": it}) + "\n")
    print(tag, "END", best, it, flush=True)


if __name__ == "__main__":
    main()
