"""C9: every single-round instance of every T-round noisy-boundary memory circuit (T = 1..5) is equivalent
(same column matroid incl. logical labels, via the physical fault correspondence) to the round-1 instance
of T = 4. Also runs the fold checks of c3 for T = 2, 3 (c3 itself).
usage: c9_crossT.py <basis>
"""
import json, pickle, sys
import numpy as np
from common import N, HOMS, gid, l as LL, m as MM, rank, memory

OUT = "/Users/ephemeral/Desktop/qec-ai-search/results/E-017-audit"
basis = sys.argv[1]


def load(T):
    P = pickle.load(open(f"{OUT}/c2_x_repo_{basis}_T{T}.pkl", "rb"))
    C, _, _ = memory("x", "repo", T, basis)
    Ml = set(i for i, (ops, tg) in enumerate(C.layers) if tg[1] == "M")
    canon = lambda comp: tuple(sorted(((pt + 1) if (q < N and pt in Ml) else pt, q) for pt, q in comp))
    d = {}
    for ft, sg in zip(P["faults"], P["sigs"]):
        if ft[5]:
            d.setdefault(ft[0], {}).setdefault(canon(ft[5]), sg)
    return P, d


def tq(q, s):
    i, j = (q % N) // MM, (q % N) % MM
    return (N if q >= N else 0) + gid(i + s[0], j + s[1])


Pref, dref = load(4)
ref = dref[1]
res = {}
for T in (1, 2, 3, 4, 5):
    P, d = load(T)
    for r in range(1, T + 1):
        dr = r - 1
        s = (0, 0) if dr % 2 == 0 else (1, 0)
        A, B = [], []
        miss = 0
        img = set()
        for comp, sg in ref.items():
            im = tuple(sorted((pt + 8 * dr, tq(q, s)) for pt, q in comp))
            if im not in d[r]:
                miss += 1; continue
            img.add(im)
            A.append(np.concatenate([sg[0][1], sg[0][2], sg[1]]))
            t = d[r][im]
            B.append(np.concatenate([t[0][r], t[0][r + 1], t[1]]))
        if miss:
            res[f"T{T}r{r}"] = dict(missing=miss); continue
        A = np.array(A).T; B = np.array(B).T
        na = len(Pref["blocks"][1]) + len(Pref["blocks"][2]); nb = len(P["blocks"][r]) + len(P["blocks"][r + 1])
        ok = (rank(A[:na]) == rank(B[:nb]) == rank(np.vstack([A[:na], B[:nb]]))
              and rank(A) == rank(B) == rank(np.vstack([A, B])))
        res[f"T{T}r{r}"] = dict(equivalent=bool(ok), onto=img == set(d[r].keys()), rankH=int(rank(B[:nb])))
print(json.dumps(res))
json.dump(res, open(f"{OUT}/c9_{basis}.json", "w"), indent=1)
