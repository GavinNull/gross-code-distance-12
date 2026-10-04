"""三色着色的快速筛选（E-010，lead）。

背景：在 BB108 上，按 x 方向区分颜色的着色（h=(1,0),(1,1),(1,2)）里，MILP 在 300 s 内既找不到权重 ≤ T-1 的见证、
也证明不了不存在（全部 time_limit_undecided），原版 colour_search 因此在“无法判定”上耗尽时间。
策略改为两段：
  1. 筛选（本脚本）：跳过逐颜色类检验，直接枚举全部合法三色组合；每个组合只给 MILP 一个短时限去**找**权重 ≤ T-1 的
     逻辑错误。找到 = 淘汰（这是严格的上界证据）；找不到 = 候选（不是证明）。每个组合一行日志，结果实时写盘。
  2. 证明：只对少数候选投入长时限、对称性破缺的下界求解（另行进行）。

    PYTHONPATH=. uv run python -m search.noninterleaved.colour_screen --code "[[108,8,10]]" --kind X --target 10 \
        --homs 1 2 3 --time-limit 20 --workers 6
"""
from __future__ import annotations

import argparse
import json
import time
from multiprocessing import Pool

from search.noninterleaved.colour_search import S3, homomorphisms, order_terms, proper
from search.noninterleaved.ext import extended_matrices, residual_supports
from search.noninterleaved.heur import heur_min
from search.noninterleaved.run import HL, OUT, _solve, get_code, neighbours, tag
from search.noninterleaved.uniform_search import classes, single_values


def _heur_job(job):
    """启发式找错（BP-OSD 随机 η + LNS）。找到 ≤ cap 即淘汰；返回与 _solve 相同的字段。"""
    import time as _t
    t0 = _t.time()
    He, Le, _ = extended_matrices(job["H"], job["L"], job["sups"])
    w, x, info = heur_min(He, Le, trials=job["trials"], seed=job["seed"], stop_at=job["cap"])
    return {"key": job["key"], "upper": (w if (w is not None and w <= job["cap"]) else None),
            "best_found": w, "status": "witness_found" if (w is not None and w <= job["cap"]) else "no_witness_found",
            "seconds": _t.time() - t0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", default="[[108,8,10]]")
    ap.add_argument("--kind", default="X")
    ap.add_argument("--target", type=int, required=True)
    ap.add_argument("--homs", type=int, nargs="+", required=True)
    ap.add_argument("--time-limit", type=float, default=20)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--method", choices=["milp", "heur"], default="heur")
    ap.add_argument("--trials", type=int, default=300)
    a = ap.parse_args()

    code, css = get_code(a.code)
    H, L = HL(css, a.kind)
    sv = single_values(a.code)[a.kind]
    rep = classes(code, css, a.kind)
    blocks = [(pi, sg) for pi in S3 for sg in S3]
    ok = [b for b in blocks if (sv[rep[tuple(order_terms(a.kind, *b))]][1] or 99) >= a.target]
    HM = homomorphisms(code)
    base = OUT / f"colourscreen_{a.method}_{tag(a.code)}_{a.kind}_T{a.target}"
    out_path = base.with_suffix(".jsonl")
    fh = open(f"{base}.log", "a")

    def log(msg):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        fh.write(line + "\n")
        fh.flush()

    jobs = []
    for hi in a.homs:
        col = HM[hi]["colour"]
        hkey = f"{HM[hi]['alpha']},{HM[hi]['beta']}"
        n_proper = 0
        for b0 in ok:
            for b1 in ok:
                for b2 in ok:
                    obc = {c: order_terms(a.kind, *b) for c, b in enumerate((b0, b1, b2))}
                    if not proper(code, a.kind, col, obc):
                        continue
                    n_proper += 1
                    sups = [s for i in range(code.n2) for s in residual_supports([neighbours(code, a.kind, i, t)
                                                                                  for t in obc[col[i]]])]
                    jobs.append({"H": H, "L": L, "sups": sups, "cap": a.target - 1, "tl": a.time_limit,
                                 "solver": "feas", "trials": a.trials, "seed": 0,
                                 "key": [hkey, [[list(x) for x in b] for b in (b0, b1, b2)]]})
        log(f"h={hkey}: {n_proper} proper triples (from {len(ok)} block orders passing the single bound)")
    log(f"total {len(jobs)} triples, time limit {a.time_limit}s each, {a.workers} workers")
    n = killed = cand = 0
    with Pool(a.workers) as p, out_path.open("a") as fo:
        for r in p.imap_unordered(_heur_job if a.method == "heur" else _solve, jobs):
            n += 1
            rec = {k: r.get(k) for k in ("key", "status", "upper", "best_found", "seconds")}
            fo.write(json.dumps(rec) + "\n")
            fo.flush()
            if r["upper"] is not None:
                killed += 1
            else:
                cand += 1
                log(f"CANDIDATE {r['key']} status={r['status']} {r['seconds']:.0f}s")
            if n % 25 == 0:
                log(f"progress {n}/{len(jobs)}: killed (witness <= {a.target - 1}) {killed}, candidates {cand}")
    log(f"done: {n} triples, killed {killed}, candidates {cand}")


if __name__ == "__main__":
    main()
