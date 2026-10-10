"""E-021: extended code of the gross code for ARBITRARY per-check CNOT orders (label orders), its order-preserving
translation group, orbit reduction, and a complete parallel DFS driver (dfs_first.c = e014/dfs128_all.c + STOPFIRST).

Extended columns: data columns + residual suffixes of every check's order (Strikis 2603.05481 Def. 2, as in
e014/gross_ext.py), merged by (H column, L column).  kind 'X' = X-check hooks with (HZ, LZ) (Z-basis memory),
kind 'Z' = Z-check hooks with (HX, LX).

Symmetry: translation (a,b) is a code automorphism mapping label k of check i to label k of check T(i) (asserted).
It preserves the residual set iff labord[T(i)] == labord[i] for all i.  The DFS case split by lowest orbit is the
E-014 construction (complete; audited 2026-10-05).

    d_ext test:  ext_dfs(kind, labord, W=10, stopfirst=1)  -> (found_witness or None, nodes, complete flag)
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from search.experiments.e018 import common as C
from search.experiments.e021.mono import table

OUT = Path("results/E-021-gross-new-orders")
BIN = OUT / "dfs_first"
N2 = 72


def build_bin():
    if not BIN.exists():
        subprocess.run(["cc", "-O3", "-o", str(BIN), "search/experiments/e021/dfs_first.c"], check=True)


def residuals(order):
    return [tuple(sorted(order[l - 1:])) for l in range(2, len(order) + 1)]


def group_of(labord):
    T = table()
    G = []
    for a in range(12):
        for b in range(6):
            pr, pc = C.tr(a, b)
            for kind in "XZ":
                for i in range(N2):
                    assert all(T[kind][pr[i]][k] == pc[T[kind][i][k]] for k in range(6))
            if all(tuple(labord[int(pr[i])]) == tuple(labord[i]) for i in range(N2)):
                G.append((a, b))
    return G


def ext_general(kind, labord):
    """labord: list of 72 label orders (tuples of 0..5) of the checks of type `kind`.
    Returns dict(He, Le, sups (first support per column), all_sups, perms, group, orbit, reps)."""
    H, L = C.HLk(kind)
    T = table()[kind]
    ords = [[int(T[i][k]) for k in labord[i]] for i in range(N2)]
    supports = [(j,) for j in range(2 * N2)] + [s for o in ords for s in residuals(o)]
    key_idx, keys, sup_class, col_sups = {}, [], [], []
    for S in supports:
        h = (H[:, list(S)].sum(1) % 2).astype(np.uint8)
        lv = (L[:, list(S)].sum(1) % 2).astype(np.uint8)
        if not h.any() and not lv.any():
            sup_class.append(-1); continue
        k = h.tobytes() + lv.tobytes()
        if k not in key_idx:
            key_idx[k] = len(keys); keys.append((h, lv)); col_sups.append([])
        sup_class.append(key_idx[k]); col_sups[key_idx[k]].append(S)
    N = len(keys)
    He = np.array([h for h, _ in keys]).T
    Le = np.array([lv for _, lv in keys]).T
    group = group_of(labord)
    supidx = {S: i for i, S in enumerate(supports)}
    perms = []
    for a, b in group:
        _, pc = C.tr(a, b)
        P = np.full(N, -1)
        for i, S in enumerate(supports):
            Tt = tuple(sorted(int(pc[j]) for j in S))
            assert Tt in supidx
            ci, cj = sup_class[i], sup_class[supidx[Tt]]
            if ci < 0:
                assert cj < 0; continue
            assert P[ci] in (-1, cj)
            P[ci] = cj
        assert sorted(P.tolist()) == list(range(N))
        perms.append(P)
    orb = np.full(N, -1)
    reps = []
    for j in range(N):
        if orb[j] >= 0:
            continue
        o = sorted({int(P[j]) for P in perms})
        orb[o] = len(reps)
        reps.append(j)
    return {"He": He, "Le": Le, "col_sups": col_sups, "perms": np.array(perms), "group": group, "orbit": orb,
            "reps": reps, "N": N}


def write_inst(E, path):
    He, Le, orb, reps = E["He"], E["Le"], E["orbit"], E["reps"]
    r, N = He.shape
    assert r <= 128
    with open(path, "w") as f:
        f.write(f"{r} {N} {len(reps)}\n")
        for j in range(N):
            hm = sum(1 << int(i) for i in np.nonzero(He[:, j])[0])
            lm = sum(1 << int(i) for i in np.nonzero(Le[:, j])[0])
            f.write(f"{hm & ((1 << 64) - 1)} {hm >> 64} {lm} {orb[j]}\n")
        f.write(" ".join(map(str, reps)) + "\n")


def _run_case(path, W, cs, stopfirst):
    env = dict(os.environ)
    if stopfirst:
        env["STOPFIRST"] = str(stopfirst)
    out = subprocess.run([str(BIN), str(path), str(W), str(cs)], capture_output=True, text=True, env=env).stdout
    sols, nodes, stopped = [], 0, False
    for line in out.splitlines():
        if line.startswith("FOUND"):
            sols.append(tuple(sorted(int(c) for c in line.split("cols:")[1].split())))
        elif line.startswith("SUMMARY"):
            nodes = int(line.split("nodes=")[1].split()[0])
        elif line.startswith("STOPPED"):
            stopped = True; nodes = int(line.split("nodes=")[1])
    return cs, sols, nodes, stopped


def ext_dfs(kind, labord, W, stopfirst=1, workers=4, E=None):
    """Complete search for extended logicals of weight <= W.  With stopfirst=1 returns at the first witness
    (remaining cases are still run to completion but their results ignored once one is found? no: we cancel by
    running cases in rounds).  Returns (sols, nodes, complete)."""
    build_bin()
    E = E or ext_general(kind, labord)
    fd, path = tempfile.mkstemp(suffix=".txt", dir=OUT)
    os.close(fd)
    write_inst(E, path)
    sols, nodes = [], 0
    cases = list(range(len(E["reps"])))
    try:
        with ThreadPoolExecutor(workers) as ex:
            # run in waves of `workers` so that a found witness stops further waves
            for k in range(0, len(cases), workers):
                for cs, s, n, st in ex.map(lambda c: _run_case(path, W, c, stopfirst), cases[k:k + workers]):
                    sols += s; nodes += n
                if stopfirst and sols:
                    return sols, nodes, False
    finally:
        os.remove(path)
    return sols, nodes, True


def expand(E, sols):
    """Orbit-expand solutions (column tuples) under the group."""
    out = set()
    for s in sols:
        for P in E["perms"]:
            out.add(tuple(sorted(int(P[j]) for j in s)))
    return sorted(out)
