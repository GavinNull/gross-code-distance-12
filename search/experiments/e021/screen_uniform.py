"""E-021 step 1a: d_ext screen of all UNIFORM per-check orders (every check of a type uses the same label order).

The extended code depends only on (P1, T, P3) = (prefix pair, prefix triple, suffix pair) of the order (residuals:
r5 = data, r4 == P1, r3 == T, r2 = P3 modulo stabilisers), and is invariant under reversal (P1,T,P3) -> (P3,T^c,P1).
Triples T with a weight-10 "T + 9 data" logical (pairs.py --size 3) are skipped (d_ext <= 10 already).
For each remaining class and each kind: complete W=10 DFS (stop at first witness).

    PYTHONPATH=. uv run python -m search.experiments.e021.screen_uniform --kinds XZ --workers 4
"""
from __future__ import annotations

import argparse
import itertools
import json
import time
from pathlib import Path

from search.experiments.e021.extgen import ext_dfs, ext_general
from search.experiments.e021.mono import LAB

OUT = Path("results/E-021-gross-new-orders")


def bad_triples(kind):
    d = json.loads((OUT / f"pairs_{kind}_size3_W11.json").read_text())
    bad = set()
    for name, v in d.items():
        if v["n"] > 0:
            T = tuple(LAB.index(name[i:i + 2]) for i in range(0, 6, 2))
            bad.add(frozenset(T))
            bad.add(frozenset(set(range(6)) - set(T)))
    return bad


def classes(kind):
    bad = bad_triples(kind)
    seen, out = set(), []
    for T in itertools.combinations(range(6), 3):
        if frozenset(T) in bad:
            continue
        Tc = tuple(sorted(set(range(6)) - set(T)))
        for P1 in itertools.combinations(T, 2):
            for P3 in itertools.combinations(Tc, 2):
                key = (P1, T, P3)
                rkey = (P3, Tc, P1)
                if min(key, rkey) in seen:
                    continue
                seen.add(min(key, rkey))
                m3 = [k for k in T if k not in P1][0]
                m4 = [k for k in Tc if k not in P3][0]
                out.append((key, tuple(P1) + (m3, m4) + tuple(P3)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kinds", default="XZ")
    ap.add_argument("--W", type=int, default=10)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    pc = {k: json.loads((OUT / f"pairs_{k}_size2_W11.json").read_text()) for k in "XZ"}
    res_path = OUT / f"screen_uniform_W{a.W}.jsonl"
    done = set()
    if res_path.exists():
        for line in res_path.read_text().splitlines():
            r = json.loads(line); done.add((r["kind"], tuple(r["order"])))
    for kind in a.kinds:
        cl = classes(kind)
        print(kind, len(cl), "classes", flush=True)
        for key, order in cl:
            if (kind, order) in done:
                continue
            t0 = time.time()
            lab = [order] * 72
            E = ext_general(kind, lab)
            sols, nodes, complete = ext_dfs(kind, lab, a.W, stopfirst=1, workers=a.workers, E=E)
            name = lambda ks: "".join(LAB[k] for k in ks)  # noqa: E731
            single = pc[kind][name(order[:2])]["n"] + pc[kind][name(order[4:])]["n"]
            rec = {"kind": kind, "order": list(order), "labels": [LAB[k] for k in order], "N": E["N"],
                   "group": len(E["group"]), "orbits": len(E["reps"]), "witness": [list(s) for s in sols[:1]],
                   "d_ext_ge_W1": (not sols) and complete, "nodes": nodes, "single_hook_per_check": single,
                   "sec": round(time.time() - t0, 1)}
            print(json.dumps(rec), flush=True)
            with open(res_path, "a") as f:
                f.write(json.dumps(rec) + "\n")


if __name__ == "__main__":
    main()
