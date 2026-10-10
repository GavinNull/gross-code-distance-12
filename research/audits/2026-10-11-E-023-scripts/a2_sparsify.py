"""Audit E-023 priority (a), test 1: same circuit, same DEM columns, sparsified detector basis H' = A H (A invertible,
found by greedy pairwise row XOR minimising nnz).  Re-decode the experimenter's 17 weight-2 failures (m54_repo X) and
the fixed-weight samples, with BP-OSD (IBM params) and Relay5 on H and on H'.
Outputs results/E-023-audit/a2_<prob>.json and a2_Hsparse_<prob>_<sec>.npz"""
import sys, json, time
import numpy as np, scipy.sparse as sp
sys.path.insert(0, '.')
from search.experiments.e023.common import sectors, Sec, make_decoder, OUT

def gf2rank(M):
    M = M.copy() % 2; r = 0
    for c in range(M.shape[1]):
        p = np.nonzero(M[r:, c])[0]
        if not len(p): continue
        p = p[0] + r; M[[r, p]] = M[[p, r]]
        nz = np.nonzero(M[:, c])[0]; nz = nz[nz != r]; M[nz] ^= M[r]; r += 1
        if r == M.shape[0]: break
    return r

def sparsify(Hd):
    H = Hd.copy().astype(np.uint8)
    w = H.sum(1).astype(int)
    improved = True; it = 0
    while improved:
        improved = False; it += 1
        for i in range(H.shape[0]):
            X = H ^ H[i][None, :]
            nw = X.sum(1); nw[i] = 10**9
            j = int(np.argmin(nw))
            # replacing row i by row_i ^ row_j has weight nw[j]
            if nw[j] < w[i]:
                H[i] ^= H[j]; w[i] = nw[j]; improved = True
    return H, it

if __name__ == "__main__":
    prob = sys.argv[1]
    res = {}
    for sec in sectors(prob, "sd6", 1e-3):
        Hd = sec.H.toarray().astype(np.uint8)
        t0 = time.time()
        Hs, it = sparsify(Hd)
        rks = (gf2rank(np.vstack([Hd, Hs])), gf2rank(Hd), gf2rank(Hs), Hd.shape[0]); print("ranks", rks, flush=True)
        assert rks[0] == rks[1] == rks[2]
        np.savez_compressed(f"results/E-023-audit/a2_Hsparse_{prob}_{sec.label}.npz", H=Hs)
        degH, degS = Hd.sum(0), Hs.sum(0)
        res[sec.label] = dict(nnz=int(Hd.sum()), nnz_sparse=int(Hs.sum()), coldeg_mean=float(degH.mean()),
                              coldeg_mean_sparse=float(degS.mean()), coldeg_max=int(degH.max()),
                              coldeg_max_sparse=int(degS.max()), rowwt_max=int(Hd.sum(1).max()),
                              rowwt_max_sparse=int(Hs.sum(1).max()), iters=it, secs=time.time() - t0)
        print(prob, sec.label, res[sec.label], flush=True)
    json.dump(res, open(f"results/E-023-audit/a2_{prob}_sparsity.json", "w"), indent=1)
