"""Audit claim 3: assume only layers 1 and 7 (edge-checked) are right: A terms fixed; X-check B terms in layers 3,4,5
and Z-check B^T terms in layers 3,4,5 permuted independently (36 combos).  d_circ histogram."""
import itertools, json
from search.experiments.e036_audit.core import checks, legal
from search.experiments.e036_audit.a4_robust import dc
out = {}
for variant in ("bb18", "q1863"):
    h = {}
    for px in itertools.permutations([4, 3, 5]):
        for pz in itertools.permutations([3, 4, 5]):
            SX = [None, 1, *px, 0, 2]
            SZ = [0, 2, *pz, 1, None]
            T = {}
            for k in checks(variant):
                sl = SX if k[0] == "X" else SZ
                t = [None] * 6
                for s, term in enumerate(sl):
                    if term is not None:
                        t[term] = s + 1
                T[k] = t
            ok, _ = legal(T, variant, 7)
            v = str(dc(T, variant, 3)) if ok else "illegal"
            h[v] = h.get(v, 0) + 1
    out[variant] = h
print(json.dumps(out))
