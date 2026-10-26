"""E-039 heuristic search for a d_circ = 4 schedule in W(P) / Mg(P): simulated annealing on legal schedules.
State: a legal Sched (legal2.legal_any).  Moves: swap the times of two CNOTs of one check; move one CNOT to a free
time inside the check's window (window may grow up to the class bound by moving pi / mu); shift a whole check by +-1.
Illegal proposals are rejected.  Score = 1000 * #weight-2 bulk witnesses (if any) else #weight-3 bulk witnesses
(both bases, faults in W = 4 rounds, e038 model.bulk_min, limit 3000).  Score 0 -> re-check with W = 12 -> FOUND.
usage: uv run python -m search.experiments.e039.anneal W 9 --start results/.../start.json --hours 2 --seed 1"""
import argparse
import json
import math
import random
import time

from search.experiments.e036_audit.core import support
from search.experiments.e038.model import Sched, bulk_min
from search.experiments.e039.legal2 import legal_any

OUT = "results/E-039-bb18-pipe"


def score(s):
    w, wits = bulk_min(s, 3, W=4, want_all=True, limit=3000)
    if w is None:
        return 0
    return 1000 * len(wits) if w <= 2 else len(wits)


def propose(s, rng, merged):
    P = s.P
    gap = P if merged else P - 1
    t = Sched(s.variant, P, s.pi, s.mu, s.tau)
    k = rng.choice(s.ks)
    m = rng.random()
    if m < 0.5:
        a, b = rng.sample(range(6), 2)
        t.tau[(k, a)], t.tau[(k, b)] = t.tau[(k, b)], t.tau[(k, a)]
    elif m < 0.85:
        a = rng.randrange(6)
        used = {t.tau[(k, x)] for x in range(6)}
        lo = t.mu[k] - gap + 1   # pi >= mu - gap  ->  tau >= mu - gap + 1 ; window can slide
        cand = [x for x in range(min(used) - 2, max(used) + 3) if x not in used]
        x = rng.choice(cand)
        t.tau[(k, a)] = x
        ts = [t.tau[(k, y)] for y in range(6)]
        t.pi[k] = min(ts) - 1
        t.mu[k] = max(ts) + 1
        if t.mu[k] - t.pi[k] > gap:
            return None
        # keep pi in 0..P-1 by relabelling the instance
        sh = (t.pi[k] // P) * P
        if sh:
            t.pi[k] -= sh
            t.mu[k] -= sh
            for y in range(6):
                t.tau[(k, y)] -= sh
    else:
        d = rng.choice((-1, 1))
        t.pi[k] += d
        t.mu[k] += d
        for y in range(6):
            t.tau[(k, y)] += d
        sh = (t.pi[k] // P) * P
        if sh:
            t.pi[k] -= sh
            t.mu[k] -= sh
            for y in range(6):
                t.tau[(k, y)] -= sh
    if not legal_any(t, merged)[0]:
        return None
    return t


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cls")
    ap.add_argument("P", type=int)
    ap.add_argument("--start", required=True)
    ap.add_argument("--hours", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--T0", type=float, default=3.0)
    a = ap.parse_args()
    merged = a.cls == "Mg"
    rng = random.Random(a.seed)
    s = Sched.from_json(json.load(open(a.start)))
    assert s.P == a.P and legal_any(s, merged)[0]
    cur = score(s)
    best, bests = cur, s
    tag = f"anneal_{a.cls}{a.P}_s{a.seed}"
    log = open(f"{OUT}/{tag}.log", "a")
    t0 = time.time()
    it = acc = 0
    while time.time() - t0 < a.hours * 3600:
        it += 1
        T = a.T0 * (1 - (time.time() - t0) / (a.hours * 3600)) + 0.05
        t = propose(s, rng, merged)
        if t is None:
            continue
        sc = score(t)
        if sc <= cur or rng.random() < math.exp(-(sc - cur) / T):
            s, cur = t, sc
            acc += 1
            if cur < best:
                best, bests = cur, s
                log.write(json.dumps({"it": it, "best": best, "sec": round(time.time() - t0)}) + "\n")
                log.flush()
                json.dump(bests.to_json(), open(f"{OUT}/{tag}_best.json", "w"))
            if cur == 0:
                w12 = bulk_min(s, 3, W=12)[0]
                if w12 is None:
                    json.dump(s.to_json(), open(f"{OUT}/found_{tag}.json", "w"))
                    log.write(json.dumps({"result": "FOUND", "it": it}) + "\n")
                    print("FOUND", flush=True)
                    break
        if it % 500 == 0:
            log.write(json.dumps({"it": it, "acc": acc, "cur": cur, "best": best, "T": round(T, 2),
                                  "sec": round(time.time() - t0)}) + "\n")
            log.flush()
    log.write(json.dumps({"result": "END", "best": best, "it": it}) + "\n")
