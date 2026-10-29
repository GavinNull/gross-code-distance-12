"""E-040 witness finder: lift an extended logical x (list of column keys of the sector's extended code) to a bulk
fault set: one fault per column (any realisation: data cut in any of the 3 slots, or any hook with that image, at any
round) plus measurement flips, total weight <= |x| + e.  (Generalised Lemma 2 with z zero-image faults only;
sound, not complete: pairs of equal-image faults are not used.)  The returned witness is re-verified by
bulk.Sector.is_witness (independent recomputation of detectors and residual).
"""
from __future__ import annotations

import numpy as np

from search.experiments.e040.bulk import Sector


def realisations(S: Sector):
    """key -> list of (fault template with anchor None, [(c', dr)])."""
    H, L = S.H, S.L
    out = {}

    def key(qs):
        v = np.zeros(S.NQ, np.uint8)
        v[list(qs)] = 1
        return (H @ v % 2).astype(np.uint8).tobytes() + (L @ v % 2).astype(np.uint8).tobytes()

    for q in range(S.NQ):
        k = key([q])
        for c, b in S.readers[q]:
            f = ("d", q, b, 0)
            out.setdefault(k, []).append((("d", q, b), S.dets(f)))
    for c in range(S.N2):
        for Sx in S.suffixes():
            qs = [int(S.TH[c][m]) for m in Sx]
            k = key(qs)
            if not (H @ np.bincount(qs, minlength=S.NQ) % 2).any() and not (L @ np.bincount(qs, minlength=S.NQ) % 2).any():
                continue
            out.setdefault(k, []).append((("h", c, Sx), S.dets(("h", c, Sx, 0))))
    return out


def linecost(rs):
    rs = sorted(rs)
    assert len(rs) % 2 == 0
    return sum(rs[i + 1] - rs[i] for i in range(0, len(rs), 2))


def lift(S: Sector, real, x, e, arange=3):
    cols = [real[k] for k in x]
    n = len(cols)
    touch = []
    for opts in cols:
        cs = set()
        for _, ds in opts:
            cs |= {c for c, _ in ds}
        touch.append(cs)
    # a check is "closed" when every column whose image contains it, or whose options touch it, is assigned
    allc = sorted(set().union(*touch))
    who = {c: [i for i in range(n) if c in touch[i]] for c in allc}
    order = [max(range(n), key=lambda i: len(touch[i]))]
    while len(order) < n:
        done = set(order)
        cand = [i for i in range(n) if i not in done]
        order.append(max(cand, key=lambda i: (sum(1 for c in touch[i] if all(j in done or j == i for j in who[c])),
                                               len(touch[i] & set().union(*(touch[j] for j in done))))))
    closes = []
    seen = set()
    for pos, i in enumerate(order):
        done = set(order[:pos + 1])
        cl = [c for c in allc if c not in seen and all(j in done for j in who[c])]
        seen |= set(cl)
        closes.append(cl)
    rounds = {}
    choice = [None] * n

    def add(ds, a, sgn):
        for c, dr in ds:
            r = dr + a
            s = rounds.setdefault(c, {})
            s[r] = s.get(r, 0) ^ 1
            if not s[r]:
                del s[r]

    def rec(pos, cost):
        if pos == n:
            return True
        i = order[pos]
        if pos == 0:
            anchors = [0]
        else:
            anc = set()
            for _, ds in cols[i]:
                for c, dr in ds:
                    if c in rounds:
                        for r in rounds[c]:
                            for t in range(-e, e + 1):
                                anc.add(r + t - dr)
            anchors = sorted(anc) if anc else list(range(-arange, arange + 1))
        for tpl, ds in cols[i]:
            for a in anchors:
                add(ds, a, 1)
                c2 = cost
                ok = True
                for c in closes[pos]:
                    c2 += linecost(rounds.get(c, {}).keys())
                    if c2 > e:
                        ok = False
                        break
                if ok:
                    choice[i] = (tpl, a)
                    if rec(pos + 1, c2):
                        return True
                add(ds, a, -1)
        return False

    if not rec(0, 0):
        return None
    faults = []
    for tpl, a in choice:
        faults.append(tpl + (a,))
    for c, s in rounds.items():
        rs = sorted(s)
        for k in range(0, len(rs), 2):
            for r in range(rs[k], rs[k + 1]):
                faults.append(("m", c, r))
    ok, D, ev = S.is_witness(faults)
    assert ok, ("finder produced a non-witness", D)
    return faults
