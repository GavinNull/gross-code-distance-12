"""E-039 static (complete) enumeration of witness patterns of given slot types for a class.

Pattern = (basis, sorted slots) exactly as e038.cegar.pattern_of: D(q, r), H(k, U, r) (U = set of term indices),
M(c, r); rounds relative (min 0).  The residual of a pattern (XOR of the data sets of its D / H slots) must commute
with every measured reader and have a non-zero observable (necessary for an undetectable logical); all slot multisets
of the requested types with such a residual are listed.

Round vectors.  Completeness argument (journal): a MINIMUM-weight witness is connected in the graph "two slots share a
toggled detector" (each detector is toggled only within one component, so every component cancels by itself; the
residual of one component has a non-zero observable, so that component alone would be a smaller witness).  In W(P)
(any event time in 1..2P-2) every slot of round r toggles detectors only in rounds r-1..r+2 (first-instance offset
j0 - r = floor((t_g - t_f)/P) + 1 in {-1,0,1,2} because |t_g - t_f| <= 2P - 3), so adjacent slots have
|r_a - r_b| <= 3 and a connected witness of 3 slots has sorted round gaps <= 3.  We enumerate exactly those vectors
(GAP = 3); the encoder drops vectors that cannot cancel.  Duplicate identical slots are skipped (they cancel: smaller
witness).
"""
from __future__ import annotations

import itertools

import numpy as np

from search.experiments.e036_audit.core import checks, observables, support

GAP = 3


def valid_table(variant, basis):
    ks = checks(variant)
    rmask = [sum(1 << q for q in support(k)) for k in ks if k[0] == basis]
    lm = [sum(1 << q for q in range(18) if v[q]) for v in observables(variant, basis)]
    m = np.arange(1 << 18, dtype=np.int64)

    def par(x):
        x = x.copy()
        p = np.zeros_like(x)
        while x.any():
            p ^= x & 1
            x >>= 1
        return p
    ok = np.ones(1 << 18, bool)
    for r in rmask:
        ok &= par(m & r) == 0
    anyl = np.zeros(1 << 18, bool)
    for l in lm:
        anyl |= par(m & l) == 1
    return ok & anyl


def slot_types(variant, basis):
    ks = checks(variant)
    D = [(("D", q), 1 << q) for q in range(18)]
    H = []
    for k in ks:
        if k[0] == basis:
            continue
        s = support(k)
        for n in range(2, 6):
            for U in itertools.combinations(range(6), n):
                H.append((("H", k, U), sum(1 << s[a] for a in U)))
    M = [(("M", k), 0) for k in ks if k[0] == basis]
    return D, H, M


def round_vectors(n, gap=GAP):
    out = []
    for v in itertools.product(range(gap * (n - 1) + 1), repeat=n):
        if min(v) != 0:
            continue
        s = sorted(v)
        if all(s[i + 1] - s[i] <= gap for i in range(n - 1)):
            out.append(v)
    return out


def multisets(variant, basis, types):
    """slot-type multisets (tuples of slot heads) whose residual is valid; types e.g. {'HH','HHM','DDH','DHH'}."""
    V = valid_table(variant, basis)
    D, H, M = slot_types(variant, basis)
    pools = {"D": D, "H": H, "M": M}
    out = []
    for t in sorted(types):
        umax = int(t[-1]) if t[-1].isdigit() else 6   # e.g. "DDH2": hooks with |U| <= 2 only
        t = t.rstrip("0123456789")
        letters = sorted(t)
        lists = [pools[c] for c in letters]
        # combinations with repetition across equal letters
        def rec(i, start, acc, mask):
            if i == len(letters):
                if V[mask] and all(len(a[2]) <= umax for a, _ in acc if a[0] == "H"):
                    out.append(tuple(a for a, _ in acc))
                return
            lst = lists[i]
            st = start if i > 0 and letters[i] == letters[i - 1] else 0
            for j in range(st, len(lst)):
                rec(i + 1, j, acc + [lst[j]], mask ^ lst[j][1])
        rec(0, 0, [], 0)
    return out


def patterns_of(basis, heads, gap=GAP):
    """all round assignments of a multiset of slot heads -> canonical patterns (dedup)."""
    out = set()
    for v in round_vectors(len(heads), gap):
        slots = tuple(sorted((h + (r,) for h, r in zip(heads, v)), key=repr))
        if len(set(slots)) < len(slots):
            continue
        out.add((basis, slots))
    return sorted(out, key=repr)   # deterministic clause order (independent of PYTHONHASHSEED)
