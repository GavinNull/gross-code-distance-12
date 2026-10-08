"""Independent check of mdfs (no search tree): meet-in-the-middle decides whether an undetected logical of
weight <= w exists, w <= 6, by matching syndromes of column subsets of size <= 3 (and <= 2).
usage: t4_mitm.py instance_file"""
import sys, json, itertools
import numpy as np

def load(path):
    with open(path) as fh:
        R, C, NO, NORB = map(int, fh.readline().split())
        S = np.zeros((C, (R + 63) // 64), dtype=np.uint64)
        L = np.zeros(C, dtype=np.uint64)
        for c in range(C):
            t = list(map(int, fh.readline().split()))
            k = t[1]; rows = t[2:2 + k]; j = t[2 + k]; obs = t[3 + k:3 + k + j]
            for r in rows:
                S[c, r // 64] ^= np.uint64(1) << np.uint64(r % 64)
            for o in obs:
                L[c] ^= np.uint64(1) << np.uint64(o)
    return S, L

def subsets(S, L, size):
    C = len(L)
    if size == 0:
        return np.zeros((1, S.shape[1]), dtype=np.uint64), np.zeros(1, dtype=np.uint64)
    idx = np.array(list(itertools.combinations(range(C), size)), dtype=np.int64)
    s = S[idx[:, 0]].copy(); l = L[idx[:, 0]].copy()
    for j in range(1, size):
        s ^= S[idx[:, j]]; l ^= L[idx[:, j]]
    return s, l

def exists(SA, LA, SB, LB):
    """exists a in A, b in B: s_a == s_b and l_a != l_b"""
    s = np.vstack([SA, SB]); l = np.concatenate([LA, LB])
    keys = np.ascontiguousarray(np.column_stack([s, l])).view([('', s.dtype)] * (s.shape[1] + 1)).ravel()
    order = np.lexsort(tuple(s[:, k] for k in range(s.shape[1] - 1, -1, -1)))
    ss = s[order]; ll = l[order]
    same = np.all(ss[1:] == ss[:-1], axis=1)
    # within each syndrome group, check if logical values differ
    grp = np.concatenate([[0], np.cumsum(~same)])
    lmin = np.full(grp[-1] + 1, np.iinfo(np.uint64).max, dtype=np.uint64); lmax = np.zeros(grp[-1] + 1, dtype=np.uint64)
    np.minimum.at(lmin, grp, ll); np.maximum.at(lmax, grp, ll)
    return bool((lmin != lmax).any())

def exists_ab(S_all, L_all, small_mask):
    """sets = all subsets of size <= a (rows of S_all); small_mask marks those of size <= b.
    exists x (size<=a), y (size<=b) with equal syndrome and different logical  <=>  some syndrome group
    contains a small element and >= 2 distinct logical values (small sets are also in the big family)."""
    s = S_all
    order = np.lexsort(tuple(s[:, k] for k in range(s.shape[1] - 1, -1, -1)))
    ss = s[order]; ll = L_all[order]; sm = small_mask[order]
    same = np.all(ss[1:] == ss[:-1], axis=1)
    grp = np.concatenate([[0], np.cumsum(~same)])
    G = grp[-1] + 1
    lmin = np.full(G, np.iinfo(np.uint64).max, dtype=np.uint64); lmax = np.zeros(G, dtype=np.uint64)
    np.minimum.at(lmin, grp, ll); np.maximum.at(lmax, grp, ll)
    hs = np.zeros(G, dtype=bool); np.logical_or.at(hs, grp, sm)
    return bool(((lmin != lmax) & hs).any())

if __name__ == '__main__':
    S, L = load(sys.argv[1])
    tab = {k: subsets(S, L, k) for k in range(0, 4)}
    res = {}
    for w in range(1, 7):
        a, b = (w + 1) // 2, w // 2
        Sa = np.vstack([tab[j][0] for j in range(a + 1)]); La = np.concatenate([tab[j][1] for j in range(a + 1)])
        small = np.concatenate([np.full(len(tab[j][1]), j <= b) for j in range(a + 1)])
        e = exists_ab(Sa, La, small)
        res[w] = e
        if e:
            break
    print(json.dumps(dict(file=sys.argv[1].split('/')[-1], cols=len(L), exists_upto=res)))
