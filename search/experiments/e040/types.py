"""E-040 step 1: per code, per side (kind X = X-check hooks / Z-basis memory, kind Z), per extended-code type (90; the
type of an order determines its extended code, Strikis 2603.05481 Def. 2), with every check using that order:
d_ext (complete hook-orbit DFS at W = d_ext - 1 with 0 solutions; every extended logical of weight < d contains a hook
column) and the complete weight-d_ext list (orbit-expanded under the 45 / 72 translations, each verified).

    PYTHONPATH=.:tests uv run python -m search.experiments.e040.types --code bb90 --kind X --workers 2
"""
from __future__ import annotations

import argparse
import json
import pickle
import time

from search.experiments.e040.codes import DCODE, MOD, OUT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--kind", required=True)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--wmin", type=int, default=3)
    a = ap.parse_args()
    C = MOD[a.code]
    from search.experiments.e032.dext import hooks_first  # generic (uses E only)
    out = OUT / f"types_{a.code}_{a.kind}.jsonl"
    done = set()
    if out.exists():
        done = {json.loads(l)["type"] for l in out.read_text().splitlines()}
    for o in C.all_types():
        nm = C.name(o)
        if nm in done:
            continue
        t0 = time.time()
        E = C.ext_general(a.kind, [o] * C.N2)
        orb, reps, nh = hooks_first(E)
        W = a.wmin
        while True:
            s, n, c = C.dfs(E, W, stopfirst=1, workers=a.workers, cases=range(nh), orbit=orb, reps=reps)
            if s:
                break
            assert c
            W += 1
            assert W < DCODE[a.code]
        dext = W
        log = []
        s, n, c = C.dfs(E, dext, stopfirst=0, workers=a.workers, cases=range(nh), orbit=orb, reps=reps, log=log)
        assert c
        assert all(int(l.split("found=")[1].split()[0]) < 100000 for l in log), "printing truncated"
        assert all(len(S) == dext for S in s)
        allS = C.expand(E, s)
        C.verify_logicals(E, allS)
        keys = [[E["He"][:, j].tobytes() + E["Le"][:, j].tobytes() for j in S] for S in allS]
        rec = {"code": a.code, "kind": a.kind, "type": nm, "N": E["N"], "dext": dext, "n": len(allS),
               "reps": len(s), "sec": round(time.time() - t0, 1)}
        pickle.dump({"keys": keys, "meta": rec}, open(OUT / f"list_{a.code}_{a.kind}_{nm}.pkl", "wb"))
        print(json.dumps(rec), flush=True)
        with open(out, "a") as f:
            f.write(json.dumps(rec) + "\n")


if __name__ == "__main__":
    main()
