"""Auditor's own extended code (Strikis et al. 2603.05481 v2 Def. 2) for the E-013 circuit + symmetry orbits.
Z-type: (HX, LX) + Z-check residual suffixes; X-type: (HZ, LZ) + X-check residual suffixes.
Residual set of a check with order (i1..i6): suffixes {i_l..i_6}, l = 2..6.

Symmetry: translations g = x^a y^b with b even (27 elements) map even rows to even rows and odd to odd, so map
the set of per-check orders (hence the residual set) to itself; they are code automorphisms.  A translation acts
on a column vector of [H; L] by a row permutation on H and an invertible linear map on the logical coordinates
(L rows are a basis of logicals of the other type; a code automorphism maps nontrivial logical classes to nontrivial
ones), hence identical columns map to identical columns and the action descends to merged columns.  This is
verified numerically below (well-definedness + He-row permutation + 'logical-or-not' preserved).
"""
from __future__ import annotations
import sys, json
import numpy as np
sys.path.insert(0, "research/audits/2026-10-05-E-013-scripts")
from aud13 import build, orders, code as mkcode

Z_EVEN_FIX = [3, 4, 5, 2, 1, 0]


def suffixes(o):
    return [tuple(sorted(o[l:])) for l in range(1, len(o))]


def translate_col(c, j, a, b):
    n2 = c.n2
    side, g = (0, j) if j < n2 else (1, j - n2)
    ga, gb = divmod(g, c.m)
    g2 = ((ga + a) % c.l) * c.m + (gb + b) % c.m
    return g2 + side * n2


def ext(kind, ze=Z_EVEN_FIX, **kw):
    """kind 'Z': Z errors, H=HX.  kind 'X': X errors, H=HZ.  Returns dict."""
    c, s = build(ze=ze, **kw)
    od = orders(s)
    if kind == "Z":
        H, L, ords = c.HX, c.logical_x(), od["Z"]
    else:
        H, L, ords = c.HZ, c.logical_z(), od["X"]
    H = H.astype(np.uint8); L = L.astype(np.uint8)
    supports = [(j,) for j in range(c.n)] + [S for o in ords for S in suffixes(o)]
    # merged columns
    key_of, cols, members = {}, [], []
    sup_class = []
    for S in supports:
        h = (H[:, list(S)].sum(1) % 2).astype(np.uint8)
        l = (L[:, list(S)].sum(1) % 2).astype(np.uint8)
        if not h.any() and not l.any():
            sup_class.append(-1); continue
        k = h.tobytes() + l.tobytes()
        if k not in key_of:
            key_of[k] = len(cols); cols.append((h, l)); members.append([])
        sup_class.append(key_of[k]); members[key_of[k]].append(S)
    He = np.array([h for h, l in cols]).T
    Le = np.array([l for h, l in cols]).T
    # group action on merged columns
    supidx = {S: i for i, S in enumerate(supports)}
    group = [(a, b) for a in range(c.l) for b in range(0, c.m, 2)]
    perms = []
    for a, b in group:
        img = []
        for S in supports:
            T = tuple(sorted(translate_col(c, j, a, b) for j in S))
            assert T in supidx, "residual set not invariant"
            img.append(supidx[T])
        P = np.full(len(cols), -1)
        for i, S in enumerate(supports):
            ci = sup_class[i]
            cj = sup_class[img[i]]
            if ci < 0:
                assert cj < 0; continue
            assert P[ci] in (-1, cj), "action not well defined on merged columns"
            P[ci] = cj
        assert sorted(P) == list(range(len(cols)))
        perms.append(P)
    # orbits
    orb = np.full(len(cols), -1); reps = []
    for j in range(len(cols)):
        if orb[j] >= 0: continue
        o = sorted({int(P[j]) for P in perms})
        orb[o] = len(reps); reps.append(j)
    return dict(code=c, H=H, L=L, He=He, Le=Le, members=members, perms=perms, orbit=orb, reps=reps,
                n_raw_residuals=len(supports) - c.n, orders=ords)


def dump_instance(d, path):
    He, Le = d["He"], d["Le"]
    r, N = He.shape
    assert r <= 64 and Le.shape[0] <= 30
    with open(path, "w") as f:
        f.write(f"{r} {N} {len(d['reps'])}\n")
        for j in range(N):
            hm = sum(1 << i for i in np.nonzero(He[:, j])[0])
            lm = sum(1 << i for i in np.nonzero(Le[:, j])[0])
            f.write(f"{hm} {lm} {d['orbit'][j]}\n")
        f.write(" ".join(map(str, d["reps"])) + "\n")


if __name__ == "__main__":
    for kind in "ZX":
        d = ext(kind)
        He = d["He"]
        print(kind, "He", He.shape, "Le", d["Le"].shape, "raw residuals", d["n_raw_residuals"], "orbits", len(d["reps"]),
              "orbit sizes", np.bincount(d["orbit"]).tolist(), "col weights", np.bincount(He.sum(0)).tolist(),
              "row weights", sorted(set(He.sum(1).tolist())))
        # cross-check with lead's ext.py
        from search.noninterleaved.ext import extended_matrices, residual_supports
        sup = [s for o in d["orders"] for s in residual_supports(o)]
        He2, Le2, lab = extended_matrices(d["H"], d["L"], sup)
        A = {He[:, j].tobytes() + d["Le"][:, j].tobytes() for j in range(He.shape[1])}
        B = {He2[:, j].tobytes() + Le2[:, j].tobytes() for j in range(He2.shape[1])}
        print("  same column set as ext.py:", A == B, He2.shape)
        dump_instance(d, f"results/E-013-audit/inst_{kind}.txt")
