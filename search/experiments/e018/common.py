"""E-018 shared code: gross code (evaluator task gross-dcirc), Fig. 12 schedule, its extended codes, the 24-element
translation group acting on extended columns, and the weight-11 extended logicals enumerated in stage a.

Extended code construction and column indexing are identical to search/experiments/e014/gross_ext.py (data columns
0..143, then the residual suffixes of every check in row order, merged by (H column, L column)); the column indices
therefore coincide with those of results/E-014-gross-dcirc11-proof/inst_{X,Z}.txt, which `ext()` asserts.
The (H, L) matrices are the evaluator's (build_code of task gross-dcirc).  The merge structure of columns does not
depend on the logical basis (L' = M L + K H), so keys computed with the evaluator's L are compatible.

kind "X" = X-check hooks = X errors = (HZ, LZ) = Z-basis memory;  kind "Z" = (HX, LX) = X-basis memory.
"""
from __future__ import annotations

import json
import pickle
from functools import lru_cache
from pathlib import Path

import numpy as np

from baselines.bb_code import gross_code
from baselines.strikis import strikis_fig12
from evaluators.tasks import build_code, get_task
from search.noninterleaved.ext import orders_from_schedule, residual_supports

E14 = Path("results/E-014-gross-dcirc11-proof")
OUT = Path("results/E-018-gross-interleaved-12")
L_, M_ = 12, 6
N2 = L_ * M_


@lru_cache(maxsize=None)
def css():
    c, _ = build_code(get_task("gross-dcirc"), None)
    g = gross_code()
    assert (np.asarray(c.HX) == np.asarray(g.HX)).all() and (np.asarray(c.HZ) == np.asarray(g.HZ)).all()
    return c


@lru_cache(maxsize=None)
def fig12():
    g = gross_code()
    sched, meta = strikis_fig12(g)
    return sched, meta


def orders():
    """(xo, zo): per-check data-column CNOT orders of Fig. 12 (rows in HX / HZ order)."""
    return orders_from_schedule(fig12()[0])


def HLk(kind):
    c = css()
    H, L = (c.HZ, c.LZ) if kind == "X" else (c.HX, c.LX)
    return np.asarray(H, np.uint8) % 2, np.asarray(L, np.uint8) % 2


def tr(a, b):
    p = np.array([((i // M_ + a) % L_) * M_ + (i % M_ + b) % M_ for i in range(N2)])
    return p, np.concatenate([p, p + N2])


def key_of_vec(H, L, v):
    return ((H @ v) % 2).astype(np.uint8).tobytes() + ((L @ v) % 2).astype(np.uint8).tobytes()


@lru_cache(maxsize=None)
def ext(kind):
    """Extended code of `kind` with E-014 column indexing.
    Returns dict: keys (list of bytes per column), He, Le, supports (list of supports per column), perms (24 x N),
    group."""
    H, L = HLk(kind)
    xo, zo = orders()
    ords = xo if kind == "X" else zo
    supports = [(j,) for j in range(2 * N2)] + [tuple(sorted(s)) for o in ords for s in residual_supports(o)]
    key_idx, keys, sup_class, col_sups = {}, [], [], []
    for S in supports:
        v = np.zeros(2 * N2, np.int64); v[list(S)] = 1
        k = key_of_vec(H, L, v)
        if not (H @ v % 2).any() and not (L @ v % 2).any():
            sup_class.append(-1); continue
        if k not in key_idx:
            key_idx[k] = len(keys); keys.append(k); col_sups.append([])
        sup_class.append(key_idx[k]); col_sups[key_idx[k]].append(S)
    N = len(keys)
    He = np.array([np.frombuffer(k[:H.shape[0]], np.uint8) for k in keys]).T
    Le = np.array([np.frombuffer(k[H.shape[0]:], np.uint8) for k in keys]).T
    group = [tuple(x) for x in json.loads((E14 / "meta.json").read_text())["group"]]
    supidx = {S: i for i, S in enumerate(supports)}
    perms = []
    for a, b in group:
        _, pc = tr(a, b)
        P = np.full(N, -1)
        for i, S in enumerate(supports):
            T = tuple(sorted(int(pc[j]) for j in S))
            ci, cj = sup_class[i], sup_class[supidx[T]]
            if ci < 0:
                assert cj < 0; continue
            assert P[ci] in (-1, cj)
            P[ci] = cj
        assert sorted(P.tolist()) == list(range(N))
        perms.append(P)
    # consistency with the E-014 instance file (He bits, column order)
    lines = (E14 / f"inst_{kind}.txt").read_text().split("\n")
    r, Nf, _ = map(int, lines[0].split())
    assert Nf == N and r == H.shape[0]
    for j in range(N):
        lo, hi, lm, o = map(int, lines[1 + j].split())
        hm = lo | (hi << 64)
        assert hm == sum(1 << int(i) for i in np.nonzero(He[:, j])[0]), (kind, j)
    return {"keys": keys, "He": He, "Le": Le, "col_sups": col_sups, "perms": np.array(perms), "group": group,
            "key_idx": key_idx}


def load_logicals(kind):
    """All weight-11 extended logicals of `kind` (sorted tuples of column indices), from stage a."""
    return pickle.load(open(OUT / f"w11_all_{kind}.pkl", "rb"))
