"""Audit E-020 b5: baselines.strikis.strikis_fig12 has 2 lattice isomorphisms; iso 1 gives different per-check CNOT
orders than iso 0 (the one E-018/E-020 use).  Is the iso-1 order assignment the image of iso 0's under a relabelling
(data permutation sigma, check permutation pi, optionally swapping X<->Z types) that maps every check's ordered
CNOT list to its image's?  If so, every result for iso 0 transfers verbatim."""
from baselines.bb_code import gross_code
from baselines.strikis import strikis_fig12
from search.noninterleaved.ext import orders_from_schedule
g = gross_code()
o0 = orders_from_schedule(strikis_fig12(g, 0)[0])
o1 = orders_from_schedule(strikis_fig12(g, 1)[0])
def lst(o):
    return [("X", tuple(r)) for r in o[0]] + [("Z", tuple(r)) for r in o[1]]
A, B = lst(o0), lst(o1)
def index(L):
    idx = {}
    for c, (t, r) in enumerate(L):
        for p, q in enumerate(r):
            idx.setdefault((t, q, p), []).append(c)
    return idx
IA, IB = index(A), index(B)
print("max multiplicity of (type, qubit, position):", max(len(v) for v in IA.values()), max(len(v) for v in IB.values()))
import sys
sys.setrecursionlimit(100000)


def extend(pi, sig, sw):
    """complete pi (checks) / sig (data) by DFS; returns True if a full consistent relabelling exists."""
    pi, sig = dict(pi), dict(sig)
    # propagate sig from pi
    changed = True
    while changed:
        changed = False
        for c, cc in list(pi.items()):
            for p, q in enumerate(A[c][1]):
                qq = B[cc][1][p]
                if q in sig:
                    if sig[q] != qq:
                        return False
                else:
                    if qq in set(sig.values()):
                        return False
                    sig[q] = qq; changed = True
        # forced check images: check d of A whose qubits are all mapped
        for d in range(144):
            if d in pi:
                continue
            t, r = A[d]
            if all(q in sig for q in r):
                cands = IB.get((sw(t), sig[r[0]], 0), [])
                cands = [e for e in cands if list(B[e][1]) == [sig[q] for q in r] and e not in pi.values()]
                if not cands:
                    return False
                pi[d] = cands[0]; changed = True
    if len(pi) == 144:
        return len(set(pi.values())) == 144 and len(set(sig.values())) == 144
    # branch on an unmapped check that has a mapped qubit
    for d in range(144):
        if d in pi:
            continue
        t, r = A[d]
        for p, q in enumerate(r):
            if q in sig:
                for e in IB.get((sw(t), sig[q], p), []):
                    if e in pi.values():
                        continue
                    pi2 = dict(pi); pi2[d] = e
                    if extend(pi2, sig, sw):
                        return True
                return False
    return False


found = []
for swap in (False, True):
    sw = (lambda t: {"X": "Z", "Z": "X"}[t]) if swap else (lambda t: t)
    for c1 in range(144):
        if B[c1][0] != sw(A[0][0]):
            continue
        if extend({0: c1}, {}, sw):
            found.append((swap, c1))
print("relabellings iso0 -> iso1 (X check 0 image choices) found:", len(found), found[:6])
