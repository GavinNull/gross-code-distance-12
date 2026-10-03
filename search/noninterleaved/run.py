"""E-005 driver: non-interleaved circuit distance via the extended code (arXiv:2603.05481 v2, Thm. 1).

  PYTHONPATH=. uv run python -m search.noninterleaved.run <stage> --code "[[90,8,10]]" [--workers 5]

Stages
  single   Prop.-4-style bound: for X check 0 and Z check 0, all 720 CNOT orders -> 90 residual classes each;
           exact d_ext of (code + that single check's residuals).  For any non-interleaved single-ancilla SEC
           (any depth) d_circ <= min(max_X, max_Z)  (Thm. 1 Eq. (10) with R = one check's residuals; all checks of a
           group code are equivalent under translation).
  uniform  Tiled ("uniformly tiled", App. H Prop. 5) circuits: the same term order on every X check (resp. Z).
           Exact d^X_ext(sigma_X), d^Z_ext(sigma_Z) for all 90 classes each.
  feasible Combine: all depth-8 uniform schedules (P_X = 0, sigma_X, P_Z, sigma_Z) without data conflicts and
           non-interleaved; distribution of d_ext = min(d^X, d^Z) over them; LRC subset; best schedules.
  fig12    Gross-code check: d_ext of the Strikis Fig. 12 circuit (baselines/strikis.py).
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from search.noninterleaved.ext import d_ext_type, extended_matrices, residual_supports, SOLVERS
from search.noninterleaved.schedules import (data_conflict_free, interleaving, neighbours, uniform_schedule)

OUT = Path("results/E-005-noninterleaved-bound")
CODE_D = {"[[90,8,10]]": 10, "[[108,8,10]]": 10, "[[120,8,12]]": 12, "WMc[[126,12,10]]": 10, "[[144,12,12]]": 12,
          "[[72,12,6]]": 6}


def get_code(name):
    from search.proxy.candidates import code_obj
    c = code_obj(name)
    css = c.to_css()
    return c, css


def tag(name):
    return name.replace("[", "").replace("]", "").replace(",", "_")


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)))


def HL(css, kind):
    """Matrices detecting the hooks of `kind` checks: X-check hooks are X errors -> (H_Z, L_Z); Z -> (H_X, L_X)."""
    return (css.HZ, css.LZ) if kind == "X" else (css.HX, css.LX)


def class_key(H, L, supports):
    He, Le, _ = extended_matrices(H, L, supports)
    n = H.shape[1]
    extra = sorted(He[:, j].tobytes() + Le[:, j].tobytes() for j in range(He.shape[1]))
    return tuple(extra)


def _solve(job):
    H, L, sups, cap, tl, solver = job["H"], job["L"], job["sups"], job["cap"], job["tl"], job["solver"]
    He, Le, lab = extended_matrices(H, L, sups)
    r = SOLVERS[solver](He, Le, max_weight=cap, time_limit=tl)
    return {"key": job["key"], "lower": r.lower, "upper": r.upper, "status": r.status, "seconds": r.seconds,
            "cols": He.shape[1], "witness": [lab[j] for j in r.witness]}


def run_jobs(jobs, workers):
    if workers <= 1:
        return [_solve(j) for j in jobs]
    with Pool(workers) as p:
        return list(p.imap(_solve, jobs))


# ----------------------------------------------------------------------------- single-check bound
def stage_single(name, workers, tl, cap, types="XZ", solver="milp"):
    code, css = get_code(name)
    out = {"code": name, "cap": cap, "solver": solver, "time_limit": tl, "types": {}}
    t0 = time.time()
    for kind in types:
        H, L = HL(css, kind)
        sup = [neighbours(code, kind, 0, t) for t in range(6)]   # data columns of check 0, term order 0..5
        classes = {}
        for perm in itertools.permutations(range(6)):
            order = [sup[t] for t in perm]
            k = class_key(H, L, residual_supports(order))
            classes.setdefault(k, []).append(list(perm))
        jobs = [{"H": H, "L": L, "sups": residual_supports([sup[t] for t in perms[0]]), "cap": cap, "tl": tl,
                 "solver": solver, "key": perms[0]} for k, perms in classes.items()]
        res = run_jobs(jobs, workers)
        sizes = {tuple(perms[0]): len(perms) for perms in classes.values()}
        for r in res:
            r["class_size"] = sizes[tuple(r["key"])]
        out["types"][kind] = {"num_classes": len(classes), "results": res,
                              "hist_upper": _hist([r["upper"] for r in res]),
                              "hist_lower": _hist([r["lower"] for r in res]),
                              "all_exact": all(r["lower"] == r["upper"] for r in res)}
        print(kind, len(classes), out["types"][kind]["hist_upper"], out["types"][kind]["hist_lower"], flush=True)
    out["seconds"] = time.time() - t0
    dump(OUT / f"single_{tag(name)}.json", out)
    return out


def _hist(v):
    h = {}
    for x in v:
        h[str(x)] = h.get(str(x), 0) + 1
    return dict(sorted(h.items()))


# ----------------------------------------------------------------------------- uniform tilings
def stage_uniform(name, workers, tl, cap, types="XZ", solver="milp"):
    code, css = get_code(name)
    n2 = code.n2
    out = {"code": name, "cap": cap, "solver": solver, "time_limit": tl, "types": {}}
    t0 = time.time()
    for kind in types:
        H, L = HL(css, kind)
        sup0 = [neighbours(code, kind, 0, t) for t in range(6)]
        key0 = {}
        classes = {}
        for perm in itertools.permutations(range(6)):
            # class by the single-check residual set (tiling is translation of it, so same key => same tiled code)
            k = class_key(H, L, residual_supports([sup0[t] for t in perm]))
            classes.setdefault(k, []).append(list(perm))
        jobs = []
        for k, perms in classes.items():
            perm = perms[0]
            sups = [s for i in range(n2) for s in residual_supports([neighbours(code, kind, i, t) for t in perm])]
            jobs.append({"H": H, "L": L, "sups": sups, "cap": cap, "tl": tl, "solver": solver, "key": perm})
        res = run_jobs(jobs, workers)
        perm_to_class = {}
        for r, (k, perms) in zip(res, classes.items()):
            r["members"] = perms
        out["types"][kind] = {"num_classes": len(classes), "results": res,
                              "hist_upper": _hist([r["upper"] for r in res]),
                              "hist_lower": _hist([r["lower"] for r in res]),
                              "all_exact": all(r["lower"] == r["upper"] for r in res)}
        print(kind, len(classes), out["types"][kind]["hist_upper"], out["types"][kind]["hist_lower"], flush=True)
    out["seconds"] = time.time() - t0
    dump(OUT / f"uniform_{tag(name)}.json", out)
    return out


# ----------------------------------------------------------------------------- depth-8 feasibility of uniform pairs
def overlap_types(code):
    """For X check 0: list over overlapping Z checks of [(x_term, z_term), ...] for each shared data qubit."""
    xs = {neighbours(code, "X", 0, t): t for t in range(6)}
    out = []
    for j in range(code.n2):
        sh = []
        for tz in range(6):
            d = neighbours(code, "Z", j, tz)
            if d in xs:
                sh.append((xs[d], tz))
        if sh:
            out.append(sh)
    return out


def term_level_interleaving(ov, sX, PZ, sZ):
    """Uniform schedule with P_X = 0.  Returns (no_mixed, set_of_thresholds)."""
    tx = {t: 1 + k for k, t in enumerate(sX)}
    tz = {t: PZ + 1 + k for k, t in enumerate(sZ)}
    ths = set()
    for sh in ov:
        c = None
        for delta in range(-3, 4):
            o = {tx[a] + 8 * delta > tz[b] for a, b in sh}
            if len(o) > 1:
                return False, None
            if o.pop() and c is None:
                c = delta
        ths.add(c)
    return True, ths


def _value(dmap, perm):
    return dmap[tuple(perm)]


def stage_feasible(name, max_full_checks=200):
    code, css = get_code(name)
    U = json.loads((OUT / f"uniform_{tag(name)}.json").read_text())
    d = {}
    for kind in "XZ":
        d[kind] = {}
        for r in U["types"][kind]["results"]:
            val = (r["lower"], r["upper"])
            for m in r["members"]:
                d[kind][tuple(m)] = val
    ov = overlap_types(code)
    perms = list(itertools.permutations(range(6)))
    stats = {"combos": 0, "data_ok": 0, "no_mixed": 0, "const_threshold": 0, "full_check_needed": 0,
             "full_check_ok": 0}
    dist = {}
    best = []
    lrc_best = None
    lrc_dist = {}
    A, B = (0, 1, 2), (3, 4, 5)
    for sX in perms:
        for sZ in perms:
            for PZ in range(8):
                stats["combos"] += 1
                if not data_conflict_free(0, sX, PZ, sZ):
                    continue
                stats["data_ok"] += 1
                ok, ths = term_level_interleaving(ov, sX, PZ, sZ)
                if not ok:
                    continue
                stats["no_mixed"] += 1
                if len(ths) == 1:
                    stats["const_threshold"] += 1
                    ni = True
                else:
                    stats["full_check_needed"] += 1
                    ni = None   # decided below only for candidates that matter
                dx, dz = _value(d["X"], sX), _value(d["Z"], sZ)
                lo = min(dx[0], dz[0])
                up = min(x for x in (dx[1], dz[1]) if x is not None) if (dx[1] or dz[1]) else None
                rec = {"sX": list(sX), "PZ": PZ, "sZ": list(sZ), "dX": dx, "dZ": dz, "lower": lo, "upper": up,
                       "const_threshold": ni is True, "thresholds": sorted(ths)}
                if ni is None:
                    continue_flag = True
                else:
                    continue_flag = False
                key = f"{lo}-{up}"
                if not continue_flag:
                    dist[key] = dist.get(key, 0) + 1
                    is_lrc = (set(sX[:3]) == set(A) and set(sZ[:3]) == set(B)) or \
                             (set(sX[:3]) == set(B) and set(sZ[:3]) == set(A))
                    if is_lrc:
                        lrc_dist[key] = lrc_dist.get(key, 0) + 1
                        if lrc_best is None or lo > lrc_best["lower"]:
                            lrc_best = rec
                    best.append(rec)
                else:
                    best.append({**rec, "needs_full_check": True})
    # full interleaving check for the non-constant-threshold candidates with the best values
    best.sort(key=lambda r: (-r["lower"], -(r["upper"] or 99)))
    top_lower = max(r["lower"] for r in best if not r.get("needs_full_check")) if best else None
    checked = 0
    for r in best:
        if r.get("needs_full_check") and r["lower"] >= (top_lower or 0) and checked < max_full_checks:
            sched = uniform_schedule(code, 0, r["sX"], r["PZ"], r["sZ"])
            rep = interleaving(sched)
            checked += 1
            r["full_interleaving"] = rep
            if rep["non_interleaved"]:
                stats["full_check_ok"] += 1
                key = f"{r['lower']}-{r['upper']}"
                dist[key] = dist.get(key, 0) + 1
    good = [r for r in best if not r.get("needs_full_check") or r.get("full_interleaving", {}).get("non_interleaved")]
    out = {"code": name, "stats": stats, "dist_lower_upper": dict(sorted(dist.items())),
           "note_dist": "counts of (P_X=0, sigma_X, P_Z, sigma_Z) depth-8 uniform schedules, conflict-free and "
                        "non-interleaved; candidates needing a full (non-constant threshold) check are only counted "
                        "if checked (top value only)",
           "lrc_dist": dict(sorted(lrc_dist.items())), "lrc_best": lrc_best,
           "best": good[:50], "num_good": len(good)}
    dump(OUT / f"feasible_{tag(name)}.json", out)
    print(json.dumps({k: v for k, v in out.items() if k not in ("best",)}, indent=1, default=str))
    print("best:", good[:3])
    return out


# ----------------------------------------------------------------------------- Fig. 12
def stage_fig12(workers, tl, cap, solver="milp"):
    from baselines.bb_code import gross_code
    from baselines.strikis import strikis_fig12
    from evaluators.codes import CSSCode
    from search.noninterleaved.ext import orders_from_schedule
    g = gross_code()
    css = CSSCode.from_checks(g.HX, g.HZ)
    sched, _ = strikis_fig12(g)
    xo, zo = orders_from_schedule(sched)
    jobs = []
    for kind, orders in (("X", xo), ("Z", zo)):
        H, L = HL(css, kind)
        jobs.append({"H": H, "L": L, "sups": [s for o in orders for s in residual_supports(o)], "cap": cap,
                     "tl": tl, "solver": solver, "key": kind})
    res = run_jobs(jobs, min(workers, 2))
    out = {"interleaving": interleaving(sched), "results": res, "cap": cap, "time_limit": tl}
    dump(OUT / f"fig12_cap{cap}.json", out)
    print(json.dumps(out, indent=1, default=str)[:3000])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["single", "uniform", "feasible", "fig12"])
    ap.add_argument("--code", default="[[90,8,10]]")
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--time-limit", type=float, default=1800)
    ap.add_argument("--cap", type=int, default=None, help="valid cap on the weight (default: code distance)")
    ap.add_argument("--types", default="XZ")
    ap.add_argument("--solver", default="milp")
    a = ap.parse_args()
    cap = a.cap if a.cap is not None else CODE_D.get(a.code)
    if a.stage == "single":
        stage_single(a.code, a.workers, a.time_limit, cap, a.types, a.solver)
    elif a.stage == "uniform":
        stage_uniform(a.code, a.workers, a.time_limit, cap, a.types, a.solver)
    elif a.stage == "feasible":
        stage_feasible(a.code)
    elif a.stage == "fig12":
        stage_fig12(a.workers, a.time_limit, a.cap if a.cap is not None else 12, a.solver)


if __name__ == "__main__":
    main()
