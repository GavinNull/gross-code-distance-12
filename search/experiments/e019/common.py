"""E-019: Shaw-Terhal morphing circuits for weight-6 BB codes, general (l, m, A, B), three circuit variants.

Generalisation of the E-017 auditor's construction (research/audits/2026-10-08-E-017-scripts/common.py), which was
written from the public repo Mac-Shaw/morphing_qec_circuits (bb_params.py, read only, not executed) and checked
gate-by-gate against search/experiments/e017/morph.py.

Variants (all two-round, homomorphism f: G -> Z_2):
  "repo"  : get_standard_morphing_specification (layer 0 uses b2/a2, layer 1 b3/a3)
  "paper" : same with layers 0/1 exchanged (2407.16336 Table II/IV order)
  "swap2" : get_swap2_morphing_specification ("Table VIII", App. G.2 'reversing the CNOTs in Round 2'):
            round f(g):   L(g)->R(-a1+b3+g); R(-a1+b2+g)->L(g); L(g)->R(-a2+b2+g) [MZ on R(-a2+b2+g)]
            round f(g)+1: R(-a3+b1+g)->L(g); L(g)->R(-a2+b1+g); R(-a2+b2+g)->L(g) [MX on R(-a2+b2+g)]
In all variants a, b are the polynomial term lists with the unique f-odd-one-out moved to position 0 (repo
`prepare_for_standard_morphing`). Validity (contraction property) is checked by Pauli propagation, not assumed.

Qubits: L(g) = idx(g) in 0..N-1, R(g) = N + idx(g), idx(i, j) = i*m + j, group Z_l x Z_m written additively.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import stim

HOMS = {"x": lambda g: g[0] % 2, "y": lambda g: g[1] % 2, "xy": lambda g: (g[0] + g[1]) % 2}

A6 = [(3, 0), (0, 1), (0, 2)]
B6 = [(0, 3), (1, 0), (2, 0)]
CODES = {   # Table I of 2407.16336 (= Table 3 of 2308.07915)
    "bb72": (6, 6, A6, B6),
    "bb108": (9, 6, A6, B6),
    "bb144": (12, 6, A6, B6),
    "bb288": (12, 12, [(3, 0), (0, 7), (0, 2)], B6),
}


# ---------------------------------------------------------------- GF(2)
def rref(M):
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
    M = np.asarray(M)
    if M.size == 0:
        return 0
    return len(rref(M)[1])


def nullspace(M):
    M = np.array(M, dtype=np.uint8) & 1
    cols = M.shape[1]
    Rm, piv = rref(M)
    ps = set(piv)
    free = [c for c in range(cols) if c not in ps]
    out = np.zeros((len(free), cols), dtype=np.uint8)
    for k, f in enumerate(free):
        out[k, f] = 1
        for i, p in enumerate(piv):
            if Rm[i, f]:
                out[k, p] = 1
    return out


def logicals(Hstab, Hother):
    """basis of ker(Hother) modulo rowspace(Hstab)"""
    K = nullspace(Hother)
    out = []
    cur = rref(Hstab)[0]
    rk = cur.shape[0]
    for v in K:
        t = np.vstack([cur, v])
        if rank(t) > rk:
            out.append(v)
            cur = rref(t)[0]
            rk += 1
    return np.array(out, dtype=np.uint8)


# ---------------------------------------------------------------- code + spec
@dataclass
class Code:
    name: str
    l: int
    m: int
    A: list
    B: list

    @property
    def N(self):
        return self.l * self.m

    def gid(self, i, j):
        return (i % self.l) * self.m + (j % self.m)

    def L(self, i, j):
        return self.gid(i, j)

    def R(self, i, j):
        return self.N + self.gid(i, j)

    def coords(self, q):
        q = q % self.N
        return q // self.m, q % self.m

    def poly_matrix(self, poly):
        N = self.N
        M = np.zeros((N, N), dtype=np.uint8)
        for i in range(self.l):
            for j in range(self.m):
                for (a, b) in poly:
                    M[self.gid(i, j), self.gid(i + a, j + b)] ^= 1
        return M

    def checks(self):
        Am, Bm = self.poly_matrix(self.A), self.poly_matrix(self.B)
        return np.concatenate([Am, Bm], axis=1), np.concatenate([Bm.T, Am.T], axis=1)

    def translate_q(self, q, s):
        i, j = self.coords(q)
        return (self.N if q >= self.N else 0) + self.gid(i + s[0], j + s[1])


def get_code(name):
    l, m, A, B = CODES[name]
    return Code(name, l, m, list(A), list(B))


def hom_valid(code, hom):
    if hom in ("x", "xy") and code.l % 2:
        return False
    if hom in ("y", "xy") and code.m % 2:
        return False
    f = HOMS[hom]
    for poly in (code.A, code.B):
        v = [f(e) for e in poly]
        if not (v.count(0) == 1 or v.count(1) == 1):
            return False
    return True


def prepared(code, hom):
    f = HOMS[hom]
    lists = []
    for poly in (code.A, code.B):
        c = list(poly)
        vals = [f(e) for e in c]
        sv = 0 if vals.count(0) == 1 else 1
        k = vals.index(sv)
        c[0], c[k] = c[k], c[0]
        lists.append(c)
    return lists


VARIANTS = {   # name -> (kind, swap a2<->a3, swap b2<->b3)
    "repo": ("std", 0, 0), "paper": ("std", 1, 1), "std01": ("std", 0, 1), "std10": ("std", 1, 0),
    "swap2": ("sw2", 0, 0), "sw01": ("sw2", 0, 1), "sw10": ("sw2", 1, 0), "sw11": ("sw2", 1, 1),
}


def spec(code, hom, variant):
    """gates[r][layer] = list of (control, target); meas[r] = {"X": [...], "Z": [...]} for contraction round r.
    'paper' (Table II order) == repo construction with a2<->a3 and b2<->b3 exchanged; std01/std10 exchange only
    one pair (the order of the two non-special terms of A, B is a free convention of the input polynomials).
    swap2 (Table VIII) with the same four ordering choices: swap2 = repo input order, sw01/sw10/sw11."""
    assert hom_valid(code, hom), (code.name, hom)
    f = HOMS[hom]
    kind, sa, sb = VARIANTS[variant]
    a, b = prepared(code, hom)
    if sa:
        a = [a[0], a[2], a[1]]
    if sb:
        b = [b[0], b[2], b[1]]
    gates = [[[] for _ in range(3)] for _ in range(2)]
    meas = [{"X": [], "Z": []} for _ in range(2)]
    R = code.R
    for i in range(code.l):
        for j in range(code.m):
            rg = f((i, j))
            rh = 1 - rg
            Lq = code.L(i, j)
            if kind == "std":
                rgq = [R(i - a[0][0] + e[0], j - a[0][1] + e[1]) for e in b]
                rhq = [R(i - e[0] + b[0][0], j - e[1] + b[0][1]) for e in a]
                for k in range(1, 3):
                    layer = k - 1
                    gates[rg][layer].append((Lq, rgq[k]))
                    gates[rh][layer].append((rhq[k], Lq))
                gates[rg][2].append((rgq[0], Lq))
                gates[rh][2].append((Lq, rhq[0]))
                meas[rg]["X"].append(rgq[0])
                meas[rh]["Z"].append(rhq[0])
            elif kind == "sw2":
                rgq = [R(i - a[0][0] + e[0], j - a[0][1] + e[1]) for e in b]
                rhq = [R(i - e[0] + b[0][0], j - e[1] + b[0][1]) for e in a]
                nuc = R(i - a[1][0] + b[1][0], j - a[1][1] + b[1][1])
                gates[rg][0].append((Lq, rgq[2]))
                gates[rh][0].append((rhq[2], Lq))
                gates[rg][1].append((rgq[1], Lq))
                gates[rh][1].append((Lq, rhq[1]))
                gates[rg][2].append((Lq, nuc))
                gates[rh][2].append((nuc, Lq))
                meas[rg]["Z"].append(nuc)
                meas[rh]["X"].append(nuc)
            else:
                raise ValueError(variant)
    for r in range(2):
        for layer in gates[r]:
            qs = [q for pr in layer for q in pr]
            assert len(qs) == len(set(qs)), "qubit used twice in a layer"
        assert len(set(meas[r]["X"]) | set(meas[r]["Z"])) == code.N
    return gates, meas, a, b


def propagate(x, z, layers):
    """Heisenberg-forward through CNOT layers: P -> U P U^dag (bool arrays, copied)."""
    x = x.copy()
    z = z.copy()
    for layer in layers:
        for (c, t) in layer:
            x[t] ^= x[c]
            z[c] ^= z[t]
    return x, z


def analyse(code, gates, meas):
    """Contraction property + end-cycle codes. Returns dict with end-cycle check matrices per round."""
    HX, HZ = code.checks()
    N = code.N
    assert not np.any((HX.astype(int) @ HZ.T.astype(int)) % 2)
    out = {"k_mid": int(2 * N - rank(HX) - rank(HZ))}
    stabinfo = {}
    contracted = {("X", r): set() for r in range(N)}
    contracted.update({("Z", r): set() for r in range(N)})
    ec = {}
    for c in range(2):
        rowsX, rowsZ = [], []
        for P, H in (("X", HX), ("Z", HZ)):
            for r in range(N):
                v = H[r].astype(bool)
                zero = np.zeros(2 * N, bool)
                if P == "X":
                    x, z = propagate(v, zero, gates[c])
                    sup = np.nonzero(x)[0]
                    assert not z.any()
                else:
                    x, z = propagate(zero, v, gates[c])
                    sup = np.nonzero(z)[0]
                    assert not x.any()
                if len(sup) == 1 and sup[0] >= N:
                    assert sup[0] in meas[c][P], "contracted onto wrong-basis measurement"
                    contracted[(P, r)].add(c)
                    stabinfo.setdefault((P, r), {})[c] = ("contract", int(sup[0]))
                else:
                    Rs = [q for q in sup if q >= N]
                    stabinfo.setdefault((P, r), {})[c] = ("expand", [int(q) for q in sup if q < N], [int(q) for q in Rs])
                    assert set(Rs) <= set(meas[c][P]), "expanding stabiliser hits wrong-basis measurement"
                    vv = np.zeros(N, np.uint8)
                    vv[[q for q in sup if q < N]] = 1
                    (rowsX if P == "X" else rowsZ).append(vv)
        ec[c] = {"X": np.array(rowsX), "Z": np.array(rowsZ)}
        nX = sum(1 for r in range(N) if c in contracted[("X", r)])
        nZ = sum(1 for r in range(N) if c in contracted[("Z", r)])
        out[f"round{c}_contracted"] = (nX, nZ)
    out["each_stab_contracted_once"] = all(len(s) == 1 for s in contracted.values())
    for c in range(2):
        HXe, HZe = ec[c]["X"], ec[c]["Z"]
        assert not np.any((HXe.astype(int) @ HZe.T.astype(int)) % 2)
        out[f"ec{c}"] = dict(n=N, rankX=rank(HXe), rankZ=rank(HZe), k=int(N - rank(HXe) - rank(HZe)),
                             wX=sorted(set(map(int, HXe.sum(1)))), wZ=sorted(set(map(int, HZe.sum(1)))))
    deg = np.zeros(2 * N, int)
    nb = [set() for _ in range(2 * N)]
    for c in range(2):
        for layer in gates[c]:
            for (p, q) in layer:
                nb[p].add(q)
                nb[q].add(p)
    out["max_degree"] = max(len(s) for s in nb)
    ec["stabinfo"] = stabinfo
    return out, ec


# ---------------------------------------------------------------- circuits
class Circ:
    def __init__(self):
        self.layers = []
        self.nrec = 0
        self.recs = []

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
                    c.append("CX", [q for pr in ts for q in pr])
                elif ts:
                    c.append(op, ts)
            if extra_after_layer and li in extra_after_layer:
                c += extra_after_layer[li]
        return c


def memory(code, gates, meas, T=3, basis="Z", first_c=0):
    """Memory experiment: round-1 reset layer resets right qubits (bases of meas[p]) and left qubits (memory
    basis); T morphing rounds; final transversal readout of left qubits in the last M layer.
    Round r: contraction c = (r-1+first_c) % 2, previous p = 1-c. Layer tags (r, 'R'|'Fd0..2'|'F0..2'|'M')."""
    N = code.N
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
        if r == T:
            ops.append((mb, left))
        C.add(ops, (r, "M"))
    return C


def variants():
    """All (code, hom, variant) of the family with a valid homomorphism."""
    out = []
    for name in CODES:
        code = get_code(name)
        for hom in ("x", "y", "xy"):
            if hom_valid(code, hom):
                for v in VARIANTS:
                    out.append((name, hom, v))
    return out
