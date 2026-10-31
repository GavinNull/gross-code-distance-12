"""E-041 symmetric ansatz: restrict a W/Mg encoding to schedules invariant under an involution g of the symmetry group
(data permutation preserving the measured check set — e038.autos: sigma_p type-preserving, s1 / s2 type-swapping —
optionally composed with time reversal t -> C - t).  Invariance: tau(g(k), g(q)) = f(tau(k, q)) with f(t) = t (no
reversal) or f(t) = C - t (reversal; C = 8 maps the window [s+1, s+7] to [-s+1, -s+7]).
Every invariant schedule is an ordinary schedule of the class: the ansatz is only a restriction used to FIND
solutions (never for impossibility claims).  The image of a legal/undetectable structure under g is again one
(relabelling; transversal Hadamard for type swaps; theory C lemma 4 for reversal), which is why such fixed points are
natural candidates.
"""
from __future__ import annotations

from search.experiments.e036_audit.core import checks, support
from search.experiments.e038.autos import autos
from search.experiments.e038.enc import neg


def perms():
    p = autos("bb18", False)
    s = autos("bb18", True)
    ident = list(range(18))
    sp = [x for x in p if [x[q] for q in range(18)] != ident][0]
    return {"p": sp, "s1": s[0], "s2": s[1]}


def event_map(perm, swap):
    ks = checks("bb18")
    sup = {k: support(k) for k in ks}
    out = {}
    for k in ks:
        img = frozenset(perm[q] for q in sup[k])
        want = ({"X": "Z", "Z": "X"}[k[0]]) if swap else k[0]
        k2 = [c for c in ks if frozenset(sup[c]) == img and c[0] == want]
        assert len(k2) == 1, (k, img)
        k2 = k2[0]
        for a, q in enumerate(sup[k]):
            out[(k, a)] = (k2, sup[k2].index(perm[q]))
    return out


def add_symmetry(E, name, C=8):
    """name in {'p', 's1', 's2', 'pR', 's1R', 's2R'}; adds clauses tau(g e) = f(tau(e)) to encoder E."""
    base, rev = (name[:-1], True) if name.endswith("R") else (name, False)
    perm = perms()[base]
    assert all(perm[perm[q]] == q for q in range(18)), "not an involution"
    em = event_map(perm, base.startswith("s"))
    assert all(em[em[e]] == e for e in em), "event map not an involution"
    n0 = len(E.cl)
    for e, e2 in em.items():
        A, B = E.tau[e], E.tau[e2]
        lo = min(A.lo, B.lo, (C - A.hi) if rev else A.lo) - 1
        hi = max(A.hi, B.hi, (C - A.lo) if rev else A.hi) + 1
        for t in range(lo, hi + 1):
            lb = B.le(t)                                   # tau(e2) <= t
            la = neg(A.le(C - t - 1)) if rev else A.le(t)  # f(tau(e)) <= t
            E.add([neg(lb), la])
            E.add([lb, neg(la)])
    return len(E.cl) - n0
