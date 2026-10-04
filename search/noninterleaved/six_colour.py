"""E-012：BB108 X 侧的六色着色（x mod 3, y mod 2）搜索。lead。

状态：6 个颜色各自的块顺序 (pi, sigma)，取自能通过单检查上限的块顺序；必须合法（同一槽位不重复使用数据比特）。
评估：启发式找错器（heur_min）在若干种子上的最短权重（越大越好）。
  - 爬山（--mode climb）：每步并行评估一批合法邻居（改一个颜色的块顺序），取最好；停滞若干步后随机重启。
  - 随机（--mode random）：同样的评估预算下纯随机采样合法状态，作为对照。
达到 target 的状态用 3 个新种子 × 1000 次试验加大力度复核；扛住才记为 CANDIDATE。

    PYTHONPATH=. uv run python -m search.noninterleaved.six_colour --mode climb --evals 400 --workers 8
"""
from __future__ import annotations

import argparse
import json
import random
import time
from multiprocessing import Pool

from search.noninterleaved.colour_search import S3, order_terms, proper
from search.noninterleaved.ext import extended_matrices, residual_supports
from search.noninterleaved.heur import heur_min
from search.noninterleaved.run import HL, OUT, get_code, neighbours
from search.noninterleaved.uniform_search import classes, single_values

NAME, KIND, M = "[[108,8,10]]", "X", 6
_C = {}


def ctx():
    if not _C:
        code, css = get_code(NAME)
        H, L = HL(css, KIND)
        sv = single_values(NAME)[KIND]
        rep = classes(code, css, KIND)
        blocks = [(pi, sg) for pi in S3 for sg in S3]
        ok = [b for b in blocks if (sv[rep[tuple(order_terms(KIND, *b))]][1] or 99) >= 10]
        colour = tuple(((i // M) % 3) * 2 + ((i % M) % 2) for i in range(code.n2))
        _C.update(code=code, H=H, L=L, ok=ok, colour=colour)
    return _C


def is_proper(state):
    c = ctx()
    return proper(c["code"], KIND, c["colour"], {k: order_terms(KIND, *c["ok"][s]) for k, s in enumerate(state)})


def weight(args):
    state, seeds, trials = args
    c = ctx()
    obc = {k: order_terms(KIND, *c["ok"][s]) for k, s in enumerate(state)}
    sups = [s for i in range(c["code"].n2)
            for s in residual_supports([neighbours(c["code"], KIND, i, t) for t in obc[c["colour"][i]]])]
    He, Le, _ = extended_matrices(c["H"], c["L"], sups)
    best = None
    for sd in seeds:
        w, _, _ = heur_min(He, Le, trials=trials, seed=sd, lns_starts=8 if trials <= 300 else 16, stop_at=9)
        best = w if best is None or (w is not None and w < best) else best
        if best is not None and best <= 9:
            break
    return state, best


def random_proper(rng, nok):
    while True:
        s = tuple(rng.randrange(nok) for _ in range(6))
        if is_proper(s):
            return s


def neighbours_of(state, rng, nok, k):
    out = set()
    tries = 0
    while len(out) < k and tries < 2000:
        tries += 1
        s = list(state)
        s[rng.randrange(6)] = rng.randrange(nok)
        s = tuple(s)
        if s != state and is_proper(s):
            out.add(s)
    return list(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["climb", "random"], default="climb")
    ap.add_argument("--evals", type=int, default=400)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--patience", type=int, default=4)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    nok = len(ctx()["ok"])
    tag = f"e012_{a.mode}_s{a.seed}"
    logf = open(OUT / f"{tag}.log", "a")
    recf = open(OUT / f"{tag}.jsonl", "a")

    def log(msg):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    log(f"mode {a.mode}, {nok} block orders, budget {a.evals} evals, workers {a.workers}")
    used = 0
    hist = {}
    best_seen = None
    cand = None
    screen = ((0, 1), 300)
    with Pool(a.workers) as p:
        def evaluate(states):
            nonlocal used, best_seen
            todo = [s for s in states if s not in hist]
            for st, w in p.imap_unordered(weight, [(s, *screen) for s in todo]):
                used += 1
                hist[st] = w
                recf.write(json.dumps({"n": used, "state": st, "w": w}) + "\n")
                recf.flush()
                if w is not None and (best_seen is None or w > best_seen):
                    best_seen = w
                    log(f"eval {used}: new best screen weight {w} at {st}")
            return [(s, hist[s]) for s in states]

        def harden(state):
            res = p.map(weight, [(state, (s,), 1000) for s in (11, 12, 13)])
            ws = [w for _, w in res]
            return min(w for w in ws if w is not None), ws

        cur = None
        stall = 0
        while used < a.evals and cand is None:
            if a.mode == "random":
                batch = [random_proper(rng, nok) for _ in range(a.workers)]
            else:
                if cur is None or stall >= a.patience:
                    cur = random_proper(rng, nok)
                    evaluate([cur])
                    stall = 0
                batch = neighbours_of(cur, rng, nok, a.workers)
            scored = evaluate(batch)
            for st, w in sorted(scored, key=lambda x: -(x[1] or 0)):
                if w is not None and w >= 10:
                    hw, ws = harden(st)
                    log(f"harden {st}: weights {ws}")
                    if hw >= 10:
                        cand = st
                        log(f"CANDIDATE {st} ({[ctx()['ok'][s] for s in st]})")
                        break
                    hist[st] = hw
            if a.mode == "climb" and cand is None:
                top = max((st for st, _ in scored), key=lambda st: hist.get(st) or 0) if scored else None
                if top is not None and (hist.get(top) or 0) > (hist.get(cur) or 0):
                    cur, stall = top, 0
                else:
                    stall += 1
    log(f"done: {used} evals, best screen weight {best_seen}, candidate {cand}")


if __name__ == "__main__":
    main()
