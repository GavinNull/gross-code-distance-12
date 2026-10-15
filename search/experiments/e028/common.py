"""E-028 shared code for [[90,8,10]] (IBM 2308.07915 Table 3: l=15, m=3, A = x^9 + y + y^2, B = 1 + x^2 + x^7;
evaluator task bb90-dcirc).  Port of e018/common + e021/mono + e021/extgen + e024b/common with the code as a parameter.

Indexing (evaluator bb_matrices, kron(S_l^a, S_m^b)): check / data index i = a*m + b, a in Z_15, b in Z_3; data columns
0..44 = left block, 45..89 = right block.  Labels 0..5 = A1 A2 A3 B1 B2 B3 (A = [x^9, y, y^2], B = [1, x^2, x^7]).
X check i touches L[A_p(i)] (label p) and R[B_p(i)] (label 3+p); Z check i touches R[A_p^T(i)] (label p) and
L[B_p^T(i)] (label 3+p).  Translation (a,b) maps check i -> tr(i) and label k of check i to label k of check tr(i).

kind 'X' = X-check hooks (X errors) with (HZ, LZ) = Z-basis memory;  kind 'Z' = Z-check hooks with (HX, LX).
Extended code (Strikis 2603.05481 Def. 2): data columns + every proper suffix of every check's order, merged by
(H column, L column) key, zero columns dropped.
"""
from __future__ import annotations

import itertools
import os
import subprocess
import tempfile
import time
from functools import lru_cache
from pathlib import Path

import numpy as np

from evaluators.tasks import build_code, get_task

OUT = Path("results/E-028-bb90-interleaved")
L_, M_ = 15, 3
N2 = L_ * M_
NQ = 2 * N2
LAB = ["A1", "A2", "A3", "B1", "B2", "B3"]
A_EXP = [(9, 0), (0, 1), (0, 2)]
B_EXP = [(0, 0), (2, 0), (7, 0)]
D_CODE = 10
BIN = OUT / "dfs_first"
BINALL = OUT / "dfs128_all"


@lru_cache(maxsize=None)
def css():
    c, _ = build_code(get_task("bb90-dcirc"), None)
    assert c.n == 90 and c.k == 8
    return c


def HLk(kind):
    c = css()
    H, L = (c.HZ, c.LZ) if kind == "X" else (c.HX, c.LX)
    return np.asarray(H, np.uint8) % 2, np.asarray(L, np.uint8) % 2


def idx(a, b):
    return (a % L_) * M_ + (b % M_)


def tr(a, b):
    p = np.array([idx(i // M_ + a, i % M_ + b) for i in range(N2)])
    return p, np.concatenate([p, p + N2])


GROUP = [(a, b) for a in range(L_) for b in range(M_)]


@lru_cache(maxsize=None)
def table():
    """T[kind][i][k] = data column of label k in check i."""
    T = {"X": np.zeros((N2, 6), int), "Z": np.zeros((N2, 6), int)}
    for i in range(N2):
        a, b = divmod(i, M_)
        for p in range(3):
            # A_p as matrix kron(S^ea, S^eb): row i has its 1 at column (a+ea, b+eb)
            ea, eb = A_EXP[p]
            T["X"][i, p] = idx(a + ea, b + eb)
            T["Z"][i, p] = N2 + idx(a - ea, b - eb)          # A_p^T
            ea, eb = B_EXP[p]
            T["X"][i, 3 + p] = N2 + idx(a + ea, b + eb)
            T["Z"][i, 3 + p] = idx(a - ea, b - eb)           # B_p^T
    c = css()
    for kind, H in (("X", np.asarray(c.HX) % 2), ("Z", np.asarray(c.HZ) % 2)):
        for i in range(N2):
            assert sorted(T[kind][i]) == sorted(np.nonzero(H[i])[0].tolist()), (kind, i)
    for (ga, gb) in GROUP:
        pr, pc = tr(ga, gb)
        for kind in "XZ":
            for i in range(N2):
                assert all(T[kind][pr[i]][k] == pc[T[kind][i][k]] for k in range(6))
    return T


def name(o):
    return "".join(LAB[k] for k in o)


def parse_order(s):
    return tuple(LAB.index(s[i:i + 2]) for i in range(0, 12, 2))


def residuals(order):
    return [tuple(sorted(order[l - 1:])) for l in range(2, len(order) + 1)]


def type_key(o):
    P1, T, P3 = frozenset(o[:2]), frozenset(o[:3]), frozenset(o[4:])
    Tc = frozenset(range(6)) - T
    return min((tuple(sorted(P1)), tuple(sorted(T)), tuple(sorted(P3))),
               (tuple(sorted(P3)), tuple(sorted(Tc)), tuple(sorted(P1))))


def all_types():
    """the 90 extended-code types of one check (canonical order representatives)."""
    seen, out = set(), []
    for o in itertools.permutations(range(6)):
        k = type_key(o)
        if k not in seen:
            seen.add(k); out.append(o)
    assert len(out) == 90
    return out


def resid_sets(o):
    return {frozenset(o[2:]), frozenset(o[3:]), frozenset(o[4:])}


def class_orders(o):
    """8 orders with the same extended-code type (s12, s56, rev)."""
    out = set()
    for sw1, sw2, rev in itertools.product((0, 1), (0, 1), (0, 1)):
        x = list(o)
        if sw1:
            x[0], x[1] = x[1], x[0]
        if sw2:
            x[4], x[5] = x[5], x[4]
        if rev:
            x = x[::-1]
        out.add(tuple(x))
    return sorted(out)


# ------------------------------------------------------------------ extended code

def group_of(kind_unused, labord):
    return [(a, b) for (a, b) in GROUP
            if all(tuple(labord[int(tr(a, b)[0][i])]) == tuple(labord[i]) for i in range(N2))]


def ext_general(kind, labord, group=None):
    H, L = HLk(kind)
    T = table()[kind]
    ords = [[int(T[i][k]) for k in labord[i]] for i in range(N2)]
    supports = [(j,) for j in range(NQ)] + [s for o in ords for s in residuals(o)]
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
    group = group if group is not None else group_of(kind, labord)
    supidx = {S: i for i, S in enumerate(supports)}
    perms = []
    for a, b in group:
        _, pc = tr(a, b)
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
            "reps": reps, "N": N, "key_idx": key_idx}


def keyset(E):
    return frozenset(E["He"][:, j].tobytes() + E["Le"][:, j].tobytes() for j in range(E["N"]))


def key_of(kind, qs):
    H, L = HLk(kind)
    qs = list(qs)
    return (H[:, qs].sum(1) % 2).astype(np.uint8).tobytes() + (L[:, qs].sum(1) % 2).astype(np.uint8).tobytes()


@lru_cache(maxsize=None)
def realisations(kind):
    """key -> list of (check a, frozenset U of labels) over label subsets of size 2..4."""
    T = table()[kind]
    out = {}
    for a in range(N2):
        for size in (2, 3, 4):
            for U in itertools.combinations(range(6), size):
                out.setdefault(key_of(kind, [int(T[a][x]) for x in U]), []).append((a, frozenset(U)))
    return out


# ------------------------------------------------------------------ DFS (E-014 algorithm, audited)

def build_bins():
    OUT.mkdir(parents=True, exist_ok=True)
    if not BIN.exists():
        subprocess.run(["cc", "-O3", "-o", str(BIN), "search/experiments/e021/dfs_first.c"], check=True)
    if not BINALL.exists():
        subprocess.run(["cc", "-O3", "-o", str(BINALL), "search/experiments/e014/dfs128_all.c"], check=True)


def write_inst(E, path, orbit=None, reps=None):
    He, Le = E["He"], E["Le"]
    orb = E["orbit"] if orbit is None else orbit
    reps = E["reps"] if reps is None else reps
    r, N = He.shape
    assert r <= 128 and Le.shape[0] <= 30
    with open(path, "w") as f:
        f.write(f"{r} {N} {len(reps)}\n")
        for j in range(N):
            hm = sum(1 << int(i) for i in np.nonzero(He[:, j])[0])
            lm = sum(1 << int(i) for i in np.nonzero(Le[:, j])[0])
            f.write(f"{hm & ((1 << 64) - 1)} {hm >> 64} {lm} {orb[j]}\n")
        f.write(" ".join(map(str, reps)) + "\n")


def dfs(E, W, stopfirst=1, workers=4, split=1, log=None, cases=None, orbit=None, reps=None):
    """Complete DFS for extended logicals of weight <= W (E-014 orbit case split).  `cases` restricts to a subset of
    orbit cases (only valid when the caller knows every logical of weight <= W meets one of those orbits' columns
    under the forbidding rule, e.g. all orbits that can occur first).  Returns (sols, nodes, complete)."""
    build_bins()
    fd, path = tempfile.mkstemp(suffix=".txt", dir=OUT)
    os.close(fd)
    write_inst(E, path, orbit, reps)
    nrep = len(E["reps"] if reps is None else reps)
    binp = BIN if stopfirst else BINALL
    cl = list(range(nrep)) if cases is None else list(cases)
    jobs = [(c, (split, s) if split > 1 else None) for c in cl for s in range(split)]
    env = dict(os.environ)
    if stopfirst:
        env["STOPFIRST"] = str(stopfirst)
    sols, nodes, summs = [], 0, []
    running = []
    try:
        while jobs or running:
            while jobs and len(running) < workers:
                cs, sp = jobs.pop(0)
                args = [str(binp), str(path), str(W), str(cs)] + ([str(sp[0]), str(sp[1])] if sp else [])
                of = tempfile.TemporaryFile(mode="w+")
                running.append((subprocess.Popen(args, stdout=of, env=env), of))
            time.sleep(0.01)
            still = []
            for pr, of in running:
                if pr.poll() is None:
                    still.append((pr, of)); continue
                of.seek(0)
                for line in of.read().splitlines():
                    if line.startswith("FOUND"):
                        sols.append(tuple(sorted(int(c) for c in line.split("cols:")[1].split())))
                    elif line.startswith("SUMMARY"):
                        summs.append(line); nodes += int(line.split("nodes=")[1].split()[0])
                    elif line.startswith("STOPPED"):
                        nodes += int(line.split("nodes=")[1])
                of.close()
            running = still
            if stopfirst and sols:
                for pr, of in running:
                    pr.kill(); pr.wait(); of.close()
                running = []
                return sols, nodes, False
    finally:
        for pr, of in running:
            pr.kill(); pr.wait()
        os.remove(path)
    if log is not None:
        log.extend(summs)
    assert len(summs) == len(cl) * split, "a DFS case did not finish"
    return sols, nodes, True


def expand(E, sols):
    out = set()
    for s in sols:
        for P in E["perms"]:
            out.add(tuple(sorted(int(P[j]) for j in s)))
    return sorted(out)


def verify_logicals(E, sols):
    He, Le = E["He"], E["Le"]
    for s in sols:
        assert len(set(s)) == len(s)
        assert not (He[:, list(s)].sum(1) % 2).any() and (Le[:, list(s)].sum(1) % 2).any(), s
