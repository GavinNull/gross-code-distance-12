"""E-040: recompute sector coverage from witness files (vec.test on every sector-signature representative), then
signature-level survivors (both sectors uncovered).  Writes survivors2_<code>_P<P>.json.

    PYTHONPATH=.:tests uv run python -m search.experiments.e040.combine2 --code gross --P 10 --X a.jsonl b.jsonl --Z c.jsonl
"""
from __future__ import annotations

import argparse
import json

import numpy as np

from search.experiments.e040 import vec
from search.experiments.e040.bulk import Sector
from search.experiments.e040.codes import OUT
from search.experiments.e040.sweep import groups, sector_key


def coverage(code, P, kind, files, W):
    rows, keys, g = groups(P, kind)
    reps = [rows[g[k][0]] for k in keys]
    tH = np.array([(r["tx"] if kind == "X" else r["tz"]) for r in reps])
    tR = np.array([(r["tz"] if kind == "X" else r["tx"]) for r in reps])
    S0 = Sector(code, kind, reps[0]["tx"], reps[0]["tz"], P)
    wt = np.full(len(reps), 99)
    seen = set()
    for fp in files:
        for l in open(fp):
            w = json.loads(l)
            if w["weight"] > W:
                continue
            key = json.dumps(w["faults"])
            if key in seen:
                continue
            seen.add(key)
            f = [tuple(frozenset(y) if isinstance(y, list) else y for y in x) for x in w["faults"]]
            m = vec.test(S0, f, tH, tR, P)
            wt[m] = np.minimum(wt[m], len(f))
    return rows, {k: int(wt[i]) for i, k in enumerate(keys)}, len(seen)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--W", type=int, default=11)
    ap.add_argument("--X", nargs="*", default=[])
    ap.add_argument("--Z", nargs="*", default=[])
    a = ap.parse_args()
    rows, cx, nx = coverage(a.code, a.P, "X", a.X, a.W)
    _, cz, nz = coverage(a.code, a.P, "Z", a.Z, a.W)
    surv, hist = [], {}
    for r in rows:
        w = min(cx[sector_key(r, "X")], cz[sector_key(r, "Z")])
        hist[w] = hist.get(w, 0) + 1
        if w == 99:
            surv.append(r)
    res = {"code": a.code, "P": a.P, "W": a.W, "patterns_X": nx, "patterns_Z": nz,
           "X_uncovered": sum(v == 99 for v in cx.values()), "Z_uncovered": sum(v == 99 for v in cz.values()),
           "signatures": len(rows), "survivors": len(surv), "hist": {str(k): v for k, v in sorted(hist.items())}}
    print(json.dumps(res))
    (OUT / f"survivors2_{a.code}_P{a.P}.json").write_text(json.dumps(surv))


if __name__ == "__main__":
    main()
