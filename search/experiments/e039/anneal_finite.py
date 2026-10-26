"""E-039 heuristic search (simulated annealing) for a non-wrapping N(S) schedule whose exactly-R-round memory
experiment has no undetectable logical of weight <= 3 (finite.mechs, both bases).  Moves: swap the layers of two
CNOTs of one check, or move one CNOT to a free layer of its check; illegal proposals (model.legal) rejected.
Score = 1000 * #weight-<=2 witnesses or #weight-3 witnesses (limit 3000).  Heuristic only.
usage: uv run python -m search.experiments.e039.anneal_finite --S 7 --R 1 --start s.json --hours 1 --seed 1"""
import argparse
import json
import math
import random
import time

from search.experiments.e036_audit.core import min_weight_le
from search.experiments.e038.model import Sched, legal
from search.experiments.e039 import finite

OUT = "results/E-039-bb18-pipe"


def score(s, R):
    tot = 0
    worst = 9
    res = []
    for b in "ZX":
        w, wits = min_weight_le(finite.mechs(s, b, R), 3, want_all=True, limit=3000)
        if w is not None:
            res.append((w, len(wits)))
    if not res:
        return 0
    wmin = min(w for w, _ in res)
    n = sum(c for w, c in res if w == wmin)
    return n * (1000 if wmin <= 2 else 1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--S", type=int, default=7)
    ap.add_argument("--R", type=int, default=1)
    ap.add_argument("--start", required=True)
    ap.add_argument("--hours", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--T0", type=float, default=2.0)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    s = Sched.from_json(json.load(open(a.start)))
    cur = score(s, a.R)
    best = cur
    tag = f"annealF_N{a.S}_R{a.R}_s{a.seed}"
    log = open(f"{OUT}/{tag}.log", "a")
    t0 = time.time()
    it = 0
    while time.time() - t0 < a.hours * 3600:
        it += 1
        T = a.T0 * (1 - (time.time() - t0) / (a.hours * 3600)) + 0.05
        t = Sched(s.variant, s.P, s.pi, s.mu, s.tau)
        k = rng.choice(s.ks)
        if rng.random() < 0.6:
            x, y = rng.sample(range(6), 2)
            t.tau[(k, x)], t.tau[(k, y)] = t.tau[(k, y)], t.tau[(k, x)]
        else:
            used = {t.tau[(k, z)] for z in range(6)}
            free = [l for l in range(1, a.S + 1) if l not in used]
            if not free:
                continue
            t.tau[(k, rng.randrange(6))] = rng.choice(free)
        if not legal(t)[0]:
            continue
        sc = score(t, a.R)
        if sc <= cur or rng.random() < math.exp(-(sc - cur) / T):
            s, cur = t, sc
            if cur < best:
                best = cur
                json.dump(s.to_json(), open(f"{OUT}/{tag}_best.json", "w"))
                log.write(json.dumps({"it": it, "best": best, "sec": round(time.time() - t0)}) + "\n")
                log.flush()
            if cur == 0:
                json.dump(s.to_json(), open(f"{OUT}/found_{tag}.json", "w"))
                log.write(json.dumps({"result": "FOUND", "it": it}) + "\n")
                break
    log.write(json.dumps({"result": "END", "best": best, "it": it}) + "\n")
