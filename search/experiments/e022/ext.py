"""E-022: the 'morphing extended code' of a two-round morphing circuit (one half-cycle), plus fault classification.

Half-cycle (interior round) with previous contraction p and current contraction c:
    layer 0: reset right qubits (bases of meas[p]);  layers 1..3: F_p^dag (gates[p] reversed);
    layers 4..6: F_c (gates[c]);  then measure right qubits (bases of meas[c]).
Memory basis Z -> X-type errors (propagate control -> target), 'flag' basis Z; basis X -> Z errors, mirror.

Every single fault f of the half-cycle (CNOT component after layer k, reset flip of a flag-basis reset right qubit,
flag-basis measurement flip, left-qubit data error at the start / end) is propagated
  forward  to the end of the half-cycle: (b_f on the N left qubits = data error on C~_c, rho_f = flips of the N/2
           flag-basis measurements of this round);
  backward to the start of the half-cycle: (a_f on C~_p, r_f = support on the N/2 flag-basis reset qubits;
           support on the other reset qubits is a stabiliser of the fresh state and dropped).
Claim (proved in the journal): a set S of faults of one half-cycle is undetectable iff sum rho = 0 and
sum b in ker H~_c (equivalently sum r = 0 and sum a in ker H~_p), and it is a logical failure iff sum b is a
nontrivial C~_c logical. So the single-round circuit distance = distance of the code with columns
(H~_c b_f ; rho_f | L~_c b_f) -- the 'morphing extended code' Ext(c).
"""
from __future__ import annotations

import numpy as np

from search.experiments.e019.common import HOMS, analyse, get_code, logicals, spec

LABELS = ["R", "Fd0", "Fd1", "Fd2", "F0", "F1", "F2"]


def halfcycle(code, gates, meas, p, c):
    layers = [None] + [gates[p][2], gates[p][1], gates[p][0]] + [gates[c][0], gates[c][1], gates[c][2]]
    return layers


def prop(e, layers, ks, basis):
    """apply CNOT layers with indices in ks (in the given order) to error vector e (copy)."""
    e = e.copy()
    for k in ks:
        L = layers[k]
        if L is None:
            continue
        cs = np.fromiter((a for a, b in L), int)
        ts = np.fromiter((b for a, b in L), int)
        if basis == "Z":     # X errors: X_c -> X_c X_t
            e[ts] ^= e[cs]
        else:                # Z errors: Z_t -> Z_c Z_t
            e[cs] ^= e[ts]
    return e


def faults_of(code, layers, meas, p, c, basis, cnot_only=False):
    """list of (kind, layer, qubits) with the error vector placed right after 'layer'."""
    N = code.N
    flag = "Z" if basis == "Z" else "X"
    out = []
    if not cnot_only:
        for q in range(N):
            out.append(("data_start", 0, (q,)))
        for q in sorted(meas[p][flag]):
            out.append(("reset", 0, (q,)))
    for k in range(1, 7):
        for (a, b) in layers[k]:
            out.append(("cx", k, (a,)))
            out.append(("cx", k, (b,)))
            out.append(("cx", k, (a, b)))
    if not cnot_only:
        for q in range(N):
            out.append(("data_end", 6, (q,)))
        for q in sorted(meas[c][flag]):
            out.append(("meas", 6, (q,)))
    return out


class Ext:
    def __init__(self, key, basis, p=0, c=1, cnot_only=False):
        name, hom, variant = key.split("_")
        self.key, self.basis, self.p, self.c = key, basis, p, c
        self.code = code = get_code(name)
        N = self.N = code.N
        gates, meas, _, _ = spec(code, hom, variant)
        self.gates, self.meas = gates, meas
        info, ec = analyse(code, gates, meas)
        self.info, self.ec = info, ec
        flag = "Z" if basis == "Z" else "X"
        other = "X" if flag == "Z" else "Z"
        self.Hc, self.Hp = ec[c][flag], ec[p][flag]          # checks detecting our error type
        self.Lc = logicals(ec[c][flag], ec[c][other])          # functionals: class of x in ker Hc
        self.Lp = logicals(ec[p][flag], ec[p][other])
        self.Xc = logicals(ec[c][other], ec[c][flag])          # logical operators of our error type
        self.Xp = logicals(ec[p][other], ec[p][flag])
        self.layers = layers = halfcycle(code, gates, meas, p, c)
        self.mset = sorted(q - N for q in meas[c][flag])     # flag-basis measured right qubits (index - N)
        self.rset = sorted(q - N for q in meas[p][flag])     # flag-basis reset right qubits
        self.faults = faults_of(code, layers, meas, p, c, basis, cnot_only)
        nf = len(self.faults)
        self.a = np.zeros((nf, N), np.uint8)
        self.r = np.zeros((nf, len(self.rset)), np.uint8)
        self.b = np.zeros((nf, N), np.uint8)
        self.rho = np.zeros((nf, len(self.mset)), np.uint8)
        for i, (kind, k, qs) in enumerate(self.faults):
            e = np.zeros(2 * N, np.uint8)
            e[list(qs)] = 1
            fw = prop(e, layers, range(k + 1, 7), basis)
            bw = prop(e, layers, range(k, 0, -1), basis)
            self.b[i], self.rho[i] = fw[:N], fw[N:][self.mset]
            self.a[i], self.r[i] = bw[:N], bw[N:][self.rset]
        self.sb = (self.b.astype(np.int64) @ self.Hc.T.astype(np.int64)) % 2
        self.sa = (self.a.astype(np.int64) @ self.Hp.T.astype(np.int64)) % 2
        self.lb = (self.b.astype(np.int64) @ self.Lc.T.astype(np.int64)) % 2
        self.la = (self.a.astype(np.int64) @ self.Lp.T.astype(np.int64)) % 2

    def end_matrix(self):
        """rows: [H~_c b ; rho], logical rows L~_c b (fault order)."""
        return np.concatenate([self.sb, self.rho], 1).T.astype(np.uint8), self.lb.T.astype(np.uint8)

    def start_matrix(self):
        return np.concatenate([self.sa, self.r], 1).T.astype(np.uint8), self.la.T.astype(np.uint8)

    def translations(self):
        f = HOMS[self.key.split("_")[1]]
        code = self.code
        G = [(i, j) for i in range(code.l) for j in range(code.m)]
        return [s for s in G if f(s) == 0]

    def fault_perm(self, s):
        idx = {(kind, k, tuple(sorted(qs))): i for i, (kind, k, qs) in enumerate(self.faults)}
        out = []
        for (kind, k, qs) in self.faults:
            im = tuple(sorted(self.code.translate_q(q, s) for q in qs))
            j = idx.get((kind, k, im))
            if j is None:
                return None
            out.append(j)
        return out


def dedup(H, L, keep=None):
    """unique nonzero columns of [H;L]; returns (H', L', groups: col -> list of fault indices)."""
    M = np.vstack([H, L])
    cols = {}
    for i in range(M.shape[1]):
        if keep is not None and not keep[i]:
            continue
        v = M[:, i]
        if not v.any():
            continue
        cols.setdefault(v.tobytes(), []).append(i)
    keys = list(cols)
    A = np.array([np.frombuffer(k, np.uint8) for k in keys]).T
    return A[:H.shape[0]], A[H.shape[0]:], [cols[k] for k in keys]
