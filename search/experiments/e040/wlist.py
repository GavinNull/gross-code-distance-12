"""E-040: weight-w extended-logical list (orbit-expanded, verified) for one (code, kind, type), w > d_ext; used only as
a source of lift candidates (soundness needs only that each listed set is an extended logical, which is verified;
completeness is recorded but not needed).

    PYTHONPATH=.:tests uv run python -m search.experiments.e040.wlist --code bb90 --kind X --type A1B2B3A2A3B1 --w 7
"""
from __future__ import annotations

import argparse
import json
import pickle
import time

from search.experiments.e040.codes import MOD, OUT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--kind", required=True)
    ap.add_argument("--type", required=True)
    ap.add_argument("--w", type=int, required=True)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--split", type=int, default=1)
    a = ap.parse_args()
    C = MOD[a.code]
    from search.experiments.e032.dext import hooks_first
    o = C.parse_order(a.type)
    E = C.ext_general(a.kind, [o] * C.N2)
    orb, reps, nh = hooks_first(E)
    t0 = time.time()
    log = []
    s, n, c = C.dfs(E, a.w, stopfirst=0, workers=a.workers, split=a.split, cases=range(nh), orbit=orb, reps=reps, log=log)
    trunc = any(int(l.split("found=")[1].split()[0]) >= 100000 for l in log)
    s = [S for S in s if len(S) == a.w]
    allS = C.expand(E, s)
    C.verify_logicals(E, allS)
    keys = [[E["He"][:, j].tobytes() + E["Le"][:, j].tobytes() for j in S] for S in allS]
    rec = {"code": a.code, "kind": a.kind, "type": a.type, "w": a.w, "n": len(allS), "complete": bool(c and not trunc),
           "sec": round(time.time() - t0, 1)}
    pickle.dump({"keys": keys, "meta": {**rec, "dext": a.w}}, open(OUT / f"list{a.w}_{a.code}_{a.kind}_{a.type}.pkl", "wb"))
    print(json.dumps(rec), flush=True)
    with open(OUT / "wlist_summary.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")


if __name__ == "__main__":
    main()
