"""E-021 step 1: which hook supports can sit inside a low-weight logical?

For a check of type `kind` and a subset T of its 6 labels (|T| = 2 pair, 3 triple), count the extended-code
logicals of weight <= W that consist of the column e_T (the residual support T) plus data columns only:
x = e_T + (W-1 data), H x = 0, L x != 0.  For |T| = 2, W = 11 these are exactly the "10 data + 1 pair-hook"
single-hook logicals of any order whose prefix pair or suffix pair is T (r4 == prefix pair mod stabiliser).
By the 72-element translation symmetry of the code, the count does not depend on the check, so check 0 suffices.

Uses the E-014 128-bit DFS (dfs128_all.c, complete, prints every solution once).

    PYTHONPATH=. uv run python -m search.experiments.e021.pairs --kind X --size 2 --W 11
"""
from __future__ import annotations

import argparse
import itertools
import json
import subprocess
from pathlib import Path

import numpy as np

from search.experiments.e018 import common as C
from search.experiments.e021.mono import LAB, table

OUT = Path("results/E-021-gross-new-orders")
BIN = OUT / "dfs128_all"


def build_bin():
    if not BIN.exists():
        subprocess.run(["cc", "-O3", "-o", str(BIN), "search/experiments/e014/dfs128_all.c"], check=True)


def write_instance(kind, extra_supports, path):
    """Data columns (orbit 1) + extra columns (orbit 0 for the first, 2.. for others).  Case 0 starts at col 144."""
    H, L = C.HLk(kind)
    cols = [(H[:, j], L[:, j], 1) for j in range(144)]
    for t, S in enumerate(extra_supports):
        cols.append(((H[:, list(S)].sum(1) % 2).astype(np.uint8), (L[:, list(S)].sum(1) % 2).astype(np.uint8),
                     0 if t == 0 else 2))
    r = H.shape[0]
    with open(path, "w") as f:
        f.write(f"{r} {len(cols)} {3 if len(extra_supports) > 1 else 2}\n")
        for h, lv, o in cols:
            hm = sum(1 << int(i) for i in np.nonzero(h)[0])
            lm = sum(1 << int(i) for i in np.nonzero(lv)[0])
            f.write(f"{hm & ((1 << 64) - 1)} {hm >> 64} {lm} {o}\n")
        reps = [144, 0] + ([145] if len(extra_supports) > 1 else [])
        f.write(" ".join(map(str, reps)) + "\n")


def run(kind, T, W, tag):
    build_bin()
    tab = table()[kind]
    S = tuple(sorted(int(tab[0][k]) for k in T))
    p = OUT / f"inst_{tag}.txt"
    write_instance(kind, [S], p)
    res = subprocess.run([str(BIN), str(p), str(W), "0"], capture_output=True, text=True, check=True).stdout
    sols = []
    summ = ""
    for line in res.splitlines():
        if line.startswith("FOUND"):
            cols = tuple(sorted(int(c) for c in line.split("cols:")[1].split()))
            sols.append(cols)
        elif line.startswith("SUMMARY"):
            summ = line
    return S, sols, summ


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", default="X")
    ap.add_argument("--size", type=int, default=2)
    ap.add_argument("--W", type=int, default=11)
    a = ap.parse_args()
    out = {}
    for T in itertools.combinations(range(6), a.size):
        name = "".join(LAB[k] for k in T)
        S, sols, summ = run(a.kind, T, a.W, f"{a.kind}_{name}_W{a.W}")
        ws = sorted({len(s) for s in sols})
        print(a.kind, name, S, "n_sols", len(sols), "weights", ws, summ, flush=True)
        out[name] = {"support": S, "n": len(sols), "sols": sols, "summary": summ}
    (OUT / f"pairs_{a.kind}_size{a.size}_W{a.W}.json").write_text(json.dumps(out))


if __name__ == "__main__":
    main()
