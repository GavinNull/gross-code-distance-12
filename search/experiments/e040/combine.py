"""E-040: combine the two sector sweeps: a signature is killed (bulk weight <= W witness in at least one memory basis)
iff its X-sector or its Z-sector signature is covered.  Prints the survivors (both sectors unresolved).

    PYTHONPATH=.:tests uv run python -m search.experiments.e040.combine --code bb90 --P 8 --W 9 [--tagX ..] [--tagZ ..]
"""
from __future__ import annotations

import argparse
import json

import numpy as np

from search.experiments.e040.codes import OUT
from search.experiments.e040.sweep import sector_key


def load(tag):
    z = np.load(OUT / f"{tag}.npz")
    return {tuple(tuple(x) if isinstance(x, list) else x for x in json.loads(k)): (int(c), int(w))
            for k, c, w in zip(z["keys"], z["cover"], z["wt"])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--W", type=int, required=True)
    ap.add_argument("--tagX", default="")
    ap.add_argument("--tagZ", default="")
    a = ap.parse_args()
    tX = a.tagX or f"sweep_{a.code}_P{a.P}_X_W{a.W}"
    tZ = a.tagZ or f"sweep_{a.code}_P{a.P}_Z_W{a.W}"
    mx, mz = load(tX), load(tZ)
    rows = json.loads((OUT / f"sigs_P{a.P}.json").read_text())
    surv, hist = [], {}
    for i, r in enumerate(rows):
        cx, wx = mx[sector_key(r, "X")]
        cz, wz = mz[sector_key(r, "Z")]
        w = min(wx if cx >= 0 else 99, wz if cz >= 0 else 99)
        hist[w] = hist.get(w, 0) + 1
        if w == 99:
            surv.append(i)
    out = {"code": a.code, "P": a.P, "W": a.W, "signatures": len(rows), "survivors": len(surv),
           "min_witness_weight_hist": {str(k): v for k, v in sorted(hist.items())}}
    print(json.dumps(out))
    (OUT / f"survivors_{a.code}_P{a.P}_W{a.W}.json").write_text(json.dumps([rows[i] for i in surv]))


if __name__ == "__main__":
    main()
