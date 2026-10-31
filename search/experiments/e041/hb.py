"""E-041 heat-bath / best-response search on single checks (heuristic).

Kernel: for one check k, enumerate EVERY placement of its 6 CNOTs inside 7 consecutive layers (window start 1..P,
empty slot 0..6, 720 term orders = 45,360 (P = 9) placements), keep the legal ones (others fixed), score each with the
exact bulk counter (cost = B * n2 + n3, both bases, W fault rounds), and pick one by heat-bath sampling
p ~ exp(-cost / T) (T -> 0: best response).  Outer loop: sweeps over random checks with temperature cycling; a kick
(random legal perturbation of 1-3 checks via fast.viol-repair) when a sweep gives no improvement.  A state with
cost 0 is re-checked with W = 6 and e038.model.bulk_min(W = 12) -> results/E-041-bb18-p9/found_*.json.
usage: uv run python -m search.experiments.e041.hb --P 9 --start random --seed 1 --hours 1"""
import argparse
import itertools
import json
import math
import os
import time

import numba as nb
import numpy as np

from search.experiments.e041.fast import (NK, ONQ_A, ONQ_K, ONQ_N, PAIR_AX, PAIR_AZ, PAIR_K, PAIR_N, SUP, TABLES,
                                          count_both, legal_viol, sched_from_tau, viol)
from search.experiments.e041.rand import mutate, normalise
from search.experiments.e041.sa import start_state

OUT = "results/E-041-bb18-p9"
PERMS = np.array(list(itertools.permutations(range(6))), np.int64)


@nb.njit(cache=True)
def enum_check(tau, k, P, W, B, tz, tx, sup, perms, onq_n, onq_k, onq_a, pk, pn, pax, paz):
    """all legal placements of check k: returns (times[n, 6], cost[n], n2[n])."""
    nconf = P * 7 * perms.shape[0]
    T = np.zeros((nconf, 6), np.int64)
    C = np.zeros(nconf, np.float64)
    N2 = np.zeros(nconf, np.int64)
    old = tau[k].copy()
    n = 0
    slots = np.zeros(6, np.int64)
    for s in range(P):
        for e in range(7):
            m = 0
            for x in range(7):
                if x != e:
                    slots[m] = x
                    m += 1
            for pi in range(perms.shape[0]):
                for a in range(6):
                    tau[k, a] = s + 1 + slots[perms[pi, a]]
                if legal_viol(tau, P, 6, onq_n, onq_k, onq_a, pk, pn, pax, paz) != 0:
                    continue
                n1, n2, n3 = count_both(tau, P, W, tz, tx, sup)
                T[n] = tau[k]
                C[n] = B * n2 + n3 + 1e6 * n1
                N2[n] = n2
                n += 1
    tau[k] = old
    return T[:n], C[:n], N2[:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--P", type=int, default=9)
    ap.add_argument("--start", default="random")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--hours", type=float, default=1.0)
    ap.add_argument("--W", type=int, default=3)
    ap.add_argument("--B", type=float, default=20.0)
    ap.add_argument("--T0", type=float, default=3.0)
    ap.add_argument("--T1", type=float, default=0.2)
    ap.add_argument("--cycle", type=int, default=60, help="check updates per temperature cycle")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    P = a.P
    rng = np.random.default_rng(a.seed)
    tz, tx = TABLES["Z"], TABLES["X"]
    tag = f"hb_P{P}_{os.path.basename(a.start).replace('.json', '')}_s{a.seed}{a.tag}"
    log = open(f"{OUT}/{tag}.log", "a")
    tau = start_state(a.start, P, rng)
    if viol(tau, P) != 0:   # repair (penalised descent on legality only)
        v = viol(tau, P)
        while v:
            k = int(rng.integers(NK))
            old = tau[k].copy()
            mutate(tau, k, rng, 7)
            v2 = viol(tau, P)
            if v2 <= v or rng.random() < 0.01:
                v = v2
            else:
                tau[k] = old
        tau = normalise(tau, P)

    def cost(t):
        n1, n2, n3 = count_both(t, P, a.W, tz, tx, SUP)
        return a.B * n2 + n3 + 1e6 * n1, n2, n3

    cur = cost(tau)
    best, btau = cur, tau.copy()
    log.write(json.dumps({"start": a.start, "args": vars(a), "cost": cur}) + "\n")
    t0 = time.time()
    step = 0
    while time.time() - t0 < a.hours * 3600:
        frac = (step % a.cycle) / a.cycle
        T = a.T0 * (a.T1 / a.T0) ** frac
        if step % a.cycle == 0 and step:
            log.write(json.dumps({"cycle": step // a.cycle, "best": best, "cur": cur, "sec": round(time.time() - t0)})
                      + "\n")
            log.flush()
            if rng.random() < 0.5:
                tau, cur = btau.copy(), best
        step += 1
        k = int(rng.integers(NK))
        Tm, C, N2 = enum_check(tau, k, P, a.W, a.B, tz, tx, SUP, PERMS, ONQ_N, ONQ_K, ONQ_A, PAIR_K, PAIR_N,
                               PAIR_AX, PAIR_AZ)
        if len(C) == 0:
            continue
        w = np.exp(-(C - C.min()) / T)
        i = int(rng.choice(len(C), p=w / w.sum()))
        tau[k] = Tm[i]
        tau = normalise(tau, P)
        cur = (float(C[i]), int(N2[i]), int(C[i] - a.B * N2[i]))
        if cur[0] < best[0]:
            best, btau = cur, tau.copy()
            log.write(json.dumps({"step": step, "best": best, "nlegal": len(C), "sec": round(time.time() - t0)}) + "\n")
            log.flush()
            json.dump({"P": P, "tau": btau.tolist(), "cost": best}, open(f"{OUT}/{tag}_best.json", "w"))
            if best[0] == 0:
                c6 = count_both(btau, P, 6, tz, tx, SUP)
                from search.experiments.e038.model import bulk_min
                w12 = bulk_min(sched_from_tau(btau, P), 3, W=12)[0]
                log.write(json.dumps({"zero": True, "W6": c6, "bulk_min_W12": w12}) + "\n")
                if c6[1] == 0 and c6[2] == 0 and w12 is None:
                    json.dump(sched_from_tau(btau, P).to_json(), open(f"{OUT}/found_{tag}.json", "w"))
                    log.write(json.dumps({"result": "FOUND", "step": step}) + "\n")
                    log.flush()
                    print("FOUND", tag, flush=True)
                    return
    log.write(json.dumps({"result": "END", "best": best, "steps": step}) + "\n")
    print(tag, "END", best, step, flush=True)


if __name__ == "__main__":
    main()
