"""E-039 audit a5: symmetries of the 14-measured-check Tanner graph of Kunlun [[18,4,4]] (own computation).
(1) the 9 torus translations x^i y^j (acting on both blocks; check row r = 3a + b <-> monomial x^a y^b, data L_i / R_i
    likewise) -- which ones map the measured X rows to measured X rows and measured Z rows to measured Z rows;
(2) ALL permutations of the 18 data qubits that map the set of measured check supports onto itself, type-preserving
    or X<->Z swapping (exact enumeration by backtracking on the bipartite incidence structure).
usage: uv run python -m search.experiments.e039_audit.a5_sym"""
import itertools

import numpy as np

from search.experiments.e036_audit.core import HX_FULL, HZ_FULL
from search.experiments.e039_audit import fcore as F


def rows_of(H):
    return [frozenset(np.nonzero(r)[0].tolist()) for r in H]


def translations():
    out = []
    for i, j in itertools.product(range(3), repeat=2):
        perm = {}
        for blk in (0, 9):
            for a, b in itertools.product(range(3), repeat=2):
                perm[blk + 3 * a + b] = blk + 3 * ((a + i) % 3) + (b + j) % 3
        out.append(((i, j), perm))
    return out


if __name__ == "__main__":
    fx, fz = rows_of(HX_FULL), rows_of(HZ_FULL)
    mx = {s for k in F.KS if k[0] == "X" for s in [frozenset(F.SUPP[k])]}
    mz = {s for k in F.KS if k[0] == "Z" for s in [frozenset(F.SUPP[k])]}
    # sanity: translations are automorphisms of the full code
    for (i, j), p in translations():
        full_ok = {frozenset(p[q] for q in s) for s in fx} == set(fx) and {frozenset(p[q] for q in s) for s in fz} == set(fz)
        img_x = {frozenset(p[q] for q in s) for s in mx}
        img_z = {frozenset(p[q] for q in s) for s in mz}
        print("translation", (i, j), "full-code automorphism", full_ok, "preserves measured set", img_x == mx and img_z == mz)
    # exhaustive: automorphisms of the bipartite incidence graph data -- measured checks, check nodes coloured by type
    # (type-preserving) or with the X/Z colours exchanged (swap); a data permutation preserving the support sets
    # is exactly the data part of such a graph isomorphism (supports are distinct, so the check part is determined).
    import networkx as nx
    from networkx.algorithms.isomorphism import GraphMatcher

    def graph(swap):
        G = nx.Graph()
        for q in range(18):
            G.add_node(("d", q), c="d")
        for k in F.KS:
            t = k[0] if not swap else ("Z" if k[0] == "X" else "X")
            G.add_node(("c", k), c=t)
            for q in F.SUPP[k]:
                G.add_edge(("c", k), ("d", q))
        return G
    G0 = graph(False)
    for swap in (False, True):
        GM = GraphMatcher(G0, graph(swap), node_match=lambda a, b: a["c"] == b["c"])
        perms = set()
        for m in GM.isomorphisms_iter():
            perms.add(tuple(m[("d", q)][1] for q in range(18)))
        print("swap" if swap else "type-preserving", "data permutations:", len(perms))
        for p in sorted(perms):
            print("   ", list(p))
