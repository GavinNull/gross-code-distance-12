"""E-017: DFS instance (projected single-round DEM) with translation symmetry.

Rows = memory-type detectors with nonzero degree; columns = merged projected DEM columns; Le = observable mask.
Symmetry: translations t in K = ker f act on stabiliser labels; a translation is used only if it maps every
column to a column (He part permuted, Le part transformed by Le' = M Le + Nmat He with M invertible, solved and
checked over GF(2)) -- so undetected logicals map to undetected logicals.
Usage: uv run python -m search.experiments.e017.dfs_inst --basis Z --out results/.../inst_Z.txt
"""
from __future__ import annotations

import argparse
import json

import numpy as np

from search.experiments.e017.morph import TWO_GROSS, rank, rref
from search.experiments.e017.oneround import one_round_circuit
from search.experiments.e017.project import projected_columns

NW = 5


def solve_affine(Xs, ys):
    """Find a with a . x = y for all (x, y) over GF(2); X rows = x. Returns a or None."""
    X = np.array(Xs, dtype=np.uint8)
    y = np.array(ys, dtype=np.uint8)[:, None]
    A = np.hstack([X, y])
    Rr, piv = rref(A)
    if X.shape[1] in piv:
        return None
    a = np.zeros(X.shape[1], dtype=np.uint8)
    for i, pc in enumerate(piv):
        a[pc] = Rr[i, -1]
    return a


def build(hom="x", swap23=False, basis="Z", first_j=1, full_rounds=0):
    if full_rounds:
        from search.experiments.e017.ub import build as build_full
        from search.experiments.e017.morph import Morph
        c = build_full(hom, swap23, basis, full_rounds, first_j)
        M = Morph(TWO_GROSS, hom, swap23=swap23)
    else:
        c, M = one_round_circuit(hom=hom, swap23=swap23, basis=basis, first_j=first_j)
    keep, cols = projected_columns(c, basis)
    deg = np.zeros(len(keep), int)
    for ds, ob in cols:
        for d in ds:
            deg[d] += 1
    rows = [i for i in range(len(keep)) if deg[i] > 0]
    rpos = {r: i for i, r in enumerate(rows)}
    R = len(rows)
    nobs = c.num_observables
    He = np.zeros((R, len(cols)), dtype=np.uint8)
    Le = np.zeros((nobs, len(cols)), dtype=np.uint8)
    for j, (ds, ob) in enumerate(cols):
        for d in ds:
            He[rpos[d], j] = 1
        for o in ob:
            Le[o, j] = 1
    coords = c.get_detector_coordinates()
    # detector key -> row
    key2row = {}
    for i, r in enumerate(rows):
        co = coords[keep[r]]
        key2row[(int(co[0]), int(co[1]), int(co[2]))] = i
    code = TWO_GROSS
    elems = code.elems()
    f = M.f
    gens = []
    hekey = {}
    for j in range(len(cols)):
        hekey.setdefault(He[:, j].tobytes(), []).append(j)
    for t in [g for g in elems if f(g) == 0]:
        rmap = np.full(R, -1)
        ok = True
        for (r, rd, ty), i in key2row.items():
            g = elems[r]
            g2 = code.mul(g, t)
            k2 = (code.idx(g2), rd, ty)
            if k2 not in key2row:
                ok = False
                break
            rmap[i] = key2row[k2]
        if not ok:
            continue
        He2 = np.zeros_like(He)
        He2[rmap, :] = He
        # unique-He matches give equations for the Le transformation
        cand = [hekey.get(He2[:, j].tobytes(), []) for j in range(len(cols))]
        if any(len(cd) == 0 for cd in cand):
            continue
        X = np.vstack([Le, He]).T          # rows: [Le_c ; He_c]
        A = []
        for o in range(nobs):
            eqs = [(X[j], Le[o, cand[j][0]]) for j in range(len(cols)) if len(cand[j]) == 1]
            a = solve_affine([e[0] for e in eqs], [e[1] for e in eqs])
            if a is None:
                A = None
                break
            A.append(a)
        if A is None:
            continue
        A = np.array(A)
        Mm = A[:, :nobs]
        if rank(Mm) != nobs:
            continue
        perm = np.full(len(cols), -1)
        for j in range(len(cols)):
            want = (A @ X[j]) % 2
            m = [k for k in cand[j] if (Le[:, k] == want).all()]
            if len(m) != 1:
                perm = None
                break
            perm[j] = m[0]
        if perm is None or len(set(perm.tolist())) != len(cols):
            continue
        gens.append((t, perm))
    # orbits
    parent = list(range(len(cols)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for t, perm in gens:
        for j in range(len(cols)):
            a, b = find(j), find(int(perm[j]))
            if a != b:
                parent[max(a, b)] = min(a, b)
    roots = sorted(set(find(j) for j in range(len(cols))), key=lambda r: -sum(1 for j in range(len(cols)) if find(j) == r))
    # order orbits: largest orbit first? (any order is valid); use order of smallest column weight first
    orb_of = {r: i for i, r in enumerate(roots)}
    corb = [orb_of[find(j)] for j in range(len(cols))]
    reps = [r for r in roots]
    return dict(R=R, He=He, Le=Le, corb=corb, reps=reps, ngroup=len(gens), cols=cols, rows=rows, keep=keep,
                circuit=c)


def write(inst, path):
    R, He, Le = inst["R"], inst["He"], inst["Le"]
    assert R <= 64 * NW
    with open(path, "w") as fh:
        fh.write(f"{R} {He.shape[1]} {len(inst['reps'])}\n")
        for j in range(He.shape[1]):
            words = []
            for k in range(NW):
                v = 0
                for b in range(64):
                    i = 64 * k + b
                    if i < R and He[i, j]:
                        v |= 1 << b
                words.append(f"{v:x}")
            lm = int(sum(int(Le[o, j]) << o for o in range(Le.shape[0])))
            fh.write(" ".join(words) + f" {lm} {inst['corb'][j]}\n")
        fh.write(" ".join(str(r) for r in inst["reps"]) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--basis", default="Z")
    ap.add_argument("--hom", default="x")
    ap.add_argument("--swap23", action="store_true")
    ap.add_argument("--first_j", type=int, default=1)
    ap.add_argument("--full_rounds", type=int, default=0, help="all-noisy memory circuit with this many rounds")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    inst = build(a.hom, a.swap23, a.basis, a.first_j, a.full_rounds)
    write(inst, a.out)
    sizes = np.bincount(inst["corb"]).tolist()
    meta = {"rows": inst["R"], "cols": int(inst["He"].shape[1]), "group_order": inst["ngroup"],
            "orbits": len(inst["reps"]), "orbit_sizes": sizes, "config": vars(a)}
    json.dump(meta, open(a.out + ".json", "w"), indent=1)
    print(meta)
