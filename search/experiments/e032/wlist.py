"""E-032 (copy of e028/wlist.py; gross via e032.common, weight <= 11 < d = 12 so hook-orbit cases remain complete) step 2: for a side class (kind, per-check label orders given by a colouring sub-group + per-coset orders, or
uniform), complete d_ext proof (W = w-1 complete DFS, 0 solutions) and complete weight-w list (W = w complete DFS,
every solution printed, orbit-expanded under the order-preserving translation group, each verified).  Cases: hook-column
orbits only (every extended logical of weight <= 9 contains a hook column since data-only logicals have weight >= 10).
Saved by (H,L) keys.

    PYTHONPATH=.:tests uv run python -m search.experiments.e032.wlist --kind X --orders A1A2A3B2B1B3 --w 8
"""
from __future__ import annotations

import argparse
import collections
import json
import pickle
import time

from search.experiments.e032 import common as C
from search.experiments.e032.dext import cosets, dext_dfs


def labord_of(sub, orders_s):
    ords = [C.parse_order(o) for o in orders_s.split(",")]
    if sub in ("", "all"):
        assert len(ords) == 1
        return [ords[0]] * C.N2
    gens = [tuple(int(v) for v in g.split(",")) for g in sub.split(";")]
    colv, m, _, _ = cosets(gens)
    assert len(ords) == m
    return [ords[colv[i]] for i in range(C.N2)]


def tag_of(kind, sub, orders_s, w):
    return f"w{w}_{kind}_{sub.replace(';', '_').replace(',', '') or 'all'}_" + orders_s.replace(",", "-")


def composition(E, S):
    out = []
    for j in S:
        sups = E["col_sups"][j]
        if any(len(s) == 1 for s in sups):
            continue
        out.append(min(min(len(s), 6 - len(s)) for s in sups))
    return tuple(sorted(out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True)
    ap.add_argument("--sub", default="all")
    ap.add_argument("--orders", required=True)
    ap.add_argument("--w", type=int, default=8)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--split", type=int, default=1)
    ap.add_argument("--dmin", type=int, default=0, help="asserted d_ext (default: w)")
    a = ap.parse_args()
    a.dmin = a.dmin or a.w
    kind = a.kind
    lab = labord_of(a.sub, a.orders)
    E = C.ext_general(kind, lab)
    tag = tag_of(kind, a.sub, a.orders, a.w)
    res = {"kind": kind, "sub": a.sub, "orders": a.orders, "N": E["N"], "group": len(E["group"]),
           "orbits": len(E["reps"])}
    t0 = time.time()
    lo = []
    s0, n0, c0 = dext_dfs(E, a.dmin - 1, stopfirst=0, workers=a.workers, split=a.split, log=lo)
    assert c0 and not s0, "d_ext < dmin"
    res.update(lower_W=a.dmin - 1, lower_nodes=n0, lower_sec=round(time.time() - t0, 1))
    t1 = time.time()
    log = []
    s, n, c = dext_dfs(E, a.w, stopfirst=0, workers=a.workers, split=a.split, log=log)
    assert c
    s = [S for S in s if len(S) == a.w]   # with dmin < w the DFS also prints the weight-(<w) logicals
    found = sum(int(l.split("found=")[1].split()[0]) for l in log)
    assert found >= len(s) and all(int(l.split("found=")[1].split()[0]) < 100000 for l in log), "printing truncated"
    allS = C.expand(E, s)
    C.verify_logicals(E, allS)
    assert all(len(S) == a.w for S in allS)
    keys = [[E["He"][:, j].tobytes() + E["Le"][:, j].tobytes() for j in S] for S in allS]
    comp = collections.Counter(composition(E, S) for S in allS)
    res.update(reps=len(s), total=len(allS), nodes=n, sec=round(time.time() - t1, 1),
               composition={str(k): v for k, v in sorted(comp.items())})
    pickle.dump({"keys": keys, "meta": res, "colset": sorted(C.keyset(E))}, open(C.OUT / f"{tag}.pkl", "wb"))
    print(json.dumps(res), flush=True)
    with open(C.OUT / "wlist_summary.jsonl", "a") as f:
        f.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    main()
