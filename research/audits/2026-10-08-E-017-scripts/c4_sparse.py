"""C4: rewrite the round-1 instance in the record-singleton basis (span(D_1 u D_2) = all Z records of
rounds 1, 2 in Z memory / X records in X memory, checked), verify it is the same column matroid
(an invertible row transform of the c3 instance, same column order), write the DFS instance."""
import pickle, sys, json
import numpy as np
from common import rank
hom, order, basis, T = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
OUT = "/Users/ephemeral/Desktop/qec-ai-search/results/E-017-audit"
tag = f"{hom}_{order}_{basis}_T{T}"
P = pickle.load(open(f"{OUT}/c2_{tag}.pkl", "rb"))
I = pickle.load(open(f"{OUT}/inst_{tag}_r1.pkl", "rb"))
blocks, grp, cols_all = P["blocks"], P["grp"], P["cols_all"]
colpos = {c: i for i, c in enumerate(cols_all)}
recs12 = [colpos[c] for c in grp[1] + grp[2]]
D12 = np.vstack([blocks[1], blocks[2]])
# span(D1 u D2) == singletons on rounds 1,2 ?
assert not np.any(np.delete(D12, recs12, axis=1)), "D1,D2 supported outside rounds 1,2"
assert rank(D12[:, recs12]) == len(recs12) == 144
# singleton signatures of each instance column: need the raw record flips of one fault per column.
# recompute record flips from the (H in D-basis): H_D = D12[:, recs12] @ flips  => flips = inv * H_D
Dsq = D12[:, recs12].astype(np.uint8)
# invert over GF(2)
n = 144
A = np.concatenate([Dsq, np.eye(n, dtype=np.uint8)], axis=1)
from common import rref
Rm, piv = rref(A)
assert piv[:n] == list(range(n))
Dinv = Rm[:, n:]
H = I["H"]  # rows = D1 rows then D2 rows
Hs = (Dinv.astype(np.int64) @ H.astype(np.int64)) % 2
Lm = I["L"]
assert rank(H) == rank(Hs) and rank(np.vstack([H, Lm])) == rank(np.vstack([Hs, Lm]))
w = Hs.sum(0)
info = dict(rows=int(Hs.shape[0]), nonzero_rows=int(Hs.any(1).sum()), cols=int(Hs.shape[1]),
            colweight_hist={int(k): int((w == k).sum()) for k in sorted(set(w))})
print(json.dumps(info))
orb = I["orb"]
nz = [i for i in range(Hs.shape[0]) if Hs[i].any()]
with open(f"{OUT}/sp_{tag}_r1.txt", "w") as fo:
    fo.write(f"{len(nz)} {Hs.shape[1]} {max(orb)+1}\n")
    for c in range(Hs.shape[1]):
        rows_c = [nz.index(i) for i in np.nonzero(Hs[:, c])[0]]
        lmask = int(sum(1 << b for b in np.nonzero(Lm[:, c])[0]))
        fo.write(f"{orb[c]} {lmask} {len(rows_c)} " + " ".join(map(str, rows_c)) + "\n")
json.dump(info, open(f"{OUT}/c4_{tag}.json", "w"))
