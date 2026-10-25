"""E-038: automorphisms of the measured-check Tanner structure (data permutation pi plus a map of checks) that map
the measured X checks to measured X checks and measured Z checks to measured Z checks (type-preserving), and the
type-swapping ones (X <-> Z, i.e. combined with a transversal Hadamard).  Exhaustive backtracking over data
permutations consistent with check supports.  usage: uv run python -m search.experiments.e038.autos bb18"""
import sys

from search.experiments.e036_audit.core import checks, support


def autos(variant, swap):
    ks = checks(variant)
    sup = {k: frozenset(support(k)) for k in ks}
    X = [k for k in ks if k[0] == "X"]
    Z = [k for k in ks if k[0] == "Z"]
    tgtX, tgtZ = (Z, X) if swap else (X, Z)
    setsX = {sup[k] for k in tgtX}
    setsZ = {sup[k] for k in tgtZ}
    # qubit signature: (#X checks, #Z checks) containing it
    def sig(q, A, B):
        return (sum(q in sup[k] for k in A), sum(q in sup[k] for k in B))
    out = []
    perm = {}

    def consistent():
        for k in X + Z:
            img = [perm[q] for q in sup[k] if q in perm]
            if len(img) < 6:
                continue
            S = frozenset(img)
            if S not in (setsX if k[0] == "X" else setsZ):
                return False
        return True

    def rec(q):
        if q == 18:
            out.append(dict(perm))
            return
        for t in range(18):
            if t in perm.values():
                continue
            if sig(q, X, Z) != sig(t, tgtX, tgtZ):
                continue
            perm[q] = t
            if consistent():
                rec(q + 1)
            del perm[q]
    rec(0)
    return out


if __name__ == "__main__":
    v = sys.argv[1] if len(sys.argv) > 1 else "bb18"
    for swap in (False, True):
        a = autos(v, swap)
        print(v, "type-swapping" if swap else "type-preserving", len(a))
        for p in a[:8]:
            print("  ", [p[q] for q in range(18)])
