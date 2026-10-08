"""E-019 stage 2: exact end-cycle code distances (adfs, translation-orbit split) for every family member.
Needs results/E-019-morphing-family/ec/<key>_c<c>.npz from construct.py.
usage: uv run python -m search.experiments.e019.endcycle [key ...]
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

from search.experiments.e019.common import HOMS, get_code, logicals, variants
from search.experiments.e019.dfsrun import min_weight, orbits, perm_ok, write_inst

OUT = "/Users/ephemeral/Desktop/qec-ai-search/results/E-019-morphing-family"


def ec_distance(key, Wmax=14):
    name, hom, v = key.split("_")
    code = get_code(name)
    f = HOMS[hom]
    N = code.N
    res = {}
    for c in (0, 1):
        z = np.load(f"{OUT}/ec/{key}_c{c}.npz")
        HX, HZ = z["HX"], z["HZ"]
        LX, LZ = logicals(HX, HZ), logicals(HZ, HX)
        for typ, H, L in (("X", HZ, LZ), ("Z", HX, LX)):
            perms = []
            for i in range(code.l):
                for j in range(code.m):
                    if f((i, j)) != 0:
                        continue
                    p = np.array([code.gid(code.coords(q)[0] + i, code.coords(q)[1] + j) for q in range(N)])
                    if perm_ok(H, L, p):
                        perms.append(p)
            orb = orbits(N, perms)
            path = f"{OUT}/ec/inst_{key}_c{c}_{typ}err.txt"
            norb = write_inst(path, H, L, orb)
            W, sol, log = min_weight(path, norb, Wmax, outdir=f"{OUT}/ec/dfs", Wstart=2)
            if sol is not None:
                x = np.zeros(N, np.uint8)
                x[sol] = 1
                assert not np.any((H.astype(int) @ x) % 2) and np.any((L.astype(int) @ x) % 2)
            res[f"c{c}_{typ}"] = dict(d=W, witness=sol, n_sym=len(perms), norb=norb, log=log)
            print(key, c, typ, "d =", W, "sym", len(perms), "orbits", norb,
                  "sec", round(sum(e["sec"] for e in log), 1), flush=True)
    ds = [r["d"] for r in res.values()]
    out = dict(n=N, k=int(len(logicals(HX, HZ))), d=min(ds) if None not in ds else None, detail=res)
    json.dump(out, open(f"{OUT}/ec/dist_{key}.json", "w"), indent=1)
    return out


if __name__ == "__main__":
    os.makedirs(f"{OUT}/ec/dfs", exist_ok=True)
    keys = sys.argv[1:] or ["_".join(t) for t in variants()]
    for key in keys:
        ec_distance(key)
