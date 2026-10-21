"""E-032 step 2a: uniform type assignments (every check of a side uses the same order type; full 72-translation
symmetry).  For each of the 90 types per side: complete W=9 DFS (hook-orbit cases only; every extended logical of
weight <= 11 contains a hook column because data-only logicals have weight >= d = 12) -> d_ext >= 10 or a verified
witness of weight <= 9.  Optional: count the weight-10 solutions (complete W=10 enumeration, orbit-expanded).

    PYTHONPATH=.:tests uv run python -m search.experiments.e032.uniform --kind X [--count10 1]
"""
from __future__ import annotations

import argparse
import json
import time

from search.experiments.e032 import common as C
from search.experiments.e032.dext import dext_dfs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--count10", type=int, default=0)
    a = ap.parse_args()
    out = C.OUT / f"uniform_{a.kind}.jsonl"
    done = set()
    if out.exists():
        done = {json.loads(l)["type"] for l in out.read_text().splitlines()}
    for o in C.all_types():
        nm = C.name(o)
        if nm in done:
            continue
        t0 = time.time()
        E = C.ext_general(a.kind, [o] * C.N2)
        s, n, c = dext_dfs(E, 9, stopfirst=1, workers=a.workers)
        rec = {"type": nm, "N": E["N"], "group": len(E["group"]), "orbits": len(E["reps"])}
        if s:
            C.verify_logicals(E, s[:1])
            rec.update(dext_le=len(s[0]), witness=list(s[0]))
        else:
            assert c
            rec.update(dext=10, nodes9=n)
            if a.count10:
                s10, n10, c10 = dext_dfs(E, 10, stopfirst=0, workers=a.workers)
                assert c10
                allS = C.expand(E, [S for S in s10 if len(S) == 10])
                C.verify_logicals(E, allS)
                rec.update(n10=len(allS), reps10=len(s10), nodes10=n10)
        rec["sec"] = round(time.time() - t0, 1)
        print(json.dumps(rec), flush=True)
        with open(out, "a") as f:
            f.write(json.dumps(rec) + "\n")


if __name__ == "__main__":
    main()
