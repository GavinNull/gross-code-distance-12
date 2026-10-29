"""E-040: signatures whose best found witness weight (min over the two sectors) equals the maximum over T(P) --
candidates for the best d_circ at period P.  Writes best_<code>_P<P>.json (rows) and prints their type pairs.

    PYTHONPATH=.:tests uv run python -m search.experiments.e040.best --code gross --P 8 --tagX .. --tagZ ..
"""
from __future__ import annotations

import argparse
import collections
import json

from search.experiments.e040.codes import MOD, OUT
from search.experiments.e040.combine import load
from search.experiments.e040.lists import orbit_reps, type_rep
from search.experiments.e040.sweep import load_rows, sector_key


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--tagX", required=True)
    ap.add_argument("--tagZ", required=True)
    a = ap.parse_args()
    C = MOD[a.code]
    mx, mz = load(a.tagX), load(a.tagZ)
    rows = load_rows(a.P)
    ws = []
    for r in rows:
        cx, wx = mx[sector_key(r, "X")]
        cz, wz = mz[sector_key(r, "Z")]
        ws.append((wx if cx >= 0 else 99, wz if cz >= 0 else 99))
    top = max(min(w) for w in ws)
    sel = [i for i, w in enumerate(ws) if min(w) == top]
    cnt = collections.Counter()
    for i in sel:
        r = rows[i]
        tx, tz = type_rep(a.code, tuple(r["ox"])), type_rep(a.code, tuple(r["oz"]))
        cnt[(C.name(tuple(r["ox"])), C.name(tx), orbit_reps(a.code, "X", tx)[0],
             C.name(tuple(r["oz"])), C.name(tz), orbit_reps(a.code, "Z", tz)[0], ws[i])] += 1
    for k, v in cnt.most_common():
        print(v, k)
    print(json.dumps({"code": a.code, "P": a.P, "max_best": top, "n": len(sel), "type_pairs": len(cnt)}))
    (OUT / f"best_{a.code}_P{a.P}.json").write_text(json.dumps([dict(rows[i], w=ws[i]) for i in sel]))


if __name__ == "__main__":
    main()
