"""E-040: stronger finder (all available lists up to W, measurement flips, one cancelling pair) on a given list of
rows (e.g. best_<code>_P<P>.json), both sectors; records the best weight found per sector and the witnesses.

    PYTHONPATH=.:tests uv run python -m search.experiments.e040.target --code gross --P 8 --rows best_gross_P8.json --W 10
"""
from __future__ import annotations

import argparse
import json
import time

from search.experiments.e040.codes import OUT
from search.experiments.e040.sweep import find, to_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--rows", required=True)
    ap.add_argument("--W", type=int, required=True)
    ap.add_argument("--pairs", type=int, default=1)
    ap.add_argument("--kinds", default="XZ")
    ap.add_argument("--onlypair", type=int, default=0)
    ap.add_argument("--full", type=int, default=1, help="complete anchor window in the lift DFS")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    rows = json.loads((OUT / a.rows).read_text())
    tag = a.tag or f"target_{a.code}_P{a.P}_W{a.W}"
    out = open(OUT / f"{tag}.jsonl", "w")
    for i, r in enumerate(rows):
        rec = {"i": i, "tx": r["tx"], "tz": r["tz"]}
        for kind in a.kinds:
            t0 = time.time()
            S, f, dext = find(a.code, kind, r, a.P, a.W, a.pairs, full=bool(a.full), onlypair=bool(a.onlypair))
            rec[kind] = {"dext": dext, "weight": None if f is None else len(f), "sec": round(time.time() - t0, 1),
                         "faults": None if f is None else to_json(f)}
            if f is not None:
                break     # one sector suffices to bound the circuit
        out.write(json.dumps(rec) + "\n")
        out.flush()
        print(json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != "faults"})
                          for k, v in rec.items()}), flush=True)


if __name__ == "__main__":
    main()
