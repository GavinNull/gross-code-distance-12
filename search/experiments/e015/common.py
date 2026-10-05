"""E-015 common code: BB / twisted-torus codes, subgroup colourings, LRC orders, extended codes, DFS instances.

Generalises search/noninterleaved/two_colour.py (BB108 only) to any abelian group code.  Read-only use of
search.codes, search.noninterleaved (order_terms, neighbours, ext), evaluators (heuristic routines via heur.py).

LRC template (as in E-013, colour_search.py): X check prep 0, CNOT slots 1..6 (A block then B block), meas 7;
Z check prep 4, CNOT slots 5,6,7,0,1,2 (B block then A block), meas 3.  Non-interleaved and data-conflict-free
across kinds by construction; inside one kind the per-colour block orders must be a proper edge colouring
(`proper`).  A colouring is a map group element -> colour label; `order_terms(kind, pi, sigma)` = (A perm, B perm).
"""
from __future__ import annotations

import itertools
import json
import time
from functools import lru_cache
from pathlib import Path

import numpy as np

from search.codes.construct import GroupAlgebraCode, bb_code, coprime_bb_code
from search.codes.groups import FiniteGroup
from search.noninterleaved.colour_search import order_terms
from search.noninterleaved.ext import extended_matrices, residual_supports
from search.noninterleaved.schedules import neighbours

OUT = Path("results/E-015-bb-generalization")
OUT.mkdir(parents=True, exist_ok=True)
S3 = list(itertools.permutations(range(3)))
BLOCKS = [(pi, sg) for pi in S3 for sg in S3]


# ----------------------------------------------------------------------------- groups / codes
def twisted_group(l: int, m: int, alpha: int) -> FiniteGroup:
    """Z^2 / <(l,0), (alpha,m)>: x^l = 1, x^alpha y^m = 1.  Element (i,j), 0<=i<l, 0<=j<m -> index i*m+j."""
    def red(i, j):
        q, j2 = divmod(j, m)
        return ((i - q * alpha) % l) * m + j2
    N = l * m
    I, J = np.divmod(np.arange(N), m)
    mul = np.array([[red(I[a] + I[b], J[a] + J[b]) for b in range(N)] for a in range(N)], dtype=np.int64)
    labels = [f"x^{i}y^{j}" for i, j in zip(I, J)]
    g = FiniteGroup(name=f"T{l}x{m}a{alpha}", mul=mul, labels=labels)
    g._red = red
    return g


def twisted_code(l, m, alpha, A, B, name=""):
    G = twisted_group(l, m, alpha)
    a = tuple(G._red(i, j) for i, j in A)
    b = tuple(G._red(i, j) for i, j in B)
    c = GroupAlgebraCode(G, a, b, family="BB-twisted", name=name)
    c.coords = lambda g: divmod(g, m)
    return c


def _with_coords(c, m):
    c.coords = lambda g: divmod(g, m)
    return c


@lru_cache(maxsize=None)
def get_code(key: str):
    if key == "bb72":
        return _with_coords(bb_code(6, 6, "x^3+y+y^2", "y^3+x+x^2", name="[[72,12,6]]"), 6)
    if key == "bb108":
        return _with_coords(bb_code(9, 6, "x^3+y+y^2", "y^3+x+x^2", name="[[108,8,10]]"), 6)
    if key == "gross":
        return _with_coords(bb_code(12, 6, "x^3+y+y^2", "y^3+x+x^2", name="[[144,12,12]]"), 6)
    if key == "bb288":
        return _with_coords(bb_code(12, 12, "x^3+y^2+y^7", "y^3+x+x^2", name="[[288,12,18]]"), 12)
    if key == "bb90":
        return _with_coords(bb_code(15, 3, "x^9+y+y^2", "1+x^2+x^7", name="[[90,8,10]]"), 3)
    if key == "bb120p":   # project's bb120-dcirc (E-004 pilot), (l,m)=(20,3)
        return _with_coords(bb_code(20, 3, "1+x^3y^2+x^7y^2", "1+x^16y+x^9y", name="[[120,8,12]]p"), 3)
    if key == "cp126":
        return _with_coords(coprime_bb_code(7, 9, (0, 1, 58), (0, 13, 41), name="WMc[[126,12,10]]"), 9)
    if key == "wm180":
        return _with_coords(bb_code(6, 15, "x^3+y+y^2", "y^6+x^4+x^5", name="WM[[180,8,16]]"), 15)
    if key == "wmc108":   # 2408.10001 Table 2 (coprime), l=2 even
        return _with_coords(coprime_bb_code(2, 27, (0, 3, 42), (0, 6, 39), name="WMc[[108,12,6]]"), 27)
    if key == "bb124":    # E-004 pilot top20 #20 (MILP exact d=10), (31,2)
        return _with_coords(bb_code(31, 2, "1+x^27y+x^17", "1+x^30y+x^12y", name="[[124,10,10]]p"), 2)
    if key == "bb140":    # pilot top20 #9 (MILP exact d=14), (14,5); same (n,k,d) as 2511.13560 Tab.4
        return _with_coords(bb_code(14, 5, "1+x^3y+x^9y^3", "1+x^4y^3+x^6y^3", name="[[140,6,14]]p"), 5)
    if key.startswith("tt120"):  # 2601.09911: l,m=10,6, alpha=4, A=1+x+x^-2 y, B=1+y+x y^2 ; sign convention by key
        alpha = {"tt120a": 4, "tt120b": -4}[key]
        return twisted_code(10, 6, alpha, [(0, 0), (1, 0), (-2, 1)], [(0, 0), (0, 1), (1, 2)], name=f"[[120,8,12]]tt{alpha}")
    raise KeyError(key)


def css_of(code):
    return code.to_css()


def HL(code, kind):
    css = css_of(code)
    return (css.HZ, css.LZ) if kind == "X" else (css.HX, css.LX)


# ----------------------------------------------------------------------------- colourings
def homs_to_Zp(code, p):
    """All nonzero homomorphisms G -> Z_p (as arrays over group elements), up to scaling for p=3."""
    G = code.group
    N = G.order
    mul = G.mul
    # generators: elements (1,0) and (0,1) in coords
    m = None
    out, seen = [], set()
    coords = [code.coords(g) for g in range(N)]
    for u in range(p):
        for v in range(p):
            if (u, v) == (0, 0):
                continue
            h = np.array([(u * i + v * j) % p for i, j in coords])
            # homomorphism check
            if not all(h[mul[a, b]] == (h[a] + h[b]) % p for a in range(N) for b in range(N)):
                continue
            key = min(tuple(h), tuple((2 * h) % p)) if p == 3 else tuple(h)
            if key in seen:
                continue
            seen.add(key)
            out.append({"u": u, "v": v, "colour": tuple(int(c) for c in h)})
    return out


def colour_symmetry(code, colour):
    """Translations g with colour[g*h] == colour[h] for all h (they map the per-check orders to themselves)."""
    G = code.group
    return [g for g in range(G.order) if all(colour[G.mul[g, h]] == colour[h] for h in range(G.order))]


# ----------------------------------------------------------------------------- orders / ext
def check_orders(code, kind, colour, blocks_by_colour):
    """Per-check data-column orders (rows in H order of `kind` checks)."""
    out = []
    for i in range(code.n2):
        o = order_terms(kind, *blocks_by_colour[colour[i]])
        out.append([neighbours(code, kind, i, t) for t in o])
    return out


def proper(code, kind, colour, blocks_by_colour):
    used = set()
    for i in range(code.n2):
        o = order_terms(kind, *blocks_by_colour[colour[i]])
        for k, t in enumerate(o):
            key = (neighbours(code, kind, i, t), k)
            if key in used:
                return False
            used.add(key)
    return True


def ext_of_orders(code, kind, orders):
    H, L = HL(code, kind)
    sups = [s for o in orders for s in residual_supports(o)]
    return extended_matrices(H, L, sups)


def heur(He, Le, seeds, trials, target, lns_starts=None):
    """Shortest logical found by BP-OSD + LNS over several seeds (upper bound; witness verified)."""
    from search.noninterleaved.heur import heur_min
    best, wit = None, None
    for sd in seeds:
        w, x, _ = heur_min(He, Le, trials=trials, seed=sd,
                           lns_starts=lns_starts or (8 if trials <= 300 else 16), stop_at=target - 1)
        if w is not None and (best is None or w < best):
            best, wit = w, x
        if best is not None and best < target:
            break
    return best, wit


# ----------------------------------------------------------------------------- DFS instance
def dump_instance(code, kind, orders, sym, path):
    """Merged extended code + orbits of the translation group `sym` (list of group elements) on merged columns.
    File format for dfs128: 'R N NO' / per column 'lo hi lmask orbit' / reps."""
    H, L = HL(code, kind)
    H = np.asarray(H, dtype=np.uint8); L = np.asarray(L, dtype=np.uint8)
    n2, n = code.n2, code.n
    supports = [(j,) for j in range(n)] + [tuple(sorted(s)) for o in orders for s in residual_supports(o)]
    key_of, cols, sup_class = {}, [], []
    for S in supports:
        h = (H[:, list(S)].sum(1) % 2).astype(np.uint8)
        l = (L[:, list(S)].sum(1) % 2).astype(np.uint8)
        if not h.any() and not l.any():
            sup_class.append(-1); continue
        k = h.tobytes() + l.tobytes()
        if k not in key_of:
            key_of[k] = len(cols); cols.append((h, l))
        sup_class.append(key_of[k])
    supidx = {S: i for i, S in enumerate(supports)}
    mul = code.group.mul

    def tr(j, g):
        return int(mul[g, j]) if j < n2 else n2 + int(mul[g, j - n2])
    perms = []
    for g in sym:
        P = np.full(len(cols), -1)
        for i, S in enumerate(supports):
            T = tuple(sorted(tr(j, g) for j in S))
            assert T in supidx, "residual set not invariant under symmetry"
            ci, cj = sup_class[i], sup_class[supidx[T]]
            if ci < 0:
                assert cj < 0; continue
            assert P[ci] in (-1, cj), "action not well defined on merged columns"
            P[ci] = cj
        assert sorted(P) == list(range(len(cols)))
        perms.append(P)
    orb = np.full(len(cols), -1); reps = []
    for j in range(len(cols)):
        if orb[j] >= 0:
            continue
        o = sorted({int(P[j]) for P in perms})
        orb[o] = len(reps); reps.append(j)
    R = H.shape[0]
    assert R <= 128 and L.shape[0] <= 31
    with open(path, "w") as f:
        f.write(f"{R} {len(cols)} {len(reps)}\n")
        for j, (h, l) in enumerate(cols):
            hm = sum(1 << int(i) for i in np.nonzero(h)[0])
            lm = sum(1 << int(i) for i in np.nonzero(l)[0])
            f.write(f"{hm & ((1 << 64) - 1)} {hm >> 64} {lm} {orb[j]}\n")
        f.write(" ".join(map(str, reps)) + "\n")
    He = np.array([h for h, _ in cols]).T
    return {"rows": R, "cols": len(cols), "orbits": len(reps), "sym": len(sym),
            "orbit_sizes": np.bincount(orb).tolist(), "max_col_weight": int(He.sum(0).max())}


def jdump(path, obj):
    Path(path).write_text(json.dumps(obj, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)))


def now():
    return time.strftime("%H:%M:%S")
