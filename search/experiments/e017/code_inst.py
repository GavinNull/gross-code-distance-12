"""E-017: DFS instance for a plain CSS code (end-cycle code of the morphing circuit, or gross), for dfsw.c.

Rows = checks of the other type, columns = qubits, Le = opposite-type logical basis (column flips logical i).
Symmetry: translations t in K acting on left qubits (end-cycle qubits are the mid-cycle left qubits L(g));
used only if they map the check rowspace to itself (checked) -- then logicals map to logicals.
Two orbits are expected (end-cycle 'left' = even, 'right' = odd left qubits).
Usage: uv run python -m search.experiments.e017.code_inst --j 0 --P X --out .../ec_j0_X.txt
"""
from __future__ import annotations

import argparse
import json

import numpy as np

from search.experiments.e017.morph import TWO_GROSS, Morph, logicals, rank


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hom", default="x")
    ap.add_argument("--j", type=int, default=0)
    ap.add_argument("--P", default="X", help="type of the logical error searched for")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    M = Morph(TWO_GROSS, a.hom)
    ec = M.end_cycle_checks(a.j)
    Hs, Ho = (ec["X"], ec["Z"]) if a.P == "X" else (ec["Z"], ec["X"])
    Lo = logicals(Ho, Hs)
    code = TWO_GROSS
    elems = code.elems()
    n = Hs.shape[1]
    perms = []
    for t in [g for g in elems if M.f(g) == 0]:
        perm = np.array([code.idx(code.mul(elems[q], t)) for q in range(n)])
        Ho2 = np.zeros_like(Ho)
        Ho2[:, perm] = Ho
        Hs2 = np.zeros_like(Hs)
        Hs2[:, perm] = Hs
        if rank(np.vstack([Ho, Ho2])) == rank(Ho) and rank(np.vstack([Hs, Hs2])) == rank(Hs):
            perms.append(perm)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x
    for perm in perms:
        for q in range(n):
            ra, rb = find(q), find(int(perm[q]))
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    roots = sorted(set(find(q) for q in range(n)))
    orb = {r: i for i, r in enumerate(roots)}
    R = Ho.shape[0]
    with open(a.out, "w") as fh:
        fh.write(f"{R} {n} {len(roots)}\n")
        for q in range(n):
            words = []
            for k in range(5):
                v = 0
                for b in range(64):
                    i = 64 * k + b
                    if i < R and Ho[i, q]:
                        v |= 1 << b
                words.append(f"{v:x}")
            lm = int(sum(int(Lo[i, q]) << i for i in range(Lo.shape[0])))
            fh.write(" ".join(words) + f" {lm} {orb[find(q)]}\n")
        fh.write(" ".join(str(r) for r in roots) + "\n")
    meta = {"rows": R, "n": n, "group": len(perms), "orbits": len(roots), "k": int(Lo.shape[0])}
    json.dump(meta, open(a.out + ".json", "w"))
    print(meta)


if __name__ == "__main__":
    main()
