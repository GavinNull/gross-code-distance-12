"""Two-colour (index-2 subgroup) LRC exhaust for one code / kind / homomorphism.

    PYTHONPATH=. uv run python search/experiments/e015/twocol.py exact --code bb72 --target 6
    PYTHONPATH=. uv run python search/experiments/e015/twocol.py heur  --code gross --target 11 --workers 3

States: (block order on colour 0, block order on colour 1), block order = (A perm, B perm) in S3 x S3 (36);
only proper ones (no data qubit hit twice in one slot by checks of this kind).  The X and Z sides are
independent (LRC template), so each side is enumerated separately and d_ext = min(d^X, d^Z).

exact: dfs128 decides "logical of weight <= target-1?" for every state (complete; symmetry = colour-preserving
       translations).  For small codes only.
heur:  (1) class test: residuals of colour-0 checks only, for each of the 36 block orders: heuristic witness
           < target kills that order on both colours (colour classes are translates; adding columns only lowers
           d_ext).  (2) all proper states built from surviving orders: screen 2 seeds x `trials`;
       (3) survivors: 3 new seeds x `htrials`.  A kill is always a verified witness; survival is not a proof.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import (BLOCKS, OUT, check_orders, colour_symmetry, ext_of_orders, get_code, heur, homs_to_Zp,  # noqa: E402
                    now, proper)
from search.noninterleaved.ext import extended_matrices, residual_supports  # noqa: E402
from search.noninterleaved.colour_search import order_terms  # noqa: E402
from search.noninterleaved.schedules import neighbours  # noqa: E402


def states_for(code, kind, colour, allowed=None):
    al = range(len(BLOCKS)) if allowed is None else allowed
    out = []
    for e in al:
        for o in al:
            if proper(code, kind, colour, {0: BLOCKS[e], 1: BLOCKS[o]}):
                out.append((e, o))
    return out


def exact(codekey, target, kinds="XZ", homsel=None, log=print):
    from dfsrun import decide
    code = get_code(codekey)
    res = {}
    for hm in homs_to_Zp(code, 2):
        hk = f"{hm['u']}{hm['v']}"
        if homsel and hk not in homsel:
            continue
        col = hm["colour"]
        sym = colour_symmetry(code, col)
        for kind in kinds:
            st = states_for(code, kind, col)
            good, hist = [], {}
            t0 = time.time()
            for e, o in st:
                orders = check_orders(code, kind, col, {0: BLOCKS[e], 1: BLOCKS[o]})
                r = decide(code, kind, orders, sym, target - 1)
                if not r["found_any"]:
                    good.append((e, o))
                    hist[f">={target}"] = hist.get(f">={target}", 0) + 1
                else:
                    w = int(r["found_cases"][0]["first"][0].split()[1][2:])
                    hist[f"<={w}"] = hist.get(f"<={w}", 0) + 1
            res[f"{hk}_{kind}"] = {"hom": hk, "kind": kind, "num_states": len(st), "achieving": good,
                                   "achieving_blocks": [[BLOCKS[e], BLOCKS[o]] for e, o in good],
                                   "hist_first_found_weight": hist, "sec": round(time.time() - t0, 1),
                                   "sym": len(sym)}
            log(f"[{now()}] {codekey} hom={hk} {kind}: {len(st)} proper states, {len(good)} with d_ext>={target} "
                f"(DFS, complete) hist={hist} {time.time() - t0:.0f}s")
    return res


# ----------------------------------------------------------------------------- heuristic pipeline
_CTX = {}


def _ctx(codekey, kind, hk):
    key = (codekey, kind, hk)
    if key not in _CTX:
        code = get_code(codekey)
        hm = [h for h in homs_to_Zp(code, 2) if f"{h['u']}{h['v']}" == hk][0]
        _CTX[key] = (code, hm["colour"])
    return _CTX[key]


def _job(args):
    codekey, kind, hk, what, payload, seeds, trials, target = args
    code, col = _ctx(codekey, kind, hk)
    t0 = time.time()
    if what == "class":
        b = BLOCKS[payload]
        o = order_terms(kind, *b)
        from common import HL
        H, L = HL(code, kind)
        sups = [s for i in range(code.n2) if col[i] == 0
                for s in residual_supports([neighbours(code, kind, i, t) for t in o])]
        He, Le, _ = extended_matrices(H, L, sups)
    else:
        e, o = payload
        He, Le, _ = ext_of_orders(code, kind, check_orders(code, kind, col, {0: BLOCKS[e], 1: BLOCKS[o]}))
    w, wit = heur(He, Le, seeds, trials, target)
    return {"what": what, "payload": payload, "seeds": list(seeds), "trials": trials, "w": w,
            "sec": round(time.time() - t0, 1)}


def heur_pipeline(codekey, kind, hk, target, workers, trials=300, htrials=1000, log=print, tag=""):
    code, col = _ctx(codekey, kind, hk)
    rec = open(OUT / f"heur_{codekey}_{hk}_{kind}_T{target}{tag}.jsonl", "a")
    out = {"code": codekey, "kind": kind, "hom": hk, "target": target}
    t0 = time.time()
    with Pool(workers) as p:
        jobs = [(codekey, kind, hk, "class", b, (0, 1), trials, target) for b in range(len(BLOCKS))]
        alive = []
        for r in p.imap_unordered(_job, jobs):
            rec.write(json.dumps(r) + "\n"); rec.flush()
            if r["w"] is None or r["w"] >= target:
                alive.append(r["payload"])
        alive.sort()
        out["class_alive"] = alive
        st = states_for(code, kind, col, alive)
        out["num_states"] = len(st)
        log(f"[{now()}] {codekey} hom={hk} {kind}: class test {len(alive)}/36 block orders alive; "
            f"{len(st)} proper states ({time.time() - t0:.0f}s)")
        jobs = [(codekey, kind, hk, "state", s, (0, 1), trials, target) for s in st]
        cand, hist = [], {}
        for r in p.imap_unordered(_job, jobs):
            rec.write(json.dumps(r) + "\n"); rec.flush()
            hist[str(r["w"])] = hist.get(str(r["w"]), 0) + 1
            if r["w"] is None or r["w"] >= target:
                cand.append(tuple(r["payload"]))
        out["screen_hist"] = hist
        out["screen_pass"] = sorted(cand)
        log(f"[{now()}] {codekey} hom={hk} {kind}: screen hist {dict(sorted(hist.items()))}, {len(cand)} reach "
            f">= {target} ({time.time() - t0:.0f}s)")
        jobs = [(codekey, kind, hk, "state", s, (sd,), htrials, target) for s in cand for sd in (11, 12, 13)]
        res = {s: [] for s in cand}
        for r in p.imap_unordered(_job, jobs):
            rec.write(json.dumps({**r, "stage": "harden"}) + "\n"); rec.flush()
            res[tuple(r["payload"])].append(r["w"])
        surv = sorted(s for s, v in res.items() if all(x is None or x >= target for x in v))
        out["harden"] = {str(k): v for k, v in res.items()}
        out["survivors"] = surv
        out["survivor_blocks"] = [[BLOCKS[e], BLOCKS[o]] for e, o in surv]
        out["sec"] = round(time.time() - t0, 1)
        log(f"[{now()}] {codekey} hom={hk} {kind}: {len(surv)} survivors after 3x{htrials} hardening "
            f"({time.time() - t0:.0f}s): {surv[:12]}")
    (OUT / f"heur_{codekey}_{hk}_{kind}_T{target}{tag}.json").write_text(json.dumps(out, indent=1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["exact", "heur"])
    ap.add_argument("--code", required=True)
    ap.add_argument("--target", type=int, required=True)
    ap.add_argument("--kinds", default="XZ")
    ap.add_argument("--homs", nargs="*", default=None)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--trials", type=int, default=300)
    ap.add_argument("--htrials", type=int, default=1000)
    a = ap.parse_args()
    logf = open(OUT / f"twocol_{a.mode}_{a.code}_T{a.target}.log", "a")

    def log(m):
        print(m, flush=True); logf.write(m + "\n"); logf.flush()
    if a.mode == "exact":
        res = exact(a.code, a.target, a.kinds, a.homs, log)
        (OUT / f"exact_{a.code}_T{a.target}.json").write_text(json.dumps(res, indent=1))
    else:
        code = get_code(a.code)
        hks = [f"{h['u']}{h['v']}" for h in homs_to_Zp(code, 2)]
        log(f"[{now()}] {a.code}: homs to Z2 {hks}")
        for hk in hks:
            if a.homs and hk not in a.homs:
                continue
            for kind in a.kinds:
                heur_pipeline(a.code, kind, hk, a.target, a.workers, a.trials, a.htrials, log)


if __name__ == "__main__":
    main()
