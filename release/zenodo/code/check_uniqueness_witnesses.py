"""SM S16, "Uniqueness of the order class": verify the witnesses behind certificates/order_class_uniqueness/.

For every instance (colouring, residual type) and every witness: the assignment gives each check the CNOT order of
its colour; every listed column support is a column of that assignment's extended code (a single data qubit, or a
residual = suffix of length 2, 3 or 4 of some check's order); the columns are distinct as (H, L) columns, at most
10 of them, their H parts sum to zero and their L parts do not, i.e. the assignment has d_ext <= 10.  Every blocked
assignment (the only survivors) has the extended code of a translate of Fig. 12.  Each nogood clause of the CNF
says that not all residual columns of one such witness (or of one of its 72 translates) are present.

    python code/check_uniqueness_witnesses.py
"""
import gzip
import json

import numpy as np

from common_cli import Verdict
from gross12.paths import CERTIFICATES
from sat.common import HLk, LAB, N2, ext_general, fig12_labels, table, tr

V = Verdict()
D = json.load(gzip.open(CERTIFICATES / "order_class_uniqueness" / "witnesses.json.gz"))
T = table()


def lab(s):
    return tuple(LAB.index(s[i:i + 2]) for i in range(0, 12, 2))


def keyset(kind, labs):
    E = ext_general(kind, labs)
    return {E["He"][:, j].tobytes() + E["Le"][:, j].tobytes() for j in range(E["N"])}


f12 = fig12_labels()
f12sets = {}
for kind in "XZ":
    s = set()
    for a in range(12):
        for b in range(6):
            pr, _ = tr(a, b)
            l1 = [None] * N2
            for i in range(N2):
                l1[int(pr[i])] = f12[kind][i]
            s.add(frozenset(keyset(kind, l1)))
    f12sets[kind] = s
tot = bad = 0
for inst in D["instances"]:
    kind, colv = inst["residual_type"], inst["colour_of_check"]
    H, L = HLk(kind)
    nbad = 0
    for w in inst["witnesses"]:
        tot += 1
        labs = [lab(w["assignment"][colv[i]]) for i in range(N2)]
        allowed = {(q,) for q in range(144)}
        for i in range(N2):
            o = [int(T[kind][i][k]) for k in labs[i]]
            allowed |= {tuple(sorted(o[k:])) for k in (2, 3, 4)}
        cols = [tuple(c) for c in w["columns"]]
        keys = []
        for c in cols:
            v = np.zeros(144, np.uint8); v[list(c)] = 1
            keys.append(((H @ v) % 2).tobytes() + ((L @ v) % 2).tobytes())
        acc = np.zeros(H.shape[0] + L.shape[0], np.uint8)
        for k in keys:
            acc ^= np.frombuffer(k, np.uint8)
        ok = (all(c in allowed for c in cols) and len(set(keys)) == len(keys) <= 10
              and not acc[:H.shape[0]].any() and acc[H.shape[0]:].any())
        nbad += not ok
    nblk = sum(frozenset(keyset(kind, [lab(b[colv[i]]) for i in range(N2)])) in f12sets[kind]
               for b in inst["blocked_fig12_translates"])
    bad += nbad
    V(nbad == 0 and nblk == len(inst["blocked_fig12_translates"]),
      f"{inst['instance']}: {len(inst['witnesses']) - nbad}/{len(inst['witnesses'])} witnesses are weight <= 10 extended "
      f"logicals of their assignment; {nblk}/{len(inst['blocked_fig12_translates'])} blocked assignments are Fig. 12 "
      f"translates")
print(f"{tot} witnesses checked, {bad} failures")
V.exit()
