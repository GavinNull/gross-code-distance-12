"""对筛选出的候选三色组合加大搜索力度（E-010，lead）：多种子、更多试验。任何一次找到 ≤ T-1 即淘汰。

    PYTHONPATH=. uv run python -m search.noninterleaved.colour_harden --code "[[108,8,10]]" --kind X --target 10 \
        --seeds 1 2 3 --trials 1000 --workers 4
读取 colourscreen_heur_<code>_<kind>_T<target>.jsonl 里 best_found ≥ target 的组合；按“颜色循环”（x 方向平移）去重。
"""
from __future__ import annotations

import argparse
import json
import time
from multiprocessing import Pool

from search.noninterleaved.colour_search import homomorphisms, order_terms
from search.noninterleaved.ext import extended_matrices, residual_supports
from search.noninterleaved.heur import heur_min
from search.noninterleaved.run import HL, OUT, get_code, neighbours, tag

_CTX = {}


def _job(args):
    name, kind, target, hkey, triple, seed, trials = args
    if (name, kind) not in _CTX:
        code, css = get_code(name)
        _CTX[(name, kind)] = (code, *HL(css, kind), {f"{h['alpha']},{h['beta']}": h["colour"]
                                                       for h in homomorphisms(code)})
    code, H, L, cols = _CTX[(name, kind)]
    col = cols[hkey]
    obc = {c: order_terms(kind, tuple(b[0]), tuple(b[1])) for c, b in enumerate(triple)}
    sups = [s for i in range(code.n2) for s in residual_supports([neighbours(code, kind, i, t) for t in obc[col[i]]])]
    He, Le, _ = extended_matrices(H, L, sups)
    t0 = time.time()
    w, x, info = heur_min(He, Le, trials=trials, seed=seed, lns_starts=16, stop_at=target - 1)
    return {"key": [hkey, triple], "seed": seed, "best_found": w, "seconds": time.time() - t0}


def canon(triple):
    """颜色循环（平移 x→x+1 把颜色 c 变成 c+1）下的代表元。"""
    rots = [tuple(map(lambda b: (tuple(b[0]), tuple(b[1])), triple[i:] + triple[:i])) for i in range(3)]
    return min(rots)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", default="[[108,8,10]]")
    ap.add_argument("--kind", default="X")
    ap.add_argument("--target", type=int, required=True)
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--trials", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    src = OUT / f"colourscreen_heur_{tag(a.code)}_{a.kind}_T{a.target}.jsonl"
    cands, seen = [], set()
    for line in open(src):
        r = json.loads(line)
        if r["best_found"] is not None and r["best_found"] >= a.target:
            k = (r["key"][0], canon(r["key"][1]))
            if k not in seen:
                seen.add(k)
                cands.append((r["key"][0], [list(map(list, b)) for b in k[1]]))
    out = OUT / f"colourharden_{tag(a.code)}_{a.kind}_T{a.target}.jsonl"
    print(f"{len(cands)} candidate classes (after colour-rotation dedupe); seeds {a.seeds}; trials {a.trials}", flush=True)
    jobs = [(a.code, a.kind, a.target, h, t, s, a.trials) for h, t in cands for s in a.seeds]
    killed = {}
    with Pool(a.workers) as p, out.open("a") as fo:
        for r in p.imap_unordered(_job, jobs):
            fo.write(json.dumps(r) + "\n")
            fo.flush()
            k = json.dumps(r["key"])
            if r["best_found"] is not None and r["best_found"] < a.target:
                killed[k] = r["best_found"]
                print(f"KILLED {r['key']} seed {r['seed']} weight {r['best_found']} ({r['seconds']:.0f}s)", flush=True)
    surv = [c for c in cands if json.dumps([c[0], c[1]]) not in killed]
    print(f"done: {len(cands)} classes, killed {len(killed)}, surviving {len(surv)}", flush=True)
    for c in surv:
        print("SURVIVOR", json.dumps(c), flush=True)


if __name__ == "__main__":
    main()
