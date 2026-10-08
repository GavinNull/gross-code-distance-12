"""E-017: Shaw-Terhal morphing circuit for BB codes (arXiv 2407.16336, Table 2 / Table 4, App. D).

Independent implementation from the paper text (cross-read against the public repo
github.com/Mac-Shaw/morphing_qec_circuits `bb_params.get_standard_morphing_specification`, not executed).

Mid-cycle code C = BB code on 2*l*m qubits: left qubits L(g), right qubits R(g), g in G = Z_l x Z_m.
  s(X,g) = X(Ag, Bg),  s(Z,g) = Z(B^-1 g, A^-1 g).
Homomorphism f: G -> Z2 with f(a1) != f(a2) = f(a3), f(b1) != f(b2) = f(b3); K = ker f.
Contraction circuit F_j (j = 0: "g" ranges over K, "h" over K^c; j = 1: swapped):
  layer 0: CNOT(L(g), R(a1^-1 b2 g)),  CNOT(R(a2^-1 b1 h), L(h))      [repo order; paper Table 4 uses b3/a3 first]
  layer 1: CNOT(L(g), R(a1^-1 b3 g)),  CNOT(R(a3^-1 b1 h), L(h))
  layer 2: CNOT(R(a1^-1 b1 g), L(g)),  CNOT(L(h), R(a1^-1 b1 h))
  M_j: MX on R(a1^-1 b1 g) (g-set), MZ on R(a1^-1 b1 h) (h-set)     -> all right qubits measured
One measurement round t (ends in M_{j(t)}, j(t) = t mod 2):
  reset (the qubits measured by M_{j'} in their bases) | F_{j'}^dagger (3 layers reversed) | F_j (3 layers) | M_j
End-cycle perspective: left qubits = data of the end-cycle code (weight-9 checks), right qubits = ancillas.
Memory experiment (basis b in {X, Z}): left qubits reset in basis b in round 1's reset layer; after round T the
left qubits are measured in basis b in the same layer as M_{j(T)}.
Detectors / observables are derived by Pauli propagation through F_j (stim.PauliString.after) and checked.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np
import stim


# ----------------------------------------------------------------- group / code

@dataclass
class BB:
    l: int
    m: int
    A: list  # list of (i, j) exponents of x^i y^j
    B: list

    @property
    def N(self):
        return self.l * self.m

    def mul(self, g, h):
        return ((g[0] + h[0]) % self.l, (g[1] + h[1]) % self.m)

    def inv(self, g):
        return ((-g[0]) % self.l, (-g[1]) % self.m)

    def idx(self, g):
        return g[0] * self.m + g[1]

    def elems(self):
        return [(i, j) for i in range(self.l) for j in range(self.m)]

    def Lq(self, g):
        return self.idx(g)

    def Rq(self, g):
        return self.N + self.idx(g)

    def HX(self):
        H = np.zeros((self.N, 2 * self.N), dtype=np.uint8)
        for g in self.elems():
            r = self.idx(g)
            for a in self.A:
                H[r, self.Lq(self.mul(a, g))] ^= 1
            for b in self.B:
                H[r, self.Rq(self.mul(b, g))] ^= 1
        return H

    def HZ(self):
        H = np.zeros((self.N, 2 * self.N), dtype=np.uint8)
        for g in self.elems():
            r = self.idx(g)
            for b in self.B:
                H[r, self.Lq(self.mul(self.inv(b), g))] ^= 1
            for a in self.A:
                H[r, self.Rq(self.mul(self.inv(a), g))] ^= 1
        return H


TWO_GROSS = BB(12, 12, A=[(3, 0), (0, 7), (0, 2)], B=[(0, 3), (1, 0), (2, 0)])   # [[288,12,18]], 2308.07915 Table 3
GROSS = BB(12, 6, A=[(3, 0), (0, 1), (0, 2)], B=[(0, 3), (1, 0), (2, 0)])        # [[144,12,12]]

HOMS = {
    "x": lambda g: g[0] % 2,
    "y": lambda g: g[1] % 2,
    "xy": lambda g: (g[0] + g[1]) % 2,
}


# ----------------------------------------------------------------- GF(2)

def rref(M):
    M = (np.array(M, dtype=np.uint8) % 2).copy()
    piv = []
    r = 0
    for c in range(M.shape[1]):
        if r >= M.shape[0]:
            break
        nz = np.nonzero(M[r:, c])[0]
        if len(nz) == 0:
            continue
        p = r + nz[0]
        if p != r:
            M[[r, p]] = M[[p, r]]
        o = np.nonzero(M[:, c])[0]
        o = o[o != r]
        if len(o):
            M[o] ^= M[r]
        piv.append(c)
        r += 1
    return M[:r], piv


def rank(M):
    return len(rref(M)[1])


def nullspace(M):
    M = np.array(M, dtype=np.uint8) % 2
    n = M.shape[1]
    R, piv = rref(M)
    ps = set(piv)
    free = [c for c in range(n) if c not in ps]
    out = np.zeros((len(free), n), dtype=np.uint8)
    for t, f in enumerate(free):
        out[t, f] = 1
        for i, pc in enumerate(piv):
            if R[i, f]:
                out[t, pc] = 1
    return out


def logicals(H_same, H_other):
    """Basis of ker(H_other) modulo rowspace(H_same) (operators of the same type as H_same's rows)."""
    ker = nullspace(H_other)
    base = rref(H_same)[0]
    r0 = base.shape[0]
    out = []
    cur = base
    for v in ker:
        test = np.vstack([cur, v])
        if rank(test) > cur.shape[0]:
            out.append(v)
            cur = rref(test)[0]
    return np.array(out, dtype=np.uint8)


# ----------------------------------------------------------------- morphing spec

@dataclass
class Morph:
    code: BB
    hom: str
    swap23: bool = False   # True: paper Table 2/4 order (b3/a3 in layer 0); False: repo order (b2/a2 first)

    def __post_init__(self):
        c = self.code
        f = HOMS[self.hom]
        self.f = f

        def special_first(lst):
            vals = [f(e) for e in lst]
            for s in (0, 1):
                if vals.count(s) == 1 and vals.count(1 - s) == len(lst) - 1:
                    i = vals.index(s)
                    lst = list(lst)
                    lst[0], lst[i] = lst[i], lst[0]
                    return lst
            raise ValueError(f"criterion 1 fails for {lst} with f_{self.hom}")

        self.a = special_first(c.A)
        self.b = special_first(c.B)
        if self.swap23:
            self.a = [self.a[0], self.a[2], self.a[1]]
            self.b = [self.b[0], self.b[2], self.b[1]]
        a, b = self.a, self.b
        self.layers = {}
        self.meas = {}
        for j in (0, 1):
            gset = [g for g in c.elems() if f(g) == j]
            hset = [g for g in c.elems() if f(g) != j]
            a1i = c.inv(a[0])
            Ls = [[], [], []]
            for k in (1, 2):
                for g in gset:
                    Ls[k - 1].append((c.Lq(g), c.Rq(c.mul(c.mul(a1i, b[k]), g))))
                for h in hset:
                    Ls[k - 1].append((c.Rq(c.mul(c.mul(c.inv(a[k]), b[0]), h)), c.Lq(h)))
            for g in gset:
                Ls[2].append((c.Rq(c.mul(c.mul(a1i, b[0]), g)), c.Lq(g)))
            for h in hset:
                Ls[2].append((c.Lq(h), c.Rq(c.mul(c.mul(a1i, b[0]), h))))
            for lay in Ls:
                qs = [q for pr in lay for q in pr]
                assert len(qs) == len(set(qs)), "qubit used twice in a layer"
            self.layers[j] = Ls
            mx = sorted(c.Rq(c.mul(c.mul(a1i, b[0]), g)) for g in gset)
            mz = sorted(c.Rq(c.mul(c.mul(a1i, b[0]), h)) for h in hset)
            assert len(set(mx) | set(mz)) == c.N
            self.meas[j] = {"X": mx, "Z": mz}
        self._analyse()

    # -- circuits for propagation
    def F(self, j):
        circ = stim.Circuit()
        for lay in self.layers[j]:
            circ.append("CX", [q for pr in lay for q in pr])
        return circ

    def _ps(self, support, P):
        n = 2 * self.code.N
        s = stim.PauliString(n)
        for q in support:
            s[int(q)] = P
        return s

    def _analyse(self):
        c = self.code
        n = 2 * c.N
        HX, HZ = c.HX(), c.HZ()
        self.HX, self.HZ = HX, HZ
        self.LX = logicals(HX, HZ)   # X-type logicals of C
        self.LZ = logicals(HZ, HX)
        assert self.LX.shape[0] == self.LZ.shape[0]
        self.k = self.LX.shape[0]
        Fc = {j: self.F(j) for j in (0, 1)}
        # for every stabilizer / logical and every j: contraction qubit or (left support, right support)
        self.stab = {}   # (P, g_idx) -> {j: ("contract", q) | ("expand", Lsupp, Rsupp)}
        self.contract_set = {0: {"X": [], "Z": []}, 1: {"X": [], "Z": []}}
        for P, H in (("X", HX), ("Z", HZ)):
            for r in range(c.N):
                supp = np.nonzero(H[r])[0]
                d = {}
                for j in (0, 1):
                    o = self._ps(supp, P).after(Fc[j])
                    qs = [q for q in range(n) if o[q] != 0]
                    assert all(o[q] == (1 if P == "X" else 3) for q in qs)
                    if len(qs) == 1 and qs[0] >= c.N:
                        assert qs[0] in self.meas[j][P], "contracted onto wrong-basis measurement"
                        d[j] = ("contract", qs[0])
                        self.contract_set[j][P].append(r)
                    else:
                        Lsupp = [q for q in qs if q < c.N]
                        Rsupp = [q for q in qs if q >= c.N]
                        assert set(Rsupp) <= set(self.meas[j][P]), "expanding op hits wrong-basis meas"
                        d[j] = ("expand", Lsupp, Rsupp)
                self.stab[(P, r)] = d
        for j in (0, 1):
            for P in ("X", "Z"):
                assert len(self.contract_set[j][P]) == c.N // 2
        # union covers all stabilisers, each contracted exactly once
        for key, d in self.stab.items():
            assert [d[j][0] for j in (0, 1)].count("contract") == 1, key
        self.log = {}
        for P, Lm in (("X", self.LX), ("Z", self.LZ)):
            for r in range(self.k):
                supp = np.nonzero(Lm[r])[0]
                d = {}
                for j in (0, 1):
                    o = self._ps(supp, P).after(Fc[j])
                    qs = [q for q in range(n) if o[q] != 0]
                    Lsupp = [q for q in qs if q < c.N]
                    Rsupp = [q for q in qs if q >= c.N]
                    assert set(Rsupp) <= set(self.meas[j][P])
                    d[j] = (Lsupp, Rsupp)
                self.log[(P, r)] = d

    # -- end-cycle code
    def end_cycle_checks(self, j):
        """Checks of the end-cycle code after M_j (on left qubits 0..N-1): left parts of expanding stabilisers."""
        c = self.code
        out = {}
        for P in ("X", "Z"):
            rows = []
            for r in range(c.N):
                d = self.stab[(P, r)][j]
                if d[0] == "expand":
                    v = np.zeros(c.N, dtype=np.uint8)
                    v[d[1]] = 1
                    rows.append(v)
            out[P] = np.array(rows)
        return out

    # -- memory circuit
    def memory_circuit(self, basis: str, rounds: int, first_j: int = 1) -> stim.Circuit:
        """Noiseless memory circuit. Round t = 1..rounds ends in M_{j(t)}, j(1) = first_j, alternating."""
        c = self.code
        N = c.N
        circ = stim.Circuit()
        for g in c.elems():
            circ.append("QUBIT_COORDS", [c.Lq(g)], [2 * g[0], 2 * g[1], 0])
            circ.append("QUBIT_COORDS", [c.Rq(g)], [2 * g[0] + 1, 2 * g[1] + 1, 0])
        meas_index = {}     # (t, qubit) -> absolute measurement record index
        nm = 0
        Pm = basis
        Po = "X" if basis == "Z" else "Z"
        jt = lambda t: (first_j + t - 1) % 2
        for t in range(1, rounds + 1):
            j = jt(t)
            jp = 1 - j
            # reset layer
            rz = list(self.meas[jp]["Z"])
            rx = list(self.meas[jp]["X"])
            if t == 1:
                (rz if basis == "Z" else rx).extend(range(N))
            if rz:
                circ.append("R", sorted(rz))
            if rx:
                circ.append("RX", sorted(rx))
            circ.append("TICK")
            for lay in reversed(self.layers[jp]):
                circ.append("CX", [q for pr in lay for q in pr])
                circ.append("TICK")
            for lay in self.layers[j]:
                circ.append("CX", [q for pr in lay for q in pr])
                circ.append("TICK")
            mz = list(self.meas[j]["Z"])
            mx = list(self.meas[j]["X"])
            final = (t == rounds)
            order = []
            if mz:
                circ.append("M", mz)
                order += mz
            if mx:
                circ.append("MX", mx)
                order += mx
            for q in order:
                meas_index[(t, q)] = nm
                nm += 1
            if final:
                data = list(range(N))
                circ.append("M" if basis == "Z" else "MX", data)
                for q in data:
                    meas_index[("final", q)] = nm
                    nm += 1
            # detectors for round t
            for P in ("X", "Z"):
                for r in self.contract_set[j][P]:
                    q = self.stab[(P, r)][j][1]
                    recs = [meas_index[(t, q)]]
                    if t == 1:
                        if P != Pm:
                            continue
                    else:
                        _, _, Rs = self.stab[(P, r)][jp]
                        recs += [meas_index[(t - 1, x)] for x in Rs]
                    circ.append("DETECTOR", [stim.target_rec(x - nm) for x in recs],
                                [r, t, 0 if P == "X" else 1])
            if final:
                for r in range(N):
                    d = self.stab[(Pm, r)][j]
                    if d[0] != "expand":
                        continue
                    recs = [meas_index[("final", x)] for x in d[1]] + [meas_index[(t, x)] for x in d[2]]
                    circ.append("DETECTOR", [stim.target_rec(x - nm) for x in recs],
                                [r, t + 1, 0 if Pm == "X" else 1])
                for li in range(self.k):
                    recs = []
                    for tt in range(1, rounds + 1):
                        recs += [meas_index[(tt, x)] for x in self.log[(Pm, li)][jt(tt)][1]]
                    recs += [meas_index[("final", x)] for x in self.log[(Pm, li)][j][0]]
                    circ.append("OBSERVABLE_INCLUDE", [stim.target_rec(x - nm) for x in recs], li)
            if not final:
                circ.append("TICK")
        return circ


def check_deterministic(circ: stim.Circuit, shots: int = 64) -> tuple[bool, bool]:
    s = circ.compile_detector_sampler()
    det, obs = s.sample(shots, separate_observables=True)
    return (not det.any()), (not obs.any())
