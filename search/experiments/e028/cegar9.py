"""E-028 step 3' (d_ext = 8 classes): timing + in-class order CEGAR blocking every weight <= 9 undetected logical in the
bulk frame model: weight-8 list (exact one fault per column), weight-8 + one readout flip (split model), weight-9 list.
Model candidates -> exact test lift9.test (R = 1..rmax, both bases); failures blocked exactly.
UNSAT => every circuit of the family has a modelled bulk weight-<=9 undetected logical (d_circ <= 9 for enough rounds).

    PYTHONPATH=.:tests uv run python -m search.experiments.e028.cegar9 --xo A1A2A3B2B1B3 --zo A1A2A3B2B1B3 --hs "0,1;1,0" --P 16
"""
from __future__ import annotations

import argparse
import json
import random
import time

from evaluators.candidate import parse_schedule
from search.experiments.e028 import common as C
from search.experiments.e028 import frame as FR
from search.experiments.e028.cegar import load_class
from search.experiments.e028.lift import KIND_OF_BASIS
from search.experiments.e028.lift9 import test as exact9
from search.experiments.e028.wlist import labord_of


def screen9(d, lists, rmax):
    spec = parse_schedule(d).canonical()
    per = []
    for R in range(1, rmax + 1):
        for b in "ZX":
            try:
                r = exact9(spec, R, b, *lists[KIND_OF_BASIS[b]])
            except Exception as e:  # noqa: BLE001
                return {"status": "error", "err": str(e)[:300]}
            per.append(r)
            if r["w8"] or r["w8z"] or r["w9"]:
                return {"status": "lifts", "R": R, "basis": b, "why": [k for k in ("w8", "w8z", "w9") if r[k]]}
    return {"status": "CERTIFIED", "per": per}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xsub", default="all")
    ap.add_argument("--xo", required=True)
    ap.add_argument("--zsub", default="all")
    ap.add_argument("--zo", required=True)
    ap.add_argument("--hs", required=True)
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--nowrap", type=int, default=0)
    ap.add_argument("--max_sec", type=float, default=3600)
    ap.add_argument("--rmax", type=int, default=4)
    ap.add_argument("--tag", default="")
    ap.add_argument("--nologic", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--maxcand", type=int, default=100000)
    a = ap.parse_args()
    P = a.P
    t0 = time.time()
    labs = {"X": labord_of(a.xsub, a.xo), "Z": labord_of(a.zsub, a.zo)}
    lists, Es, s8, s9 = {}, {}, {}, {}
    for k, sub, o in (("X", a.xsub, a.xo), ("Z", a.zsub, a.zo)):
        l8, cs8 = load_class(k, sub, o, 8)
        l9, _ = load_class(k, sub, o, 9)
        lists[k] = (l8, l9, cs8)
        Es[k] = C.ext_general(k, labs[k])
        assert C.keyset(Es[k]) == cs8
        k2j = {Es[k]["He"][:, j].tobytes() + Es[k]["Le"][:, j].tobytes(): j for j in range(Es[k]["N"])}
        s8[k] = [tuple(sorted(k2j[x] for x in S)) for S in l8]
        s9[k] = [tuple(sorted(k2j[x] for x in S)) for S in l9]
    gens = [tuple(int(v) for v in g.split(",")) for g in a.hs.split(";")]
    F = FR.Family(gens)
    for k in "XZ":
        for i in range(C.N2):
            assert labs[k][i] == labs[k][F.reps[F.cls[i]]], "family subgroup does not preserve the class"
    uord = {(ty, kk): labs[ty][F.reps[kk]] for ty in "XZ" for kk in range(F.nc)}
    r8, sk8 = FR.prepare(F, Es, s8)
    r9, sk9 = FR.prepare(F, Es, s9)
    M = FR.Enc(F, uord, P, a.nowrap)
    rng = random.Random(a.seed)
    print(f"P={P} nowrap={a.nowrap} |Hs|={len(F.Hs)} units/type={F.nc} reps8 {len(r8)} (skip {sk8}) reps9 {len(r9)} "
          f"(skip {sk9}) vars {M.pool.top} {time.time() - t0:.0f}s", flush=True)
    tag = a.tag or f"cg9_{a.xo}_{a.zo}_H{len(F.Hs)}_P{P}{'_nw' if a.nowrap else ''}"
    log = {"P": P, "xo": a.xo, "zo": a.zo, "xsub": a.xsub, "zsub": a.zsub, "hs": a.hs, "nowrap": a.nowrap,
           "reps8": len(r8), "reps9": len(r9), "skipped": [sk8, sk9], "nologic": a.nologic, "iters": 0,
           "nogoods": 0, "cands": [], "hist": []}
    status, it, ncand = "UNKNOWN", 0, 0
    best = None
    while time.time() - t0 < a.max_sec:
        it += 1
        if a.seed:
            M.S.set_phases([v if rng.random() < 0.5 else -v for v in range(1, M.pool.top + 1)])
        if not M.S.solve():
            status = "UNSAT"; break
        t, st = M.times(M.S.get_model())
        lif = [] if a.nologic else FR.evaluate9(F, r8, r9, t, P)
        cnt = {k: sum(1 for x in lif if x[3] == k) for k in ("w8", "w8z", "w9")}
        log["hist"].append(cnt)
        if best is None or len(lif) < best:
            best = len(lif)
        if not lif:
            ncand += 1
            d = FR.spec_of(F, t, st, P)
            sp = C.OUT / f"{tag}_cand{ncand}.json"
            sp.write_text(json.dumps(d))
            r = screen9(d, lists, a.rmax)
            rr = {"n": ncand, "it": it, "status": r["status"], "R": r.get("R"), "basis": r.get("basis"),
                  "why": r.get("why"), "spec": str(sp), "sec": round(time.time() - t0, 1), "err": r.get("err")}
            log["cands"].append(rr)
            print("cand", json.dumps(rr), flush=True)
            if r["status"] == "CERTIFIED":
                status = "CERTIFIED"; break
            sp.unlink()
            if ncand >= a.maxcand:
                status = "MAXCAND"; break
            M.S.add_clause([-M.x[(i, v)] for i, v in t.items()])
            continue
        for r_, cons, pi, kd in lif:
            FR.nogood2(M, cons, pi)
            log["nogoods"] += 1
        if it % 25 == 0 or it < 3:
            print({"it": it, **cnt, "nogoods": log["nogoods"], "best": best, "sec": round(time.time() - t0, 1)},
                  flush=True)
    log.update(status=status, iters=it, sec=round(time.time() - t0, 1), ncand=ncand, best=best)
    print(f"STATUS P={P} {status} it={it} cands={ncand} best={best} {log['sec']}s", flush=True)
    (C.OUT / f"{tag}.json").write_text(json.dumps(log))


if __name__ == "__main__":
    main()
