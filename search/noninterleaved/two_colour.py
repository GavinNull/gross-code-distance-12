"""E-013：BB108 的 y 奇偶两色 LRC（偶数行一个块顺序、奇数行一个块顺序），X 侧与 Z 侧都穷举。lead。

由 E-011 的见证构成推出（权重 8 见证由 y 与 y+3 的校验拼成，y 奇偶着色把它们分开），E-012 的六色穷举里
幸存者全部带有“按 y 奇偶区分块顺序”的特征，其中包含与 x 无关的纯两色状态。本脚本系统地穷举两色空间：
  全部 (偶行块顺序, 奇行块顺序) 中能通过单检查上限、且合法的组合 → 启发式初筛（2 种子 × 300 次）
  → 达到 target 的再用 3 个新种子 × 1000 次复核。

    PYTHONPATH=. uv run python -m search.noninterleaved.two_colour --kind Z --workers 8
"""
from __future__ import annotations

import argparse
import json
import time
from multiprocessing import Pool

from search.noninterleaved.colour_search import S3, order_terms, proper
from search.noninterleaved.ext import extended_matrices, residual_supports
from search.noninterleaved.heur import heur_min
from search.noninterleaved.run import HL, OUT, get_code, neighbours
from search.noninterleaved.uniform_search import classes, single_values

NAME, M, TARGET = "[[108,8,10]]", 6, 10
_C = {}


def ctx(kind):
    if kind not in _C:
        code, css = get_code(NAME)
        H, L = HL(css, kind)
        sv = single_values(NAME)[kind]
        rep = classes(code, css, kind)
        blocks = [(pi, sg) for pi in S3 for sg in S3]
        ok = [b for b in blocks if (sv[rep[tuple(order_terms(kind, *b))]][1] or 99) >= TARGET]
        colour = tuple((i % M) % 2 for i in range(code.n2))
        _C[kind] = dict(code=code, H=H, L=L, ok=ok, colour=colour)
    return _C[kind]


def weight(args):
    kind, state, seeds, trials = args
    c = ctx(kind)
    obc = {k: order_terms(kind, *c["ok"][s]) for k, s in enumerate(state)}
    sups = [s for i in range(c["code"].n2)
            for s in residual_supports([neighbours(c["code"], kind, i, t) for t in obc[c["colour"][i]]])]
    He, Le, _ = extended_matrices(c["H"], c["L"], sups)
    best = None
    for sd in seeds:
        w, _, _ = heur_min(He, Le, trials=trials, seed=sd, lns_starts=8 if trials <= 300 else 16, stop_at=TARGET - 1)
        best = w if best is None or (w is not None and w < best) else best
        if best is not None and best < TARGET:
            break
    return kind, state, best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", default="Z")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    c = ctx(a.kind)
    nok = len(c["ok"])
    states = [(e, o) for e in range(nok) for o in range(nok)
              if proper(c["code"], a.kind, c["colour"], {0: order_terms(a.kind, *c["ok"][e]),
                                                        1: order_terms(a.kind, *c["ok"][o])})]
    logf = open(OUT / f"e013_two_colour_{a.kind}.log", "a")
    recf = open(OUT / f"e013_two_colour_{a.kind}.jsonl", "a")

    def log(m):
        line = f"[{time.strftime('%H:%M:%S')}] {m}"
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    log(f"kind {a.kind}: {nok} block orders pass single bound; {len(states)} proper two-colour states")
    with Pool(a.workers) as p:
        cands = []
        for k, st, w in p.imap_unordered(weight, [(a.kind, s, (0, 1), 300) for s in states]):
            recf.write(json.dumps({"stage": "screen", "state": st, "w": w}) + "\n")
            recf.flush()
            if w is not None and w >= TARGET:
                cands.append(st)
        log(f"screen: {len(cands)}/{len(states)} reach {TARGET}")
        res = {s: [] for s in cands}
        for k, st, w in p.imap_unordered(weight, [(a.kind, s, (sd,), 1000) for s in cands for sd in (11, 12, 13)]):
            res[st].append(w)
            recf.write(json.dumps({"stage": "harden", "state": st, "w": w}) + "\n")
            recf.flush()
        surv = [s for s, v in res.items() if all(x is not None and x >= TARGET for x in v)]
        for s in surv:
            log(f"SURVIVOR {s} blocks even={c['ok'][s[0]]} odd={c['ok'][s[1]]}")
        log(f"done: {len(states)} states, {len(cands)} hardened, {len(surv)} survivors")
        (OUT / f"e013_two_colour_{a.kind}_survivors.json").write_text(
            json.dumps([{"state": s, "even": c["ok"][s[0]], "odd": c["ok"][s[1]]} for s in surv]))


if __name__ == "__main__":
    main()
