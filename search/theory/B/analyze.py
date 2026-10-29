"""Structure of the obstructions: for each listed light extended logical S of a schedule,
  - bulk lift (exact), lift on the time circle of N rounds (mod N) for N = 2, 3;
  - a minimal infeasible set of reader constraints (deletion, bulk), and its shape: the columns it involves,
    number of readers, and whether every core reader is 'private' (hit by exactly two columns of S).

  uv run python -m search.theory.B.analyze --code gross --spec search/experiments/e032/u11_spec.json --basis Z \
      --list results/E-032-gross-short-period/w10_X_all_A1A2A3B3B1B2.pkl --orbit-reps
"""
from __future__ import annotations

import argparse
import collections
import json
import pickle

import numpy as np

from search.theory.B.bulk import ROOT, Sched, bulk_lift, code_mats, load_spec
from search.theory.B.check_lists import colopts_for, enum_logicals


def describe_cols(S, cols, sch):
    out = []
    for k in S:
        reals = cols[k]
        tags = []
        for r in reals:
            if r[0] == "d":
                tags.append(f"d{r[1]}")
            else:
                tags.append(f"h{r[1]}.{7 - r[2]}")    # writer . suffix length
        out.append("/".join(tags))
    return out


def core(co, flips=0, mod=0):
    touched = sorted({z for opts in co for o in opts for z in o})
    ign = []
    for z in touched:
        if bulk_lift(co, flips=flips, mod=mod, ignore=ign + [z]) is None:
            ign.append(z)
    return [z for z in touched if z not in ign]


def hits(S, cols, sch):
    """reader -> number of columns of S hitting it oddly (H-image)."""
    h = collections.Counter()
    for k in S:
        v = np.frombuffer(k, np.uint8)[:sch.H.shape[0]]
        for z in np.flatnonzero(v):
            h[int(z)] += 1
    return h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--basis", default="Z")
    ap.add_argument("--list", required=True)
    ap.add_argument("--flips", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--mods", default="2,3")
    ap.add_argument("--core", type=int, default=1)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    sch = Sched(load_spec(a.spec), code_mats(a.code), a.basis)
    cols, zero = sch.ext()
    if a.list.startswith("enum:"):
        L = enum_logicals(sch, cols, int(a.list[5:]))
    else:
        L = pickle.load(open(ROOT / a.list, "rb"))["keys"]
    if a.limit:
        L = L[:a.limit]
    mods = [int(x) for x in a.mods.split(",") if x]
    stats = collections.Counter()
    rows = []
    for i, S in enumerate(L):
        co = colopts_for(S, cols, sch)
        row = {"i": i, "bulk": bulk_lift(co, flips=a.flips) is not None}
        for m in mods:
            row[f"mod{m}"] = bulk_lift(co, flips=a.flips, mod=m) is not None
        if a.core and not row["bulk"]:
            c = core(co, a.flips)
            h = hits(S, cols, sch)
            row["core"] = c
            row["core_hits"] = [h[z] for z in c]
            # columns touching the core
            row["core_cols"] = sorted({j for j, opts in enumerate(co) for o in opts for z in o if z in c})
        row["cols"] = describe_cols(S, cols, sch)
        rows.append(row)
        key = tuple((k, row[k]) for k in ["bulk"] + [f"mod{m}" for m in mods])
        stats[str(key)] += 1
        if a.core and not row["bulk"]:
            stats[f"core_size={len(row['core'])}"] += 1
            stats[f"core_hits={sorted(row['core_hits'])}"] += 1
    res = {"spec": a.spec, "basis": a.basis, "list": a.list, "n": len(L), "flips": a.flips, "stats": dict(stats)}
    print(json.dumps(res), flush=True)
    if a.out:
        json.dump({"res": res, "rows": rows}, open(ROOT / a.out, "w"))


if __name__ == "__main__":
    main()
