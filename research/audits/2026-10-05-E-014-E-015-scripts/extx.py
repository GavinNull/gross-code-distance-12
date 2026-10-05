"""Auditor's own extended-code builder (Strikis et al. 2603.05481 v2, Def. 2), orbit computation and dfs128 dump.

Columns: every data qubit (single support) + every proper suffix {i_l..i_w}, l = 2..w, of each check's CNOT order.
Column vector = (H 1_S, L 1_S) mod 2; zero columns dropped, identical columns merged.
"""
import numpy as np
from gf2 import solve_left, rank


def build(H, L, orders, n):
    H = np.asarray(H, np.uint8) % 2
    L = np.asarray(L, np.uint8) % 2
    sups = [(j,) for j in range(n)]
    for o in orders:
        w = len(o)
        for l in range(1, w):
            sups.append(tuple(sorted(o[l:])))
    key_of, cols, members, sup_class = {}, [], [], []
    for S in sups:
        h = H[:, list(S)].sum(1) % 2
        lv = L[:, list(S)].sum(1) % 2
        if not h.any() and not lv.any():
            sup_class.append(-1)
            continue
        k = h.astype(np.uint8).tobytes() + b"|" + lv.astype(np.uint8).tobytes()
        if k not in key_of:
            key_of[k] = len(cols)
            cols.append((h.astype(np.uint8), lv.astype(np.uint8)))
            members.append([])
        sup_class.append(key_of[k])
        members[key_of[k]].append(S)
    He = np.array([c[0] for c in cols], np.uint8).T
    Le = np.array([c[1] for c in cols], np.uint8).T
    return dict(He=He, Le=Le, sups=sups, sup_class=sup_class, members=members, H=H, L=L)


def logical_transform_ok(H, L, perm):
    """For a data permutation perm (new index of qubit j = perm[j]), check that x -> logical-ness is preserved:
    rows of L o P lie in span(L) + span(H) with an invertible L-part, where (L o P)[:, j] = L[:, perm[j]]."""
    LP = L[:, perm]
    X = solve_left(np.vstack([L, H]), LP)
    if X is None:
        return False
    M = X[:, :L.shape[0]]
    return rank(M) == L.shape[0]


def orbits(ext, data_perms):
    """data_perms: list of arrays p with p[j] = image of data qubit j.  Returns orbit labels, reps, and checks
    that the action on supports maps the support set to itself and descends to merged columns."""
    sups, sc = ext["sups"], ext["sup_class"]
    idx = {S: i for i, S in enumerate(sups)}
    N = ext["He"].shape[1]
    perms = []
    for p in data_perms:
        P = np.full(N, -1)
        for i, S in enumerate(sups):
            T = tuple(sorted(int(p[j]) for j in S))
            assert T in idx, "support set not invariant"
            a, b = sc[i], sc[idx[T]]
            if a < 0:
                assert b < 0
                continue
            assert P[a] in (-1, b), "not well defined on merged columns"
            P[a] = b
        assert sorted(P.tolist()) == list(range(N))
        perms.append(P)
    orb = np.full(N, -1)
    reps = []
    for j in range(N):
        if orb[j] >= 0:
            continue
        o = sorted({int(P[j]) for P in perms})
        orb[o] = len(reps)
        reps.append(j)
    return orb, reps, perms


def dump128(He, Le, orb, reps, path):
    r, N = He.shape
    assert r <= 128 and Le.shape[0] <= 30
    with open(path, "w") as f:
        f.write(f"{r} {N} {len(reps)}\n")
        for j in range(N):
            hm = sum(1 << int(i) for i in np.nonzero(He[:, j])[0])
            lm = sum(1 << int(i) for i in np.nonzero(Le[:, j])[0])
            f.write(f"{hm & ((1 << 64) - 1)} {hm >> 64} {lm} {int(orb[j])}\n")
        f.write(" ".join(map(str, reps)) + "\n")


def read128(path):
    lines = open(path).read().split("\n")
    r, N, NO = map(int, lines[0].split())
    He = np.zeros((r, N), np.uint8)
    lms, orb = [], []
    for j in range(N):
        lo, hi, lm, o = map(int, lines[1 + j].split())
        h = lo | (hi << 64)
        for i in range(r):
            He[i, j] = (h >> i) & 1
        lms.append(lm)
        orb.append(o)
    nl = max(lms).bit_length()
    Le = np.array([[(lm >> i) & 1 for lm in lms] for i in range(max(nl, 1))], np.uint8)
    reps = list(map(int, lines[1 + N].split()))
    return He, Le, np.array(orb), reps


def compare_columns(He1, Le1, H1rows_equal, He2, Le2):
    """Compare two merged extended codes on the same H (same row order) but possibly different logical bases.
    Finds M, N with Le2 = M Le1 + N He1 (columnwise) from uniquely-He columns, then checks set equality.
    Returns (equal, info)."""
    from gf2 import solve_left as sl
    k1 = {}
    for j in range(He1.shape[1]):
        k1.setdefault(He1[:, j].tobytes(), []).append(j)
    k2 = {}
    for j in range(He2.shape[1]):
        k2.setdefault(He2[:, j].tobytes(), []).append(j)
    info = {"N1": He1.shape[1], "N2": He2.shape[1],
            "He_multiset_equal": sorted((k, len(v)) for k, v in k1.items()) == sorted((k, len(v)) for k, v in k2.items())}
    uniq = [(k1[k][0], k2[k][0]) for k in k1 if len(k1[k]) == 1 and len(k2.get(k, [])) == 1]
    A = np.vstack([Le1[:, [a for a, _ in uniq]], He1[:, [a for a, _ in uniq]]])   # (l1+r) x u
    B = Le2[:, [b for _, b in uniq]]                                                 # l2 x u
    X = sl(A.T.T, B) if False else None
    # solve X A = B  (X: l2 x (l1+r))
    X = sl(A, B)
    if X is None:
        info["solvable"] = False
        return False, info
    info["solvable"] = True
    M = X[:, :Le1.shape[0]]
    info["M_rank"] = rank(M)
    T1 = (X.astype(int) @ np.vstack([Le1, He1]).astype(int)) % 2
    s1 = {He1[:, j].tobytes() + T1[:, j].astype(np.uint8).tobytes() for j in range(He1.shape[1])}
    s2 = {He2[:, j].tobytes() + Le2[:, j].astype(np.uint8).tobytes() for j in range(He2.shape[1])}
    info["set_equal_after_basis_change"] = s1 == s2
    # map columns 1 -> 2
    idx2 = {He2[:, j].tobytes() + Le2[:, j].astype(np.uint8).tobytes(): j for j in range(He2.shape[1])}
    mp = [idx2.get(He1[:, j].tobytes() + T1[:, j].astype(np.uint8).tobytes(), -1) for j in range(He1.shape[1])]
    info["map"] = mp
    return s1 == s2 and info["M_rank"] == Le1.shape[0] == Le2.shape[0], info
