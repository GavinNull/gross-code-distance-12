"""Exact bulk lift of every listed light extended logical, for a schedule spec.

  uv run python -m search.theory.B.check_lists --code gross --spec search/experiments/e032/u11_spec.json \
      --basis Z --list results/E-032-gross-short-period/w10_X_all_A1A2A3B3B1B2.pkl --flips 1
The list file holds (H,L)-keys (bytes) of the extended logicals (kind X <-> Z basis).  If --list is 'enum:W' the
logicals of weight <= W are enumerated here (small codes only).
"""
from __future__ import annotations

import argparse
import itertools
import json
import pickle
import time

import numpy as np

from search.theory.B.bulk import Sched, bulk_lift, code_mats, load_spec, ROOT


def colopts_for(S, cols, sch):
    out = []
    for k in S:
        opts = []
        for real in cols[k]:
            opts += sch.options(real)
        out.append(opts)
    return out


def enum_logicals(sch, cols, W):
    """all sets of distinct extended columns of size <= W with H-sum 0 and L-sum != 0 (brute force, small codes)."""
    keys = list(cols)
    nh = sch.H.shape[0]
    vecs = [np.frombuffer(k, np.uint8) for k in keys]
    res = []
    for w in range(1, W + 1):
        for S in itertools.combinations(range(len(keys)), w):
            v = np.bitwise_xor.reduce([vecs[i] for i in S])
            if not v[:nh].any() and v[nh:].any():
                res.append([keys[i] for i in S])
        if res:
            break
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--basis", default="Z")
    ap.add_argument("--list", required=True)
    ap.add_argument("--flips", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    mats = code_mats(a.code)
    spec = load_spec(a.spec) if not a.spec.startswith("{") else json.loads(a.spec)
    sch = Sched(spec, mats, a.basis)
    bad = sch.pairing_ok()
    cols, zero = sch.ext()
    if a.list.startswith("enum:"):
        L = enum_logicals(sch, cols, int(a.list[5:]))
    else:
        d = pickle.load(open(ROOT / a.list, "rb"))
        L = d["keys"]
        assert set(d["colset"]) == set(cols), "list's column set differs from this schedule's extended code"
    if a.limit:
        L = L[:a.limit]
    t0 = time.time()
    lifted = []
    for i, S in enumerate(L):
        co = colopts_for(S, cols, sch)
        r = bulk_lift(co, flips=a.flips)
        if r is not None:
            lifted.append(i)
    res = {"spec": a.spec, "basis": a.basis, "list": a.list, "n": len(L), "weight": len(L[0]) if L else None,
           "flips": a.flips, "pairing_violations": len(bad), "zero_image_hooks": len(zero), "ncols": len(cols),
           "bulk_lifted": len(lifted), "first_lifted": lifted[:10], "sec": round(time.time() - t0, 1)}
    print(json.dumps(res), flush=True)
    if a.out:
        with open(ROOT / a.out, "a") as f:
            f.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    main()
