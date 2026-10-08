"""Auditor's independent construction of the Shaw-Terhal morphing circuit (arXiv:2407.16336, Table 2/4)
for the [[288,12,18]] BB code (l=m=12, A=x^3+y^7+y^2, B=y^3+x+x^2), following the *public repo's*
`get_standard_morphing_specification` as read (not executed), plus GF(2) helpers.

Written without reading search/experiments/e017/*.py.

Qubit labels: L(g) = 12 i + j, R(g) = 144 + 12 i + j, g = x^i y^j.
"""
from __future__ import annotations

import numpy as np
import stim

l = m = 12
N = l * m
A_POLY = [(3, 0), (0, 7), (0, 2)]
B_POLY = [(0, 3), (1, 0), (2, 0)]
HOMS = {"x": lambda g: g[0] % 2, "y": lambda g: g[1] % 2, "xy": lambda g: (g[0] + g[1]) % 2}


def gid(i, j):
    return (i % l) * m + (j % m)


def L(i, j):
    return gid(i, j)


def R(i, j):
    return N + gid(i, j)


# ---------------------------------------------------------------- GF(2)
def rref(M):
    """Row-reduce a uint8 matrix over GF(2). Returns (R, pivots)."""
    M = (np.array(M, dtype=np.uint8) & 1).copy()
    rows, cols = M.shape
    piv = []
    r = 0
    for c in range(cols):
        if r >= rows:
            break
        nz = np.nonzero(M[r:, c])[0]
        if len(nz) == 0:
            continue
        p = r + nz[0]
        if p != r:
            M[[r, p]] = M[[p, r]]
        others = np.nonzero(M[:, c])[0]
        others = others[others != r]
        if len(others):
            M[others] ^= M[r]
        piv.append(c)
        r += 1
    return M[:r], piv


def rank(M):
    return len(rref(M)[1])


def nullspace(M):
    """Basis (rows) of {v : M v = 0}."""
    M = np.array(M, dtype=np.uint8) & 1
    cols = M.shape[1]
    Rm, piv = rref(M)
    free = [c for c in range(cols) if c not in set(piv)]
    out = np.zeros((len(free), cols), dtype=np.uint8)
    for k, f in enumerate(free):
        out[k, f] = 1
        for i, p in enumerate(piv):
            if Rm[i, f]:
                out[k, p] = 1
    return out


def in_rowspace(basis, v):
    if len(basis) == 0:
        return not np.any(v)
    return rank(np.vstack([basis, v])) == rank(basis)


# ---------------------------------------------------------------- code
def poly_matrix(poly):
    M = np.zeros((N, N), dtype=np.uint8)
    for i in range(l):
        for j in range(m):
            for (a, b) in poly:
                M[gid(i, j), gid(i + a, j + b)] ^= 1  # row g has a 1 at column g + a (repo convention)
    return M


def bb_checks():
    Am, Bm = poly_matrix(A_POLY), poly_matrix(B_POLY)
    HX = np.concatenate([Am, Bm], axis=1)
    HZ = np.concatenate([Bm.T, Am.T], axis=1)
    return HX, HZ


def spec(hom="x", order="repo"):
    """Gate layers and measurement lists of the two contraction rounds (repo convention).
    Returns gates[r][layer] = list of (control, target); meas[r] = {"X": [...], "Z": [...]}."""
    f = HOMS[hom]
    lists = []
    for poly in (A_POLY, B_POLY):
        c = list(poly)
        vals = [f(e) for e in c]
        if vals.count(0) == 1:
            sv = 0
        elif vals.count(1) == 1:
            sv = 1
        else:
            raise ValueError("criterion 1 fails")
        k = vals.index(sv)
        c[0], c[k] = c[k], c[0]
        lists.append(c)
    a, b = lists
    nl = 3
    gates = [[[] for _ in range(nl)] for _ in range(2)]
    meas = [{"X": [], "Z": []} for _ in range(2)]
    for i in range(l):
        for j in range(m):
            rg = f((i, j))
            rh = (rg + 1) % 2
            Lq = L(i, j)
            rgq = [R(i - a[0][0] + e[0], j - a[0][1] + e[1]) for e in b]
            rhq = [R(i - e[0] + b[0][0], j - e[1] + b[0][1]) for e in a]
            for k in range(1, 3):
                layer = (k - 1) if order == "repo" else (2 - k)  # paper Table 2: round 1 uses index 3
                gates[rg][layer].append((Lq, rgq[k]))
                gates[rh][layer].append((rhq[k], Lq))
            gates[rg][2].append((rgq[0], Lq))
            gates[rh][2].append((Lq, rhq[0]))
            meas[rg]["X"].append(rgq[0])
            meas[rh]["Z"].append(rhq[0])
    return gates, meas, a, b


def propagate_pauli(x, z, layers):
    """Heisenberg forward through CNOT layers: P -> U P U^dag. x,z: bool arrays (copied)."""
    x = x.copy(); z = z.copy()
    for layer in layers:
        for (c, t) in layer:
            x[t] ^= x[c]
            z[c] ^= z[t]
    return x, z


# ---------------------------------------------------------------- circuits
class Circ:
    """Noiseless circuit as list of layers; each layer: list of (op, targets). Records tracked."""

    def __init__(self):
        self.layers = []
        self.nrec = 0
        self.recs = []  # (round, kind, basis, qubit)

    def add(self, ops, tag=None):
        self.layers.append((ops, tag))
        for (op, ts) in ops:
            if op in ("M", "MX"):
                for q in ts:
                    self.recs.append((tag, op, q))
                    self.nrec += 1

    def stim(self, extra_after_layer=None):
        c = stim.Circuit()
        for li, (ops, tag) in enumerate(self.layers):
            if li:
                c.append("TICK")
            for (op, ts) in ops:
                if op == "CX":
                    flat = [q for pr in ts for q in pr]
                    c.append("CX", flat)
                else:
                    c.append(op, ts)
            if extra_after_layer and li in extra_after_layer:
                c += extra_after_layer[li]
        return c


def memory(hom="x", order="repo", T=3, basis="Z", final=True, first_c=0):
    """Z/X-basis memory: round-1 reset layer resets right qubits (R_p bases) and left qubits (memory basis);
    T morphing rounds; final transversal readout of left qubits in the last M layer.
    Round r (1-based): contraction c = (r-1) % 2, previous p = 1 - c (repo `morphing_QEC_round`).
    Layer tags: (r, 'R'|'Fd0'..'Fd2'|'F0'..'F2'|'M')."""
    gates, meas, _, _ = spec(hom, order)
    C = Circ()
    left = list(range(N))
    rb = "R" if basis == "Z" else "RX"
    mb = "M" if basis == "Z" else "MX"
    for r in range(1, T + 1):
        c = (r - 1 + first_c) % 2
        p = 1 - c
        ops = [("RX", sorted(meas[p]["X"])), ("R", sorted(meas[p]["Z"]))]
        if r == 1:
            ops.append((rb, left))
        C.add(ops, (r, "R"))
        for k, layer in enumerate(reversed(gates[p])):
            C.add([("CX", layer)], (r, f"Fd{k}"))
        for k, layer in enumerate(gates[c]):
            C.add([("CX", layer)], (r, f"F{k}"))
        ops = [("MX", sorted(meas[c]["X"])), ("M", sorted(meas[c]["Z"]))]
        if r == T and final:
            ops.append((mb, left))
        C.add(ops, (r, "M"))
    return C, gates, meas
