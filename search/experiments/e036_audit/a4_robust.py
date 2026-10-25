"""Audit claim 3 robustness: the Fig. S3 reconstruction depends on mapping the IBM slot labels A1..B3 to the Kunlun
monomials.  Re-evaluate d_circ (Sym, R = 1..3, both bases, reset and no-reset) for all 36 relabelings
(permute A1,A2,A3 among themselves and B1,B2,B3 among themselves) and for the A<->B swap (72 total)."""
import itertools
import json

from search.experiments.e036_audit.core import Sym, checks, legal, min_weight_le

SX = [None, 1, 4, 3, 5, 0, 2]
SZ = [0, 2, 3, 4, 5, 1, None]


def sched(variant, perm):
    T = {}
    for k in checks(variant):
        sl = SX if k[0] == "X" else SZ
        t = [None] * 6
        for s, term in enumerate(sl):
            if term is not None:
                t[perm[term]] = s + 1
        T[k] = t
    return T


def dc(T, variant, wmax):
    best = 99
    for R in (1, 2, 3):
        for b in ("Z", "X"):
            for reset in (True, False):
                w, _ = min_weight_le(Sym(variant, b, T, R, reset=reset).mechs(), wmax)
                if w is not None:
                    best = min(best, w)
    return best if best < 99 else f">{wmax}"


out = {}
for variant in ("bb18", "q1863"):
    res = {}
    for pa in itertools.permutations(range(3)):
        for pb in itertools.permutations(range(3)):
            for swap in (False, True):
                perm = list(pa) + [3 + x for x in pb]
                if swap:
                    perm = perm[3:] + perm[:3]
                T = sched(variant, perm)
                ok, _ = legal(T, variant, 7)
                key = f"{perm}"
                res[key] = dc(T, variant, 3) if ok else "illegal"
    vals = {}
    for v in res.values():
        vals[str(v)] = vals.get(str(v), 0) + 1
    out[variant] = {"histogram": vals, "identity": res[str([0, 1, 2, 3, 4, 5])]}
    print(variant, json.dumps(out[variant]))
json.dump(out, open("results/E-036-audit/a4_robust.json", "w"), indent=1)
