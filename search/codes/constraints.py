"""Hardware-motivated constraint checks: check weight, Tanner-graph connectivity, thickness <= 2.

Tanner graph vertices: X checks, Z checks, L data, R data (each |G| of them).  Every edge carries a
term label t in 0..5 = [A1, A2, A3, B1, B2, B3]:
    X-check i -- L[A_t(i)]   and   Z-check i -- R[A_t^T(i)]      (t = 0, 1, 2)
    X-check i -- R[B_t(i)]   and   Z-check i -- L[B_t^T(i)]      (t = 3, 4, 5)
i.e. the six permutation matrices A_t, B_t each contribute one perfect matching on the X side and one
on the Z side.

Thickness criterion (sufficient, certified): we look for a split of the six term labels into two
groups S, S^c such that both edge-induced subgraphs are planar (networkx.check_planarity, which
returns a certificate embedding).  If one exists the thickness is <= 2 -> status "le2".
arXiv:2308.07915 (Sec. 4, Lemma 2) proves thickness <= 2 for BB codes by decomposing the Tanner
graph into two planar subgraphs built from the term matrices; I could not consult the paper text in
this session to confirm *which* label split the proof uses, so instead of hard-coding it we try all
31 label splits, which contains any split of that kind.  If no label split works the status is
"unknown" (thickness could still be 2 with a split that does not respect labels).
A lower bound is automatic: the Tanner graph is bipartite with E = 12|G| > 2V - 4 = 8|G| - 4, so it
is never planar (thickness >= 2); "le2" therefore means thickness == 2.
"""
from __future__ import annotations

import itertools

import networkx as nx
import numpy as np


def check_weights(HX: np.ndarray, HZ: np.ndarray, max_weight: int = 6) -> dict:
    rw = int(max(HX.sum(1).max(), HZ.sum(1).max()))
    cw = int(max(HX.sum(0).max(), HZ.sum(0).max()))
    # qubit degree in the Tanner graph = column weight of HX + column weight of HZ
    qdeg = int((HX.sum(0) + HZ.sum(0)).max())
    return {"max_row_weight": rw, "max_col_weight": cw, "max_qubit_degree": qdeg,
            "weight_ok": rw <= max_weight}


def tanner_edges(code) -> list[tuple[str, str, int]]:
    """Labelled edges (u, v, term) of the Tanner graph of a GroupAlgebraCode."""
    N = code.n2
    E = []
    for t in range(6):
        for i in range(N):
            b, j = code.x_check_neighbor(t, i)
            E.append((f"X{i}", f"{b}{j}", t))
            b, j = code.z_check_neighbor(t, i)
            E.append((f"Z{i}", f"{b}{j}", t))
    return E


def num_components(code) -> int:
    """Connected components of the Tanner graph (scipy csgraph; nodes X | L | R | Z blocks)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    N = code.n2
    off = {"X": 0, "L": N, "R": 2 * N, "Z": 3 * N}
    us, vs = [], []
    for t in range(6):
        for i in range(N):
            b, j = code.x_check_neighbor(t, i)
            us.append(i)
            vs.append(off[b] + j)
            b, j = code.z_check_neighbor(t, i)
            us.append(off["Z"] + i)
            vs.append(off[b] + j)
    M = coo_matrix((np.ones(len(us)), (us, vs)), shape=(4 * N, 4 * N))
    return int(connected_components(M, directed=False)[0])


def is_connected(code) -> bool:
    return num_components(code) == 1


def thickness_le2(code, splits=None) -> dict:
    """Return {"status": "le2"|"unknown", "split": [labels of the first planar part] or None}."""
    E = tanner_edges(code)
    if splits is None:
        # all S containing label 0, S != full set (S^c must be non-empty)
        splits = [tuple([0] + list(c)) for r in range(0, 5) for c in itertools.combinations(range(1, 6), r)]
    planar_cache: dict[tuple, bool] = {}

    def planar(labels):
        key = tuple(sorted(labels))
        if key not in planar_cache:
            G = nx.Graph()
            G.add_edges_from((u, v) for u, v, t in E if t in key)
            planar_cache[key] = nx.check_planarity(G)[0]
        return planar_cache[key]

    # try balanced 3+3 splits first (most likely to succeed), then the rest
    splits = sorted(splits, key=lambda s: abs(len(s) - 3))
    for S in splits:
        Sc = tuple(t for t in range(6) if t not in S)
        if planar(S) and planar(Sc):
            return {"status": "le2", "split": list(S), "split_terms": _names(S) + " | " + _names(Sc)}
    return {"status": "unknown", "split": None, "split_terms": ""}


def _names(S):
    nm = ["A1", "A2", "A3", "B1", "B2", "B3"]
    return ",".join(nm[t] for t in S)


def check_constraints(code, max_weight: int = 6, thickness: bool = True) -> dict:
    out = check_weights(code.HX, code.HZ, max_weight)
    out["connected"] = is_connected(code)
    if thickness:
        th = thickness_le2(code)
        out["thickness"] = th["status"]
        out["thickness_split"] = th["split_terms"]
    return out
