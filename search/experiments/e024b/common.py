"""E-024b shared code: extended-code "types" per check, colourings, DFS driver (own temp dir), realisations.

A per-check label order o determines the check's extended-code contribution only through the residual sets
{o[1:], o[2:], o[3:], o[4:]} (sizes 5,4,3,2; size 5 == a data column modulo the check stabiliser), i.e. through
(P1, T, P3) = (o[:2], o[:3], o[4:]) as sets; reversal gives the same columns.  `TYPES[kind]` = the 45 canonical
orders whose prefix triple lies in an allowed triple class (no "triple + 9 data" weight-10 logical; E-021 pairs.py).

Colouring (m, alpha, beta): colour of check i = (alpha*a + beta*b) mod m, i = 6a + b (translations act by (a,b)).
"""
from __future__ import annotations

import itertools
import json
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

import numpy as np

from search.experiments.e018 import common as C
from search.experiments.e021.extgen import ext_general, write_inst
from search.experiments.e021.mono import LAB, table

OUT = Path("results/E-024b-gross12-other-classes")
E21 = Path("results/E-021-gross-new-orders")
BIN = OUT / "dfs_first"
BINALL = OUT / "dfs128_all"
N2 = 72


def build_bins():
    OUT.mkdir(parents=True, exist_ok=True)
    if not BIN.exists():
        subprocess.run(["cc", "-O3", "-o", str(BIN), "search/experiments/e021/dfs_first.c"], check=True)
    if not BINALL.exists():
        subprocess.run(["cc", "-O3", "-o", str(BINALL), "search/experiments/e014/dfs128_all.c"], check=True)


def name(o):
    return "".join(LAB[k] for k in o)


@lru_cache(maxsize=None)
def bad_triples(kind):
    d = json.loads((E21 / f"pairs_{kind}_size3_W11.json").read_text())
    bad = set()
    for nm, v in d.items():
        if v["n"] > 0:
            T = frozenset(LAB.index(nm[i:i + 2]) for i in range(0, 6, 2))
            bad.add(T); bad.add(frozenset(range(6)) - T)
    return bad


@lru_cache(maxsize=None)
def pair_counts(kind):
    d = json.loads((E21 / f"pairs_{kind}_size2_W11.json").read_text())
    return {frozenset(LAB.index(nm[i:i + 2]) for i in (0, 2)): v["n"] for nm, v in d.items()}


def type_key(o):
    P1, T, P3 = frozenset(o[:2]), frozenset(o[:3]), frozenset(o[4:])
    Tc = frozenset(range(6)) - T
    return min((tuple(sorted(P1)), tuple(sorted(T)), tuple(sorted(P3))),
               (tuple(sorted(P3)), tuple(sorted(Tc)), tuple(sorted(P1))))


@lru_cache(maxsize=None)
def types(kind):
    bad = bad_triples(kind)
    seen, out = set(), []
    for T in itertools.combinations(range(6), 3):
        if frozenset(T) in bad:
            continue
        Tc = tuple(sorted(set(range(6)) - set(T)))
        for P1 in itertools.combinations(T, 2):
            for P3 in itertools.combinations(Tc, 2):
                m3 = [k for k in T if k not in P1][0]
                m4 = [k for k in Tc if k not in P3][0]
                o = tuple(P1) + (m3, m4) + tuple(P3)
                k = type_key(o)
                if k in seen:
                    continue
                seen.add(k)
                out.append(o)
    assert len(out) == 45
    return out


def resid_sets(o):
    """label sets (sizes 2,3,4) realised as residual columns by order o (the size-5 residual is data-equivalent)."""
    return {frozenset(o[2:]), frozenset(o[3:]), frozenset(o[4:])}


def single_hooks(kind, o):
    pc = pair_counts(kind)
    return pc[frozenset(o[:2])] + pc[frozenset(o[4:])]


def class_orders(o):
    """the 8 orders with the same extended-code type as o (within-pair swaps of positions 1-2, 5-6; reversal)."""
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


def colour(col, i):
    m, al, be = col
    a, b = divmod(i, 6)
    return (al * a + be * b) % m


def labord(col, assign):
    """assign: tuple of m orders (per colour) -> list of 72 per-check label orders."""
    return [tuple(assign[colour(col, i)]) for i in range(N2)]


@lru_cache(maxsize=None)
def HL(kind):
    return C.HLk(kind)


def key_of(kind, qs):
    H, L = HL(kind)
    qs = list(qs)
    return (H[:, qs].sum(1) % 2).astype(np.uint8).tobytes() + (L[:, qs].sum(1) % 2).astype(np.uint8).tobytes()


@lru_cache(maxsize=None)
def realisations(kind):
    """key -> list of (check a, frozenset U) over label subsets of size 2..4."""
    T = table()[kind]
    out = {}
    for a in range(N2):
        for size in (2, 3, 4):
            for U in itertools.combinations(range(6), size):
                out.setdefault(key_of(kind, [int(T[a][x]) for x in U]), []).append((a, frozenset(U)))
    return out


def _run_case(binp, path, W, cs, stopfirst, split=None):
    env = dict(os.environ)
    if stopfirst:
        env["STOPFIRST"] = str(stopfirst)
    args = [str(binp), str(path), str(W), str(cs)] + ([str(split[0]), str(split[1])] if split else [])
    out = subprocess.run(args, capture_output=True, text=True, env=env).stdout
    sols, nodes, summ = [], 0, None
    for line in out.splitlines():
        if line.startswith("FOUND"):
            sols.append(tuple(sorted(int(c) for c in line.split("cols:")[1].split())))
        elif line.startswith("SUMMARY"):
            summ = line
            nodes = int(line.split("nodes=")[1].split()[0])
        elif line.startswith("STOPPED"):
            nodes = int(line.split("nodes=")[1])
    return cs, sols, nodes, summ


def dfs(E, W, stopfirst=1, workers=4, split=1, log=None):
    """Complete DFS for extended logicals of weight <= W (E-014 algorithm, orbit case split, optional first-level
    split into `split` parts).  Returns (sols, nodes, complete).  With stopfirst, returns at the first witness and
    kills the still-running sibling cases (by PID)."""
    import time as _t
    build_bins()
    fd, path = tempfile.mkstemp(suffix=".txt", dir=OUT)
    os.close(fd)
    write_inst(E, path)
    binp = BIN if stopfirst else BINALL
    jobs = [(c, (split, s) if split > 1 else None) for c in range(len(E["reps"])) for s in range(split)]
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
            _t.sleep(0.02)
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
    assert len(summs) == len(E["reps"]) * split, "a DFS case did not finish"
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
        assert not (He[:, list(s)].sum(1) % 2).any() and (Le[:, list(s)].sum(1) % 2).any()
