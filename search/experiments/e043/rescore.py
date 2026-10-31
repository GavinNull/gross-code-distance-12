"""E-043 step 2: re-score every signature of T(P) on BOTH sectors with all of E-040's witness pools.

For a sector signature the best known bulk witness weight is min over all pool witnesses that pass it (E-040 vec.test,
exact bulk detector arithmetic per time vector; witness validity = E-040's audited stim injection).  A full signature
(sigma_X, sigma_Z, G) can attain the bound `target` only if both sectors have no known witness of weight < target.
Output: results/E-043-table/rescore_<code>_P<P>.json with per-sector-key best weights and the candidate signatures
(rows of sigs_P<P>.json, normalised) whose known witnesses are all >= target on both sectors (99 = none known).

  PYTHONPATH=.:tests uv run python -m search.experiments.e043.rescore --code bb90 --P 9 --target 9
"""
from __future__ import annotations

import argparse
import glob
import json
import time

import numpy as np

from search.experiments.e040 import vec
from search.experiments.e040.bulk import Sector
from search.experiments.e040.sweep import groups, hr, sector_key

OUTD = "results/E-043-table"


def best_weights(code, P, kind, pools):
    rows, keys, g = groups(P, kind)
    reps = [rows[g[k][0]] for k in keys]
    tH = np.array([hr(r, kind)[0] for r in reps], np.int64)
    tR = np.array([hr(r, kind)[1] for r in reps], np.int64)
    S0 = Sector(code, kind, reps[0]["tx"], reps[0]["tz"], P)
    wt = np.full(len(keys), 99)
    nw = 0
    for pf in pools:
        for l in open(pf):
            w = json.loads(l)
            f = [tuple(frozenset(y) if isinstance(y, list) else y for y in x) for x in w["faults"]]
            m = vec.test(S0, f, tH, tR, P)
            wt[m] = np.minimum(wt[m], len(f))
            nw += 1
    return rows, keys, wt, nw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--target", type=int, required=True)
    ap.add_argument("--extra", nargs="*", default=[], help="additional witness jsonl files (kind:path)")
    a = ap.parse_args()
    t0 = time.time()
    res = {}
    rows = None
    for kind in ("X", "Z"):
        pools = sorted(glob.glob(f"results/E-040-min-period/sweep_{a.code}_P{a.P}_{kind}_*_witnesses.jsonl"))
        pools += [p.split(":", 1)[1] for p in a.extra if p.startswith(kind + ":")]
        rows, keys, wt, nw = best_weights(a.code, a.P, kind, pools)
        res[kind] = {"keys": keys, "wt": wt, "pools": pools, "n_witnesses": nw}
        print(json.dumps({"kind": kind, "sector_sigs": len(keys), "witnesses": nw,
                          "hist": {int(k): int(v) for k, v in zip(*np.unique(wt, return_counts=True))}}), flush=True)
    idx = {kind: {k: i for i, k in enumerate(res[kind]["keys"])} for kind in ("X", "Z")}
    cands = []
    hist = {}
    for r in rows:
        wx = int(res["X"]["wt"][idx["X"][sector_key(r, "X")]])
        wz = int(res["Z"]["wt"][idx["Z"][sector_key(r, "Z")]])
        b = min(wx, wz)
        hist[b] = hist.get(b, 0) + 1
        if b >= a.target:
            cands.append(dict(r, wX=wx, wZ=wz))
    out = {"code": a.code, "P": a.P, "target": a.target, "signatures": len(rows),
           "bound_hist": {int(k): v for k, v in sorted(hist.items())}, "n_candidates": len(cands),
           "pools": {k: res[k]["pools"] for k in res}, "sec": round(time.time() - t0, 1)}
    print(json.dumps(out), flush=True)
    out["candidates"] = cands
    with open(f"{OUTD}/rescore_{a.code}_P{a.P}.json", "w") as f:
        json.dump(out, f)


if __name__ == "__main__":
    main()
