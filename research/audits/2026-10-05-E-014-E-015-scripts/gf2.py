"""Auditor's own GF(2) helpers (no project imports)."""
import numpy as np


def rref(M):
    M = (np.array(M, dtype=np.uint8) % 2).copy()
    r, c = M.shape
    piv = []
    i = 0
    for j in range(c):
        if i >= r:
            break
        p = np.nonzero(M[i:, j])[0]
        if len(p) == 0:
            continue
        p = p[0] + i
        if p != i:
            M[[i, p]] = M[[p, i]]
        nz = np.nonzero(M[:, j])[0]
        for k in nz:
            if k != i:
                M[k] ^= M[i]
        piv.append(j)
        i += 1
    return M[:i], piv


def rank(M):
    return len(rref(M)[1])


def nullspace(M):
    """Basis (rows) of {x : M x = 0}."""
    M = np.array(M, dtype=np.uint8) % 2
    R, piv = rref(M)
    n = M.shape[1]
    free = [j for j in range(n) if j not in set(piv)]
    out = []
    for f in free:
        x = np.zeros(n, np.uint8)
        x[f] = 1
        for i, p in enumerate(piv):
            x[p] = R[i, f]
        out.append(x)
    return np.array(out, dtype=np.uint8).reshape(-1, n)


def logical_basis(H_commute, H_stab):
    """Rows: operators of one Pauli type that commute with the other type's checks (kernel of H_commute) and are
    independent modulo rowspace(H_stab).  Returns k x n."""
    K = nullspace(H_commute)
    base = rref(H_stab)[0]
    r0 = rank(base)
    out = []
    cur = base.copy()
    for v in K:
        t = np.vstack([cur, v[None]])
        if rank(t) > rank(cur):
            out.append(v)
            cur = t
    L = np.array(out, dtype=np.uint8)
    assert rank(np.vstack([base, L])) == r0 + len(L)
    return L


def solve_left(A, B):
    """Find X with X A = B (rows), A: a x n, B: b x n.  Returns X or None."""
    A = np.array(A, np.uint8) % 2
    B = np.array(B, np.uint8) % 2
    # X A = B  <=>  A^T X^T = B^T
    At = A.T
    a = A.shape[0]
    aug = np.hstack([At, B.T])
    R, piv = rref(aug)
    if any(p >= a for p in piv):
        return None
    X = np.zeros((B.shape[0], a), np.uint8)
    for i, p in enumerate(piv):
        X[:, p] = R[i, a:]
    assert ((X.astype(int) @ A) % 2 == B).all()
    return X
