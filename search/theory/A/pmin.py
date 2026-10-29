"""Theory A, Lemma P: the minimum period of a signature (pi_X, pi_Z, G) is the least P for which the difference
system below is feasible (Bellman-Ford; integral because all bounds are integers):
  x_{pi_X(i+1)} - x_{pi_X(i)} >= 1, x_{pi_X(6)} - x_{pi_X(1)} <= P-3   (same for z)
  G(k,l) P + 1 <= x_{A_k} - z_{B_l} <= G(k,l) P + P - 1,   same for x_{B_l} - z_{A_k}.
"""
from __future__ import annotations

A, B = (0, 1, 2), (3, 4, 5)


def feasible(ox, oz, G, P):
    # nodes 0..5 = x[label], 6..11 = z[label]; constraint v_u - v_w >= c  ->  edge w->u weight c (longest path)
    E = []
    for o, off in ((ox, 0), (oz, 6)):
        for i in range(5):
            E.append((off + o[i], off + o[i + 1], 1))
        E.append((off + o[5], off + o[0], 3 - P))
    for k in range(3):
        for l in range(3):
            g = G[3 * k + l]
            for xa, zb in ((A[k], B[l]), (B[l], A[k])):
                E.append((6 + zb, xa, g * P + 1))          # x - z >= gP+1
                E.append((xa, 6 + zb, -g * P - P + 1))     # z - x >= -gP-P+1
    dist = [0] * 12
    for _ in range(13):
        ch = False
        for w, u, c in E:
            if dist[w] + c > dist[u]:
                dist[u] = dist[w] + c
                ch = True
        if not ch:
            return True
    return False


def pmin(ox, oz, G, Pmax=40):
    for P in range(8, Pmax + 1):
        if feasible(ox, oz, G, P):
            return P
    return None
