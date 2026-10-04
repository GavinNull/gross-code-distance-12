"""三色着色搜索的“流式 + 找到即停”版本（E-010，lead）。

与 colour_search.run 的算法完全相同（同一套块顺序、颜色类检验、合法三元组、MILP 可行性 cap=T-1），只改执行方式：
  - 第 2 步（单颜色类检验）每完成一个就写一行日志，并把结果缓存到 JSON，重跑时直接复用；
  - 第 3 步（三色组合检验）每完成一个就写一行日志；**一旦找到 infeasible_under_cap（即 d_ext ≥ T）就停止**，
    因为 H-004 只需要存在性；
  - 找到的组合连同块顺序写入结果文件，供之后的精确复核和电路级交叉验证使用。

    PYTHONPATH=. uv run python -m search.noninterleaved.colour_fast --code "[[108,8,10]]" --kind X --target 10 --homs 1 2 3
"""
from __future__ import annotations

import argparse
import json
import time
from multiprocessing import Pool
from pathlib import Path

from search.noninterleaved.colour_search import S3, homomorphisms, order_terms, proper
from search.noninterleaved.ext import residual_supports
from search.noninterleaved.run import HL, OUT, _solve, get_code, neighbours, tag
from search.noninterleaved.uniform_search import classes, single_values


def log(msg, fh):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    fh.write(line + "\n")
    fh.flush()


def run(name, kind, target, workers, tl, homs):
    code, css = get_code(name)
    H, L = HL(css, kind)
    sv = single_values(name)[kind]
    rep = classes(code, css, kind)
    blocks = [(pi, sg) for pi in S3 for sg in S3]
    ok_blocks = [b for b in blocks if (sv[rep[tuple(order_terms(kind, *b))]][1] or 99) >= target]
    HM = homomorphisms(code)
    base = OUT / f"colourfast_{tag(name)}_{kind}_T{target}"
    fh = open(f"{base}.log", "a")
    log(f"code {name} kind {kind} target {target}: {len(ok_blocks)}/{len(blocks)} block orders pass single bound; "
        f"{len(HM)} homomorphisms; running {homs}", fh)
    result = {"code": name, "kind": kind, "target": target, "time_limit": tl, "homs": {}}
    for hi in homs:
        hm = HM[hi]
        col = hm["colour"]
        hkey = f"{hm['alpha']},{hm['beta']}"
        cache = Path(f"{base}_h{hi}_step2.json")
        # 第 2 步
        if cache.exists():
            step2 = json.loads(cache.read_text())
            log(f"h={hkey}: step 2 loaded from cache ({len(step2)} tests)", fh)
        else:
            jobs = []
            for c in range(3):
                for b in ok_blocks:
                    o = order_terms(kind, *b)
                    sups = [s for i in range(code.n2) if col[i] == c
                            for s in residual_supports([neighbours(code, kind, i, t) for t in o])]
                    jobs.append({"H": H, "L": L, "sups": sups, "cap": target - 1, "tl": tl, "solver": "feas",
                                 "key": [c, list(b[0]), list(b[1])]})
            step2 = []
            with Pool(workers) as p:
                for r in p.imap_unordered(_solve, jobs):
                    step2.append({k: r[k] for k in ("key", "status", "upper", "seconds")})
                    log(f"h={hkey} step2 {len(step2)}/{len(jobs)} key={r['key']} status={r['status']} "
                        f"upper={r['upper']} {r['seconds']:.0f}s", fh)
            cache.write_text(json.dumps(step2))
        surv = {c: [] for c in range(3)}
        for r in step2:
            c, pi, sg = r["key"]
            if r["upper"] is None:
                surv[c].append((tuple(pi), tuple(sg)))
        triples = []
        for b0 in surv[0]:
            for b1 in surv[1]:
                for b2 in surv[2]:
                    obc = {c: order_terms(kind, *b) for c, b in enumerate((b0, b1, b2))}
                    if proper(code, kind, col, obc):
                        triples.append((b0, b1, b2))
        log(f"h={hkey}: survivors {{c: len}} = {{{', '.join(f'{c}: {len(v)}' for c, v in surv.items())}}}, "
            f"proper triples {len(triples)}", fh)
        rec = {"survivors": {c: len(v) for c, v in surv.items()}, "proper_triples": len(triples),
               "tested": [], "achieving": None}
        # 第 3 步：找到即停
        jobs = []
        for tr in triples:
            obc = {c: order_terms(kind, *b) for c, b in enumerate(tr)}
            sups = [s for i in range(code.n2) for s in residual_supports([neighbours(code, kind, i, t)
                                                                          for t in obc[col[i]]])]
            jobs.append({"H": H, "L": L, "sups": sups, "cap": target - 1, "tl": tl, "solver": "feas",
                         "key": [[list(x) for x in b] for b in tr]})
        if jobs:
            with Pool(workers) as p:
                for r in p.imap_unordered(_solve, jobs):
                    rec["tested"].append({k: r[k] for k in ("key", "status", "upper", "seconds")})
                    log(f"h={hkey} step3 {len(rec['tested'])}/{len(jobs)} status={r['status']} upper={r['upper']} "
                        f"{r['seconds']:.0f}s", fh)
                    if r["status"] == "infeasible_under_cap":
                        rec["achieving"] = r["key"]
                        log(f"h={hkey}: FOUND d_ext >= {target}: {r['key']}", fh)
                        p.terminate()
                        break
        result["homs"][hkey] = rec
        Path(f"{base}.json").write_text(json.dumps(result, indent=1))
        if rec["achieving"]:
            log(f"stop: achieving triple found for h={hkey}", fh)
            break
    log("done", fh)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", default="[[108,8,10]]")
    ap.add_argument("--kind", default="X")
    ap.add_argument("--target", type=int, required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--time-limit", type=float, default=300)
    ap.add_argument("--homs", type=int, nargs="+", required=True)
    a = ap.parse_args()
    run(a.code, a.kind, a.target, a.workers, a.time_limit, a.homs)


if __name__ == "__main__":
    main()
