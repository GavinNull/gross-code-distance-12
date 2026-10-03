"""Uniformly tiled depth-8 non-interleaved circuits: enumerate the space, then decide d_ext >= target.

  PYTHONPATH=. uv run python -m search.noninterleaved.uniform_search space  --code "[[90,8,10]]"
  PYTHONPATH=. uv run python -m search.noninterleaved.uniform_search target --code "[[90,8,10]]" --target 9

space:  all (P_X = 0, sigma_X in S6, P_Z in 0..7, sigma_Z in S6) = 4,147,200 uniform schedules (P_X = 0 fixes the
        global time origin).  Keep those with (a) no data-qubit slot conflict, (b) no mixed overlapping pair
        (term-level check for every X/Z overlap type), (c) consistent round thresholds: if all overlap types give
        the same threshold the circuit is non-interleaved; otherwise the full `schedules.interleaving` check is run
        on the built schedule (cached per (sigma_X, P_Z, sigma_Z) pattern).  Also tags LRCs (X: A-block then
        B-block; Z: B-block then A-block, or the mirror image; arXiv:2603.05481 Sec. III.A).
target: d_ext of a uniform circuit is min(d^X(sigma_X), d^Z(sigma_Z)) (decoupled).  Only classes that occur in a
        feasible schedule and whose single-check bound (stage single) is >= target are tested, with the MILP cap
        target-1: infeasible => d >= target (proof), feasible => explicit witness of weight <= target-1.
        Stops early once a feasible pair with both sides >= target is found? No: tests all candidate classes so the
        full set of target-achieving schedules is reported.
"""
from __future__ import annotations

import argparse
import itertools
import json
import time

from search.noninterleaved.ext import residual_supports
from search.noninterleaved.run import (HL, OUT, class_key, dump, get_code, neighbours, run_jobs, tag)
from search.noninterleaved.schedules import data_conflict_free, interleaving, uniform_schedule

PERMS = list(itertools.permutations(range(6)))


def overlap_types(code):
    xs = {neighbours(code, "X", 0, t): t for t in range(6)}
    out = set()
    for j in range(code.n2):
        sh = tuple(sorted((xs[d], tz) for tz in range(6) for d in [neighbours(code, "Z", j, tz)] if d in xs))
        if sh:
            out.add(sh)
    return sorted(out)


def term_level(ov, sX, PZ, sZ):
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


def is_lrc(sX, sZ):
    A, B = {0, 1, 2}, {3, 4, 5}
    return (set(sX[:3]) == A and set(sZ[:3]) == B) or (set(sX[:3]) == B and set(sZ[:3]) == A)


def classes(code, css, kind):
    H, L = HL(css, kind)
    sup0 = [neighbours(code, kind, 0, t) for t in range(6)]
    cl = {}
    for p in PERMS:
        cl.setdefault(class_key(H, L, residual_supports([sup0[t] for t in p])), []).append(p)
    rep = {}
    for k, ps in cl.items():
        for p in ps:
            rep[p] = ps[0]
    return rep


def stage_space(name):
    code, css = get_code(name)
    t0 = time.time()
    ov = overlap_types(code)
    st = {"combos": 0, "data_ok": 0, "no_mixed": 0, "const_threshold": 0, "full_checked": 0, "full_ok": 0}
    feas = []
    for sX in PERMS:
        for sZ in PERMS:
            for PZ in range(8):
                st["combos"] += 1
                if not data_conflict_free(0, sX, PZ, sZ):
                    continue
                st["data_ok"] += 1
                ok, ths = term_level(ov, sX, PZ, sZ)
                if not ok:
                    continue
                st["no_mixed"] += 1
                if len(ths) == 1:
                    st["const_threshold"] += 1
                    feas.append((sX, PZ, sZ, "const"))
                else:
                    st["full_checked"] += 1
                    rep = interleaving(uniform_schedule(code, 0, sX, PZ, sZ))
                    if rep["non_interleaved"]:
                        st["full_ok"] += 1
                        feas.append((sX, PZ, sZ, "full"))
    repX, repZ = classes(code, css, "X"), classes(code, css, "Z")
    cx = sorted({repX[f[0]] for f in feas})
    cz = sorted({repZ[f[2]] for f in feas})
    out = {"code": name, "overlap_types": ov, "stats": st, "num_feasible": len(feas),
           "num_lrc": sum(is_lrc(f[0], f[2]) for f in feas),
           "x_classes_in_feasible": [list(c) for c in cx], "z_classes_in_feasible": [list(c) for c in cz],
           "num_x_classes_total": len(set(repX.values())), "num_z_classes_total": len(set(repZ.values())),
           "feasible": [[list(f[0]), f[1], list(f[2]), f[3]] for f in feas], "seconds": time.time() - t0}
    dump(OUT / f"space_{tag(name)}.json", out)
    print(json.dumps({k: v for k, v in out.items() if k not in ("feasible", "x_classes_in_feasible",
                                                                  "z_classes_in_feasible")}, default=str))
    return out


def single_values(name):
    S = json.loads((OUT / f"single_{tag(name)}.json").read_text())
    code, css = get_code(name)
    vals = {}
    for kind in "XZ":
        rep = classes(code, css, kind)
        v = {tuple(r["key"]): (r["lower"], r["upper"]) for r in S["types"][kind]["results"]}
        # map each class representative used here to the single-check value of its class
        byclass = {}
        for p, rp in rep.items():
            if p in v:
                byclass[rp] = v[p]
        vals[kind] = byclass
    return vals


def stage_target(name, target, workers, tl, only_lrc=False, solver="feas", kinds="XZ"):
    code, css = get_code(name)
    sp = json.loads((OUT / f"space_{tag(name)}.json").read_text())
    sv = single_values(name)
    repX, repZ = classes(code, css, "X"), classes(code, css, "Z")
    feas = [(tuple(a), b, tuple(c), m) for a, b, c, m in sp["feasible"]]
    if only_lrc:
        feas = [f for f in feas if is_lrc(f[0], f[2])]
    n2 = code.n2
    out = {"code": name, "target": target, "only_lrc": only_lrc, "time_limit": tl, "types": {}}
    t0 = time.time()
    res_by = {}
    for kind, rep, idx in (("X", repX, 0), ("Z", repZ, 2)):
        if kind not in kinds:
            continue
        cand = sorted({rep[f[idx]] for f in feas})
        keep = [c for c in cand if sv[kind][c][1] is None or sv[kind][c][1] >= target]
        H, L = HL(css, kind)
        jobs = []
        for perm in keep:
            sups = [s for i in range(n2) for s in residual_supports([neighbours(code, kind, i, t) for t in perm])]
            jobs.append({"H": H, "L": L, "sups": sups, "cap": target - 1, "tl": tl, "solver": solver, "key": list(perm)})
        res = run_jobs(jobs, workers)
        res_by[kind] = {tuple(r["key"]): r for r in res}
        out["types"][kind] = {"classes_in_feasible": len(cand), "classes_passing_single_bound": len(keep),
                              "results": res,
                              "proved_ge_target": [r["key"] for r in res if r["status"] == "infeasible_under_cap"],
                              "witness_below_target": [[r["key"], r["upper"]] for r in res if r["upper"] is not None],
                              "undecided": [r["key"] for r in res if r["upper"] is None and
                                            r["status"] != "infeasible_under_cap"]}
        print(kind, len(cand), len(keep), "proved>=", len(out["types"][kind]["proved_ge_target"]),
              "below:", len(out["types"][kind]["witness_below_target"]), "undecided:",
              len(out["types"][kind]["undecided"]), flush=True)
    good = []
    for sX, PZ, sZ, m in feas:
        rx, rz = res_by.get("X", {}).get(repX[sX]), res_by.get("Z", {}).get(repZ[sZ])
        if rx and rz and rx["status"] == "infeasible_under_cap" and rz["status"] == "infeasible_under_cap":
            good.append({"PX": 0, "sX": list(sX), "PZ": PZ, "sZ": list(sZ), "ni_check": m, "lrc": is_lrc(sX, sZ)})
    out["achieving_schedules"] = good
    out["num_achieving"] = len(good)
    out["num_achieving_lrc"] = sum(g["lrc"] for g in good)
    out["seconds"] = time.time() - t0
    out["kinds"] = kinds
    dump(OUT / f"target{target}_{tag(name)}{'_lrc' if only_lrc else ''}_{kinds}.json", out)
    print("achieving:", len(good), "lrc:", out["num_achieving_lrc"], good[:3], flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["space", "target"])
    ap.add_argument("--code", default="[[90,8,10]]")
    ap.add_argument("--target", type=int, default=None)
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--time-limit", type=float, default=1800)
    ap.add_argument("--only-lrc", action="store_true")
    ap.add_argument("--solver", default="feas")
    ap.add_argument("--kinds", default="XZ")
    a = ap.parse_args()
    if a.stage == "space":
        stage_space(a.code)
    else:
        stage_target(a.code, a.target, a.workers, a.time_limit, a.only_lrc, a.solver, a.kinds)


if __name__ == "__main__":
    main()
