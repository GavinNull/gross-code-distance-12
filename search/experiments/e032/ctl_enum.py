"""E-032 classical control / family census: enumerate EVERY legal deterministic circuit of a timing family (same SAT
encoding as cegar10, no logical nogoods, each time assignment blocked after use) and screen each exactly
(lift10.test, R = 1..rmax, both bases), counting how many pass.  Also records the frame-model lift count.

    PYTHONPATH=.:tests uv run python -m search.experiments.e032.ctl_enum --xo A1A2A3B3B1B2 --zo A1A2A3B3B1B2 --hs "0,1;1,0" --P 11
"""
from __future__ import annotations

import argparse
import collections
import json
import time

from search.experiments.e032 import common as C
from search.experiments.e032 import frame as FR
from search.experiments.e032.cegar import load_class
from search.experiments.e032.cegar10 import screen9
from search.experiments.e032.wlist import labord_of


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xo", required=True)
    ap.add_argument("--zo", required=True)
    ap.add_argument("--hs", required=True)
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--nowrap", type=int, default=0)
    ap.add_argument("--rmax", type=int, default=2)
    ap.add_argument("--max_sec", type=float, default=7200)
    a = ap.parse_args()
    P = a.P
    t0 = time.time()
    labs = {"X": labord_of("all", a.xo), "Z": labord_of("all", a.zo)}
    lists, Es, s10, s11 = {}, {}, {}, {}
    for k, o in (("X", a.xo), ("Z", a.zo)):
        l10, cs = load_class(k, "all", o, 10)
        l11, _ = load_class(k, "all", o, 11)
        lists[k] = (l10, l11, cs)
        Es[k] = C.ext_general(k, labs[k])
        k2j = {Es[k]["He"][:, j].tobytes() + Es[k]["Le"][:, j].tobytes(): j for j in range(Es[k]["N"])}
        s10[k] = [tuple(sorted(k2j[x] for x in S)) for S in l10]
        s11[k] = [tuple(sorted(k2j[x] for x in S)) for S in l11]
    gens = [tuple(int(v) for v in g.split(",")) for g in a.hs.split(";")]
    F = FR.Family(gens)
    uord = {(ty, kk): labs[ty][F.reps[kk]] for ty in "XZ" for kk in range(F.nc)}
    r10, _ = FR.prepare(F, Es, s10)
    r11, _ = FR.prepare(F, Es, s11)
    M = FR.Enc(F, uord, P, a.nowrap)
    out = C.OUT / f"census_{a.xo}_{a.zo}_H{len(F.Hs)}_P{P}{'_nw' if a.nowrap else ''}.jsonl"
    out.write_text("")
    n, stat, passed = 0, collections.Counter(), []
    status = "TIMEOUT"
    while time.time() - t0 < a.max_sec:
        if not M.S.solve():
            status = "COMPLETE"; break
        t, st = M.times(M.S.get_model())
        n += 1
        lif = FR.evaluate_ext(F, r10, r11, t, P)
        d = FR.spec_of(F, t, st, P)
        r = screen9(d, lists, a.rmax)
        key = (r["status"], r.get("R"), r.get("basis"), tuple(r.get("why") or []))
        stat[str(key)] += 1
        rec = {"n": n, "frame_lifts": len(lif), "status": r["status"], "R": r.get("R"), "basis": r.get("basis"),
               "why": r.get("why"), "spec": d if r["status"] == "CERTIFIED" else None}
        if r["status"] == "CERTIFIED":
            passed.append(n)
        with open(out, "a") as f:
            f.write(json.dumps(rec) + "\n")
        M.S.add_clause([-M.x[(i, v)] for i, v in t.items()])
    res = {"P": P, "status": status, "circuits": n, "passed_exact_R<=%d" % a.rmax: len(passed), "passed_ids": passed,
           "outcomes": dict(stat), "sec": round(time.time() - t0, 1)}
    print(json.dumps(res), flush=True)


if __name__ == "__main__":
    main()
