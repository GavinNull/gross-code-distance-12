"""B8: E-015 negative claim "every two-colour LRC on gross has d_ext <= 10" (X side, all three Z2 homomorphisms).

Own construction of the family: X check g (g = i*6 + j in Z12 x Z6) touches L-qubit g + a_t (A terms x^3, y, y^2) and
R-qubit g + b_t (B terms y^3, x, x^2); LRC template order = A block permuted by pi, then B block permuted by sigma
(Z checks: B block then A block).  Colour of g = (u*i + v*j) mod 2.  'proper' = no data qubit twice in one slot.
Witness finder: search.noninterleaved.heur.heur_min (lead's heuristic, used only to FIND); every witness is
verified here with the auditor's own He / Le (He x = 0, Le x != 0, |x| <= 10).
Logic (as in E-015): a witness for the class test (residuals of colour-0 checks only, order b) kills every state
using b on colour 0 (more columns only lower d_ext) and, by translating with an odd element, on colour 1.
usage: b8_gross_twocol.py <kind X|Z> <hom 10|01|11> <workers>
"""
import itertools
import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import a1_gross  # noqa: E402
import extx  # noqa: E402
from gf2 import logical_basis  # noqa: E402

OUT = Path("results/E-014-E-015-audit")
l, m = 12, 6
n2 = 72
AT = [(3, 0), (0, 1), (0, 2)]
BT = [(0, 3), (1, 0), (2, 0)]
S3 = list(itertools.permutations(range(3)))
BLOCKS = [(p, s) for p in S3 for s in S3]
HX, HZ = a1_gross.bb_mats()
LX = logical_basis(HZ, HX)
LZ = logical_basis(HX, HZ)


def add(g, t, sgn=1):
    i, j = divmod(g, m)
    return ((i + sgn * t[0]) % l) * m + (j + sgn * t[1]) % m


def nb(kind, g):
    """[A-term neighbours (3), B-term neighbours (3)] as data columns."""
    if kind == "X":
        return [add(g, a) for a in AT], [n2 + add(g, b) for b in BT]
    return [n2 + add(g, a, -1) for a in AT], [add(g, b, -1) for b in BT]


for g in range(n2):
    a, b = nb("X", g)
    assert sorted(a + b) == list(np.nonzero(HX[g])[0])
    a, b = nb("Z", g)
    assert sorted(a + b) == list(np.nonzero(HZ[g])[0])


def order(kind, g, blk):
    pi, sg = blk
    A, B = nb(kind, g)
    a = [A[pi[k]] for k in range(3)]
    b = [B[sg[k]] for k in range(3)]
    return a + b if kind == "X" else b + a


def colour(u, v):
    return [(u * (g // m) + v * (g % m)) % 2 for g in range(n2)]


def proper(kind, col, blocks):
    used = set()
    for g in range(n2):
        for k, d in enumerate(order(kind, g, blocks[col[g]])):
            if (d, k) in used:
                return False
            used.add((d, k))
    return True


def ext(kind, orders_by_check):
    """orders_by_check: list over checks of an order or None (no residuals)."""
    H, L = (HZ, LZ) if kind == "X" else (HX, LX)
    oo = [o for o in orders_by_check if o is not None]
    return extx.build(H, L, oo, 2 * n2)


def find_witness(He, Le, target, seeds, trials):
    from search.noninterleaved.heur import heur_min
    best = None
    for sd in seeds:
        w, x, _ = heur_min(He, Le, trials=trials, seed=sd, lns_starts=16, stop_at=target - 1)
        if x is not None:
            v = np.zeros(He.shape[1], int); v[list(x)] = 1
            ok = not ((He @ v) % 2).any() and ((Le @ v) % 2).any()
            if ok and (best is None or len(set(x)) < len(best)):
                best = sorted(set(int(c) for c in x))
        if best is not None and len(best) < target:
            break
    return best


def job(args):
    kind, u, v, what, payload, seeds, trials = args
    col = colour(u, v)
    if what == "class":
        blk = BLOCKS[payload]
        e = ext(kind, [order(kind, g, blk) if col[g] == 0 else None for g in range(n2)])
    else:
        e0, e1 = payload
        e = ext(kind, [order(kind, g, BLOCKS[e0] if col[g] == 0 else BLOCKS[e1]) for g in range(n2)])
    wit = find_witness(e["He"], e["Le"], 11, seeds, trials)
    return dict(what=what, payload=payload, w=None if wit is None else len(wit), witness=wit,
                witness_supports=None if wit is None else [e["members"][j][0] for j in wit])


if __name__ == "__main__":
    kind, hk, workers = sys.argv[1], sys.argv[2], int(sys.argv[3])
    u, v = int(hk[0]), int(hk[1])
    col = colour(u, v)
    res = {"kind": kind, "hom": hk}
    with Pool(workers) as p:
        cls = list(p.imap_unordered(job, [(kind, u, v, "class", b, (0, 1, 2, 3), 300) for b in range(36)]))
        alive = sorted(r["payload"] for r in cls if r["w"] is None or r["w"] > 10)
        res["class"] = sorted(cls, key=lambda r: r["payload"])
        res["class_alive"] = alive
        res["class_alive_blocks"] = [BLOCKS[b] for b in alive]
        states = [(a, b) for a in alive for b in alive if proper(kind, col, {0: BLOCKS[a], 1: BLOCKS[b]})]
        res["proper_states_from_alive"] = states
        res["all_proper_states_count"] = sum(proper(kind, col, {0: BLOCKS[a], 1: BLOCKS[b]}) for a in range(36) for b in range(36))
        st = list(p.imap_unordered(job, [(kind, u, v, "state", s, (0, 1, 2, 3, 4, 5), 1000) for s in states]))
        res["states"] = st
        res["states_unkilled"] = [r["payload"] for r in st if r["w"] is None or r["w"] > 10]
    print(json.dumps({k: res[k] for k in ("kind", "hom", "class_alive", "class_alive_blocks", "proper_states_from_alive",
                                          "all_proper_states_count", "states_unkilled")}, default=str))
    print("class witness weights:", sorted((r["payload"], r["w"]) for r in res["class"]))
    print("state witness weights:", [(r["payload"], r["w"]) for r in res["states"]])
    (OUT / f"b8_gross_{kind}_{hk}.json").write_text(json.dumps(res, indent=1, default=str))
