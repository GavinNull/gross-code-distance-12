"""E-024b step 2: for a side class (kind, colouring, per-colour orders), the complete d_ext proof (W=10 full DFS,
0 solutions) and the complete weight-11 list (W=11 full DFS, every solution printed, orbit-expanded under the
order-preserving translation group, each verified He x = 0, Le x != 0).  Saved by (H,L) KEYS so any circuit with the
same extended code can re-index it.

    PYTHONPATH=. uv run python -m search.experiments.e024b.w11 --kind X --col 3,1,1 --orders A1A2A3B3B1B2,... --split 2
"""
from __future__ import annotations

import argparse
import collections
import json
import pickle
import time

from search.experiments.e021.mono import LAB
from search.experiments.e024b.common import OUT, dfs, expand, ext_general, labord, verify_logicals

N2 = 72


def parse_orders(s):
    return tuple(tuple(LAB.index(o[i:i + 2]) for i in range(0, 12, 2)) for o in s.split(","))


def tag_of(kind, col, orders_s):
    return f"{kind}_m{col[0]}_{col[1]}{col[2]}_" + orders_s.replace(",", "-")


def composition(E, S):
    """hook profile: sorted residual sizes of non-data columns (2 = pair, 3 = triple)."""
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
    ap.add_argument("--col", required=True)
    ap.add_argument("--orders", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--split", type=int, default=1)
    ap.add_argument("--skip10", type=int, default=0)
    a = ap.parse_args()
    col = tuple(int(v) for v in a.col.split(","))
    orders = parse_orders(a.orders)
    kind = a.kind
    lab = labord(col, orders)
    E = ext_general(kind, lab)
    tag = tag_of(kind, col, a.orders)
    res = {"kind": kind, "col": col, "orders": a.orders, "N": E["N"], "group": len(E["group"]),
           "orbits": len(E["reps"])}
    t0 = time.time()
    if not a.skip10:
        log10 = []
        s10, n10, c10 = dfs(E, 10, stopfirst=0, workers=a.workers, split=a.split, log=log10)
        res.update(W10_solutions=len(s10), W10_nodes=n10, W10_complete=c10, W10_sec=round(time.time() - t0, 1))
        print(json.dumps(res), flush=True)
        (OUT / f"W10_{tag}.log").write_text("\n".join(log10))
        assert not s10, "d_ext <= 10"
    t1 = time.time()
    log11 = []
    s11, n11, c11 = dfs(E, 11, stopfirst=0, workers=a.workers, split=a.split, log=log11)
    (OUT / f"W11_{tag}.log").write_text("\n".join(log11))
    found = sum(int(l.split("found=")[1].split()[0]) for l in log11)
    assert found == len(s11) and found <= 100000 * len(log11), "printing truncated"
    allS = expand(E, s11)
    verify_logicals(E, allS)
    assert all(len(S) == 11 for S in allS)
    keys = [[E["He"][:, j].tobytes() + E["Le"][:, j].tobytes() for j in S] for S in allS]
    comp = collections.Counter(composition(E, S) for S in allS)
    res.update(W11_reps=len(s11), W11_total=len(allS), W11_nodes=n11, W11_sec=round(time.time() - t1, 1),
               composition={str(k): v for k, v in sorted(comp.items())})
    pickle.dump({"keys": keys, "meta": res}, open(OUT / f"w11_{tag}.pkl", "wb"))
    print(json.dumps(res), flush=True)
    with open(OUT / "w11_summary.jsonl", "a") as f:
        f.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    main()
