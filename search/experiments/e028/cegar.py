"""E-028 step 3: timing + in-class order CEGAR (port of e024b/gsat.main) for [[90,8,10]] with complete weight-w lists.

Class: per side a (sub, orders) as in wlist.py (extended code fixed; each unit may use any of the 8 orders of its
type).  Family: Hs (generators; must preserve both sides' label orders), units = (type, Hs-orbit).  Model candidates
(no modelled lift) go to the exact lift (lift.lift_screen, R = 1..rmax, both bases); failures are blocked exactly.
UNSAT => every circuit of the family has a frame-model-lifting weight-w extended logical, i.e. a bulk undetected
circuit logical of weight w (d_circ <= w for enough rounds).

    PYTHONPATH=.:tests uv run python -m search.experiments.e028.cegar --xo A1A2A3B2B1B3 --zo A1A2A3B2B1B3 --hs "0,1;1,0" --P 12
"""
from __future__ import annotations

import argparse
import json
import pickle
import random
import time

from search.experiments.e028 import common as C
from search.experiments.e028 import frame as FR
from search.experiments.e028.lift import lift_screen
from search.experiments.e028.wlist import labord_of, tag_of


def load_class(kind, sub, orders_s, w):
    d = pickle.load(open(C.OUT / f"{tag_of(kind, sub, orders_s, w)}.pkl", "rb"))
    return d["keys"], frozenset(d["colset"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xsub", default="all")
    ap.add_argument("--xo", required=True)
    ap.add_argument("--zsub", default="all")
    ap.add_argument("--zo", required=True)
    ap.add_argument("--w", type=int, default=8)
    ap.add_argument("--hs", required=True, help="family subgroup generators a,b;a,b ('0,0' = per-check free)")
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--nowrap", type=int, default=0)
    ap.add_argument("--max_sec", type=float, default=3600)
    ap.add_argument("--rmax", type=int, default=6)
    ap.add_argument("--tag", default="")
    ap.add_argument("--nologic", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--maxcand", type=int, default=100000)
    ap.add_argument("--stop_on_cert", type=int, default=1)
    a = ap.parse_args()
    P = a.P
    t0 = time.time()
    labs = {"X": labord_of(a.xsub, a.xo), "Z": labord_of(a.zsub, a.zo)}
    lists, colsets, Es, sols = {}, {}, {}, {}
    for k, sub, o in (("X", a.xsub, a.xo), ("Z", a.zsub, a.zo)):
        lists[k], colsets[k] = load_class(k, sub, o, a.w)
        Es[k] = C.ext_general(k, labs[k])
        assert C.keyset(Es[k]) == colsets[k]
        k2j = {Es[k]["He"][:, j].tobytes() + Es[k]["Le"][:, j].tobytes(): j for j in range(Es[k]["N"])}
        sols[k] = [tuple(sorted(k2j[x] for x in S)) for S in lists[k]]
    gens = [tuple(int(v) for v in g.split(",")) for g in a.hs.split(";")]
    F = FR.Family(gens)
    for k in "XZ":
        for i in range(C.N2):
            assert labs[k][i] == labs[k][F.reps[F.cls[i]]], "family subgroup does not preserve the class"
    uord = {(ty, kk): labs[ty][F.reps[kk]] for ty in "XZ" for kk in range(F.nc)}
    recs, skipped = FR.prepare(F, Es, sols)
    M = FR.Enc(F, uord, P, a.nowrap)
    rng = random.Random(a.seed)
    print(f"P={P} nowrap={a.nowrap} |Hs|={len(F.Hs)} units/type={F.nc} reps {len(recs)} skipped {skipped} "
          f"det {M.ndet} vars {M.pool.top} {time.time() - t0:.0f}s", flush=True)
    tag = a.tag or f"cg_{a.xo}_{a.zo}_H{len(F.Hs)}_P{P}{'_nw' if a.nowrap else ''}"
    log = {"P": P, "xo": a.xo, "zo": a.zo, "xsub": a.xsub, "zsub": a.zsub, "hs": a.hs, "nowrap": a.nowrap,
           "reps": len(recs), "skipped": skipped, "nologic": a.nologic, "iters": 0, "nogoods": 0, "cands": [],
           "lifting_hist": []}
    status, it, ncand = "UNKNOWN", 0, 0
    while time.time() - t0 < a.max_sec:
        it += 1
        if a.seed:
            M.S.set_phases([v if rng.random() < 0.5 else -v for v in range(1, M.pool.top + 1)])
        if not M.S.solve():
            status = "UNSAT"; break
        t, st = M.times(M.S.get_model())
        lif = [] if a.nologic else FR.evaluate(F, recs, t, P)
        log["lifting_hist"].append(len(lif))
        if not lif:
            ncand += 1
            d = FR.spec_of(F, t, st, P)
            sp = C.OUT / f"{tag}_cand{ncand}.json"
            sp.write_text(json.dumps(d))
            r = lift_screen(d, lists, colsets, a.rmax)
            rr = {"n": ncand, "it": it, "status": r["status"], "R": r.get("R"), "basis": r.get("basis"),
                  "spec": str(sp), "sec": round(time.time() - t0, 1), "err": r.get("err")}
            log["cands"].append(rr)
            print("cand", json.dumps(rr), flush=True)
            if r["status"] == "CERTIFIED":
                status = "CERTIFIED"
                if a.stop_on_cert:
                    break
            else:
                sp.unlink()
            if ncand >= a.maxcand:
                status = status if status == "CERTIFIED" else "MAXCAND"; break
            M.S.add_clause([-M.x[(i, v)] for i, v in t.items()])
            continue
        for r_, cons, pi in lif:
            M.nogood(cons, pi)
            log["nogoods"] += 1
        if it % 50 == 0 or it < 3:
            print({"it": it, "lifting": len(lif), "nogoods": log["nogoods"], "sec": round(time.time() - t0, 1)},
                  flush=True)
    log.update(status=status, iters=it, sec=round(time.time() - t0, 1), ncand=ncand)
    print(f"STATUS P={P} {status} it={it} cands={ncand} {log['sec']}s", flush=True)
    (C.OUT / f"{tag}.json").write_text(json.dumps(log))


if __name__ == "__main__":
    main()
