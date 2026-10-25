"""E-036 step 1: code checks against the paper (SI Fig. S1, Sec. I.1 logicals); k and d by brute force."""
import itertools
import json

import numpy as np

from search.experiments.e036.common import FIG_S1, OUT, PAPER_LOG, code, full_H, vec, checks
from evaluators.codes import code_dimension


def rank2(M):
    M = (np.array(M, np.uint8) % 2).copy()
    r = 0
    for c in range(M.shape[1]):
        p = [i for i in range(r, M.shape[0]) if M[i, c]]
        if not p:
            continue
        M[[r, p[0]]] = M[[p[0], r]]
        for i in range(M.shape[0]):
            if i != r and M[i, c]:
                M[i] ^= M[r]
        r += 1
    return r


def in_rowspace(H, v):
    return rank2(np.vstack([H, v])) == rank2(H)


def distance(Hc, Hs):
    """min weight of v with Hc v = 0, v not in rowspace(Hs)."""
    n = Hc.shape[1]
    for w in range(1, n + 1):
        for S in itertools.combinations(range(n), w):
            v = np.zeros(n, np.uint8)
            v[list(S)] = 1
            if (Hc @ v % 2).any():
                continue
            if not in_rowspace(Hs, v):
                return w, S
    return None


def main():
    HX, HZ = full_H()
    fig = np.array([[int(ch) for ch in row.replace(" ", "")] for row in FIG_S1.split()]).reshape(9, 18) \
        if False else np.array([[int(ch) for ch in (a + b)] for a, b in
                                (ln.split() for ln in FIG_S1.strip().splitlines())], np.uint8)
    rep = {}
    rep["HX_equals_FigS1"] = bool((fig == HX).all())
    rep["HX_equals_HZ"] = bool((HX == HZ).all())
    rep["col_weights"] = sorted(set(HX.sum(0).tolist()))
    for var in ("bb18", "q1863", "full"):
        c = code(var)
        xs, zs = checks(var)
        r = {"x_checks": xs, "z_checks": zs, "rank_HX": rank2(c.HX), "rank_HZ": rank2(c.HZ),
             "k": int(code_dimension(c.HX, c.HZ))}
        dX = distance(c.HZ, c.HX)  # X-type logical: commutes with Z checks
        dZ = distance(c.HX, c.HZ)
        r["dX"], r["dZ"] = dX[0], dZ[0]
        r["dX_witness"], r["dZ_witness"] = list(dX[1]), list(dZ[1])
        if var in PAPER_LOG:
            LX, LZ = c.LX, c.LZ
            r["paper_LX_commute_HZ"] = bool(not (LX @ c.HZ.T % 2).any())
            r["paper_LZ_commute_HX"] = bool(not (LZ @ c.HX.T % 2).any())
            r["paper_LX_LZ_symplectic_identity"] = bool(((LX @ LZ.T) % 2 == np.eye(len(LX), dtype=np.uint8)).all())
        rep[var] = r
    print(json.dumps(rep, indent=1))
    (OUT / "code18.json").write_text(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
