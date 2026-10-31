"""E-041 fast exact bulk witness counter (numba) for pipelined single-ancilla schedules of Kunlun [[18,4,4]].

Same bulk model as search/experiments/e038/model.py (audited; Bulk.mechs): faults in rounds 0..W-1,
  D(q, f*, r): data error on q just before reader event f* of instance r;
  H(k, suffix of length 2..5, r): spreader ancilla error after its p-th CNOT, p = 1..4;
  M(c, r): reader measurement flip.
Detector (reader c, instance j) -> bit  ridx(c) * NJ + (j + 2), NJ = W + 4 (first-instance offsets are in r-1..r+2,
so j in -1..W+1).  Mechanisms are deduplicated on (detector mask, observable mask) and trivial ones dropped.

Schedule representation: tau[14, 6] absolute CNOT times (int64), NORMALISED: every check's earliest CNOT in 1..P
(rand.normalise), so all times lie in 1..P+6 and first-instance offsets are in r-1..r+2 (asserted: count returns
n1 = 10**6 if an offset leaves the detector window) for the check order of e036_audit.core.checks('bb18'),
term order of support(k); period P.

count(tau, P, W) -> (n1, n2, n3) per basis summed: number of undetectable logicals of weight 1, 2, 3 among the
deduplicated mechanisms (n3 counts triples i<j<k with zero mask and non-zero observable; triples containing a
weight-2 sub-witness are counted as well).

legal_viol(tau, P, span_max) -> number of violated legality constraints (0 = legal):
  span of each check <= span_max (W9: 6, Mg8: 6), distinct times within a check, data-qubit times distinct mod P,
  determinism parity for every X/Z pair with shared qubits and instance shift i in -4..4.
"""
from __future__ import annotations

import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
import numba as nb
import numpy as np

from search.experiments.e036_audit.core import checks, observables, support

KS = checks("bb18")
NK = len(KS)
SUP = np.array([support(k) for k in KS], np.int64)
TYP = np.array([0 if k[0] == "X" else 1 for k in KS], np.int64)   # 0 = X, 1 = Z


def _basis_tables(b):
    """readers of basis b ('Z' -> Z checks read, X errors), reader index, rev lists, observable per qubit."""
    rtype = 1 if b == "Z" else 0
    readers = [i for i in range(NK) if TYP[i] == rtype]
    spreaders = [i for i in range(NK) if TYP[i] != rtype]
    ridx = -np.ones(NK, np.int64)
    for n, i in enumerate(readers):
        ridx[i] = n
    rev = [[] for _ in range(18)]
    for i in readers:
        for a in range(6):
            rev[SUP[i, a]].append((i, a))
    deg = np.array([len(r) for r in rev], np.int64)
    revk = -np.ones((18, 8), np.int64)
    reva = -np.ones((18, 8), np.int64)
    for q in range(18):
        for n, (i, a) in enumerate(rev[q]):
            revk[q, n], reva[q, n] = i, a
    L = observables("bb18", b)
    obsq = np.array([sum(1 << i for i in range(len(L)) if L[i][q]) for q in range(18)], np.int64)
    return (np.array(readers, np.int64), np.array(spreaders, np.int64), ridx, deg, revk, reva, obsq)


TABLES = {b: _basis_tables(b) for b in ("Z", "X")}

# X/Z pairs with shared qubits: (ix, iz, ax[], az[]) padded
_pairs = []
for ix in range(NK):
    if TYP[ix] != 0:
        continue
    for iz in range(NK):
        if TYP[iz] != 1:
            continue
        sh = [q for q in SUP[ix] if q in SUP[iz]]
        if sh:
            _pairs.append((ix, iz, [list(SUP[ix]).index(q) for q in sh], [list(SUP[iz]).index(q) for q in sh]))
NPAIR = len(_pairs)
PAIR_K = np.array([[p[0], p[1]] for p in _pairs], np.int64)
PAIR_N = np.array([len(p[2]) for p in _pairs], np.int64)
PAIR_AX = -np.ones((NPAIR, 6), np.int64)
PAIR_AZ = -np.ones((NPAIR, 6), np.int64)
for n, p in enumerate(_pairs):
    PAIR_AX[n, :len(p[2])] = p[2]
    PAIR_AZ[n, :len(p[3])] = p[3]

# data qubit -> events (check, term) over all 14 checks
_onq = [[] for _ in range(18)]
for i in range(NK):
    for a in range(6):
        _onq[SUP[i, a]].append((i, a))
ONQ_N = np.array([len(x) for x in _onq], np.int64)
ONQ_K = -np.ones((18, 8), np.int64)
ONQ_A = -np.ones((18, 8), np.int64)
for q in range(18):
    for n, (i, a) in enumerate(_onq[q]):
        ONQ_K[q, n], ONQ_A[q, n] = i, a


@nb.njit(cache=True)
def _fdiv(a, b):
    return a // b   # numba int floor division == python semantics for negatives


@nb.njit(cache=True)
def _mechs(tau, P, W, readers, spreaders, ridx, deg, revk, reva, obsq, sup):
    NJ = W + 4
    nmax = W * (int(deg.sum()) + len(spreaders) * 4 + len(readers))
    D = np.zeros(nmax, np.uint64)
    O = np.zeros(nmax, np.int64)
    n = 0
    bad = False
    one = np.uint64(1)
    for r in range(W):
        for q in range(18):
            for x in range(deg[q]):
                ks, as_ = revk[q, x], reva[q, x]
                t2 = 2 * (tau[ks, as_] + r * P) - 1
                d = np.uint64(0)
                for y in range(deg[q]):
                    kf, af = revk[q, y], reva[q, y]
                    j0 = _fdiv(t2 - 2 * tau[kf, af], 2 * P) + 1
                    if j0 - r < -1 or j0 - r > 2:
                        bad = True
                    d ^= one << np.uint64(ridx[kf] * NJ + j0 + 2)
                D[n] = d
                O[n] = obsq[q]
                n += 1
        for si in range(len(spreaders)):
            k = spreaders[si]
            order = np.argsort(tau[k])
            for p in range(1, 5):
                d = np.uint64(0)
                o = 0
                for z in range(p, 6):
                    a = order[z]
                    u = sup[k, a]
                    tg = tau[k, a] + r * P
                    for y in range(deg[u]):
                        kf, af = revk[u, y], reva[u, y]
                        j0 = _fdiv(tg - tau[kf, af], P) + 1
                        if j0 - r < -1 or j0 - r > 2:
                            bad = True
                        d ^= one << np.uint64(ridx[kf] * NJ + j0 + 2)
                    o ^= obsq[u]
                D[n] = d
                O[n] = o
                n += 1
        for ci in range(len(readers)):
            c = readers[ci]
            D[n] = (one << np.uint64(ridx[c] * NJ + r + 2)) ^ (one << np.uint64(ridx[c] * NJ + r + 3))
            O[n] = 0
            n += 1
    if bad:
        D[0] = 0
        O[0] = 1 << 20   # forces n1 >= 1: flagged as invalid input
    return D[:n], O[:n]


@nb.njit(cache=True)
def _count(D, O):
    # dedupe on (D, O), drop trivial
    n = len(D)
    idx = np.argsort(D)
    Ds = D[idx]
    Os = O[idx]
    keepD = np.zeros(n, np.uint64)
    keepO = np.zeros(n, np.int64)
    m = 0
    n1 = 0
    for i in range(n):
        if Ds[i] == 0:
            if Os[i] != 0:
                n1 += 1
            continue
        dup = False
        j = m - 1
        while j >= 0 and keepD[j] == Ds[i]:
            if keepO[j] == Os[i]:
                dup = True
                break
            j -= 1
        if not dup:
            keepD[m] = Ds[i]
            keepO[m] = Os[i]
            m += 1
    Dk = keepD[:m]
    Ok = keepO[:m]
    n2 = 0
    i = 0
    while i < m:
        j = i
        while j < m and Dk[j] == Dk[i]:
            j += 1
        for a in range(i, j):
            for b in range(a + 1, j):
                if Ok[a] != Ok[b]:
                    n2 += 1
        i = j
    n3 = 0
    for a in range(m):
        for b in range(a + 1, m):
            x = Dk[a] ^ Dk[b]
            if x == 0:
                continue
            oo = Ok[a] ^ Ok[b]
            # binary search first position with Dk >= x
            lo, hi = 0, m
            while lo < hi:
                mid = (lo + hi) // 2
                if Dk[mid] < x:
                    lo = mid + 1
                else:
                    hi = mid
            c = lo
            while c < m and Dk[c] == x:
                if c > b and Ok[c] != oo:
                    n3 += 1
                c += 1
    return n1, n2, n3


def count(tau, P, W=4, bases=("Z", "X")):
    out = np.zeros(3, np.int64)
    for b in bases:
        t = TABLES[b]
        D, O = _mechs(tau, P, W, t[0], t[1], t[2], t[3], t[4], t[5], t[6], SUP)
        out += np.array(_count(D, O))
    return tuple(int(x) for x in out)


@nb.njit(cache=True)
def count_both(tau, P, W, tz, tx, sup):
    D, O = _mechs(tau, P, W, tz[0], tz[1], tz[2], tz[3], tz[4], tz[5], tz[6], sup)
    a1, a2, a3 = _count(D, O)
    D, O = _mechs(tau, P, W, tx[0], tx[1], tx[2], tx[3], tx[4], tx[5], tx[6], sup)
    b1, b2, b3 = _count(D, O)
    return a1 + b1, a2 + b2, a3 + b3


@nb.njit(cache=True)
def legal_viol(tau, P, span_max, onq_n, onq_k, onq_a, pk, pn, pax, paz):
    v = 0
    for k in range(tau.shape[0]):
        mn, mx = tau[k, 0], tau[k, 0]
        for a in range(6):
            mn = min(mn, tau[k, a])
            mx = max(mx, tau[k, a])
            for b in range(a + 1, 6):
                if tau[k, a] == tau[k, b]:
                    v += 1
        if mx - mn > span_max:
            v += 1
    for q in range(18):
        for x in range(onq_n[q]):
            for y in range(x + 1, onq_n[q]):
                if (tau[onq_k[q, x], onq_a[q, x]] - tau[onq_k[q, y], onq_a[q, y]]) % P == 0:
                    v += 1
    for p in range(len(pn)):
        kx, kz = pk[p, 0], pk[p, 1]
        for i in range(-4, 5):
            c = 0
            for s in range(pn[p]):
                if tau[kx, pax[p, s]] < tau[kz, paz[p, s]] + i * P:
                    c += 1
            if c % 2 == 1:
                v += 1
    return v


def viol(tau, P, span_max=6):
    return int(legal_viol(tau, P, span_max, ONQ_N, ONQ_K, ONQ_A, PAIR_K, PAIR_N, PAIR_AX, PAIR_AZ))


# ----------------------------------------------------------------------------- conversions
def tau_from_sched(s):
    return np.array([[s.tau[(k, a)] for a in range(6)] for k in KS], np.int64)


def sched_from_tau(tau, P, merged=False):
    """Sched with pi = min tau - 1 normalised to 0..P-1, mu = max tau + 1 (W) — for Mg the same pi/mu are legal."""
    from search.experiments.e038.model import Sched
    pi, mu, tt = {}, {}, {}
    for i, k in enumerate(KS):
        sh = ((int(tau[i].min()) - 1) // P) * P
        pi[k] = int(tau[i].min()) - 1 - sh
        mu[k] = int(tau[i].max()) + 1 - sh
        for a in range(6):
            tt[(k, a)] = int(tau[i, a]) - sh
    return Sched("bb18", P, pi, mu, tt)
