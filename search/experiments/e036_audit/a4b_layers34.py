"""Audit claim 3: if layers 1, 2, 5, 7 of Fig. S3 are as reconstructed, the only freedom left in layers 3, 4, 6 is
B1<->B2 in the X checks (layers 3/4) and B1T<->B2T in the Z checks (layers 3/4).  Evaluate all 4 combinations."""
import json
from search.experiments.e036_audit.core import Sym, checks, legal, min_weight_le
from search.experiments.e036_audit.a4_robust import dc

for variant in ("bb18", "q1863"):
    for sx in (False, True):
        for sz in (False, True):
            SX = [None, 1, 3 if sx else 4, 4 if sx else 3, 5, 0, 2]
            SZ = [0, 2, 4 if sz else 3, 3 if sz else 4, 5, 1, None]
            T = {}
            for k in checks(variant):
                sl = SX if k[0] == "X" else SZ
                t = [None] * 6
                for s, term in enumerate(sl):
                    if term is not None:
                        t[term] = s + 1
                T[k] = t
            ok, why = legal(T, variant, 7)
            print(json.dumps({"variant": variant, "swapX_B1B2": sx, "swapZ_B1B2": sz, "legal": ok,
                              "dcirc": dc(T, variant, 3) if ok else None}))
