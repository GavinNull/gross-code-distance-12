"""E-040 bulk (infinitely many rounds) fault model of a translation-invariant single-ancilla schedule, one sector.

sector 'X' (Z-basis memory): X errors; detectors D(c', r) = m(c', r) + m(c', r-1) of the Z checks c'; faults:
  data   ('d', q, b, r): X on data q just after its read by reader label b in round r (time tR[b] + rP + 1/2);
         every cut slot between two consecutive reads of q is one of these (3 per period);
  hook   ('h', c, S, j): X-check c, instance j, ancilla X error after the CNOT preceding the suffix S (set of labels,
         2 <= |S| <= 5): X inserted on T[c][m] just after time tH[m] + jP for every m in S;
  meas   ('m', c', r): flip of m(c', r) -> D(c', r), D(c', r+1).
A data X error at time t on q flips D(c', floor((t - tR[b]) / P) + 1) for each reader (c', b) of q.
sector 'Z' is the same with the roles of X and Z exchanged (Z-check hooks, X-check readers, X-basis memory).

Everything is computed from the absolute CNOT times tH (hook side) and tR (reader side); it depends only on the
signature (orders and G).  Validated against stim DEMs in validate.py.
"""
from __future__ import annotations

import numpy as np

from search.experiments.e040.codes import MOD

AL, BL = (0, 1, 2), (3, 4, 5)


class Sector:
    def __init__(self, code, kind, tX, tZ, P):
        C = MOD[code]
        self.C, self.code, self.kind, self.P = C, code, kind, P
        T = C.table()
        hk, rk = ("X", "Z") if kind == "X" else ("Z", "X")
        self.TH, self.TR = T[hk], T[rk]
        self.tH = list(tX) if kind == "X" else list(tZ)
        self.tR = list(tZ) if kind == "X" else list(tX)
        self.order = tuple(int(v) for v in np.argsort(self.tH, kind="stable"))
        H, L = C.HLk(kind)
        self.H, self.L = H, L
        self.N2, self.NQ = C.N2, C.NQ
        self.readers = [[] for _ in range(C.NQ)]          # q -> [(c', b)]
        for c in range(C.N2):
            for b in range(6):
                self.readers[int(self.TR[c][b])].append((c, b))
        for q in range(C.NQ):
            assert len(self.readers[q]) == 3

    def suffixes(self):
        o = self.order
        return [frozenset(o[k:]) for k in range(1, 5)]      # sizes 5, 4, 3, 2

    def det_data_time(self, q, t2):
        """t2 = 2 * time (half-integer times allowed).  returns list of (c', r)."""
        P = self.P
        return [(c, (t2 - 2 * self.tR[b]) // (2 * P) + 1) for c, b in self.readers[q]]

    def dets(self, f):
        P = self.P
        if f[0] == "d":
            _, q, b, r = f
            return self.det_data_time(q, 2 * (self.tR[b] + r * P) + 1)
        if f[0] == "h":
            _, c, S, j = f
            out = []
            for m in S:
                out += self.det_data_time(int(self.TH[c][m]), 2 * (self.tH[m] + j * P) + 1)
            return out
        if f[0] == "m":
            _, c, r = f
            return [(c, r), (c, r + 1)]
        raise ValueError(f)

    def data_of(self, f):
        if f[0] == "d":
            return [f[1]]
        if f[0] == "h":
            return [int(self.TH[f[1]][m]) for m in f[2]]
        return []

    def effect(self, faults):
        """(set of flipped detectors (parity), residual data vector)."""
        par = {}
        for f in faults:
            for d in self.dets(f):
                par[d] = par.get(d, 0) ^ 1
        e = np.zeros(self.NQ, np.uint8)
        for f in faults:
            for q in self.data_of(f):
                e[q] ^= 1
        return {d for d, v in par.items() if v}, e

    def is_witness(self, faults):
        D, e = self.effect(faults)
        return (not D) and bool((self.L @ e % 2).any()), D, e

    def all_mechanisms(self, rlo, rhi):
        """every fault with anchor round in [rlo, rhi]."""
        out = []
        for q in range(self.NQ):
            for c, b in self.readers[q]:
                for r in range(rlo, rhi + 1):
                    out.append(("d", q, b, r))
        for c in range(self.N2):
            for S in self.suffixes():
                for j in range(rlo, rhi + 1):
                    out.append(("h", c, S, j))
        for c in range(self.N2):
            for r in range(rlo, rhi + 1):
                out.append(("m", c, r))
        return out


def spec_of(code, tX, tZ, P):
    """evaluator schedule dict for the translation-invariant schedule (prep just before the first CNOT, measurement
    just after the last; times mod P)."""
    C = MOD[code]
    T = C.table()
    out = {"format": "qec-schedule/v1", "period": P, "x_checks": [], "z_checks": []}
    for ty, t, key in (("X", tX, "x_checks"), ("Z", tZ, "z_checks")):
        lo, hi = min(t), max(t)
        for i in range(C.N2):
            out[key].append({"prep": (lo - 1) % P, "meas": (hi + 1) % P,
                             "cnots": [[int(T[ty][i][k]), int(t[k] % P)] for k in range(6)]})
    return out
