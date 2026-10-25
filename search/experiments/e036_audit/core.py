"""E-036 audit (auditor, 2026-10-26): independent core.  Nothing here imports evaluators/ or search/experiments/e036.

Code (arXiv 2505.09684 SI Sec. I.1, as quoted by WebFetch): l = m = 3, x = S_3 (x) I_3, y = I_3 (x) S_3,
A = x^1 + y^0 + y^2 (terms A1, A2, A3 in that written order), B = y^1 + x^0 + x^2 (B1, B2, B3),
H_X = [A | B], H_Z = [B^T | A^T].  Data qubit i < 9 is the L block, 9 + i the R block; check row r is X^r / Z^r.

Schedules: dict  check_key -> list of 6 layers (layer of term 0..5 = A1 A2 A3 B1 B2 B3 for X checks,
A1^T A2^T A3^T B1^T B2^T B3^T for Z checks), all checks prepared at layer 0 and measured at layer S+1
(non-wrapping "one round per window" template).  check_key = ("X", r) or ("Z", r).

Two independent fault models for the exact circuit distance:
  * stim_circuit(...)   : my own stim circuit + my own SD6 noise (reset or no-reset ancillas), full DEM;
  * symbolic_mechs(...) : closed-form list of all relevant single-fault effects (X parts in Z memory, Z parts in
                          X memory), derived by hand from Pauli propagation; no stim.
min_weight_le(...) is an exact meet-in-the-middle search for an undetectable logical of weight <= wmax (<= 3).
"""
from __future__ import annotations

import itertools
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np

L = M = 3
NH = 9


def shift(n):
    S = np.zeros((n, n), np.uint8)
    for i in range(n):
        S[i, (i + 1) % n] = 1
    return S


Xm = np.kron(shift(L), np.eye(M, dtype=np.uint8))
Ym = np.kron(np.eye(L, dtype=np.uint8), shift(M))
I9 = np.eye(9, dtype=np.uint8)
A_TERMS = [Xm, I9, np.linalg.matrix_power(Ym, 2) % 2]          # A1 = x, A2 = 1, A3 = y^2
B_TERMS = [Ym, I9, np.linalg.matrix_power(Xm, 2) % 2]          # B1 = y, B2 = 1, B3 = x^2
A = sum(A_TERMS) % 2
B = sum(B_TERMS) % 2
HX_FULL = np.hstack([A, B]).astype(np.uint8)
HZ_FULL = np.hstack([B.T, A.T]).astype(np.uint8)

VARIANTS = {
    "bb18": ([0, 1, 3, 4, 5, 6, 7], [0, 1, 2, 5, 6, 7, 8]),
    "q1863": ([0, 1, 3, 4, 6, 7], [0, 1, 2, 6, 7, 8]),
    "full": (list(range(9)), list(range(9))),
}


def term_qubit(kind, r, t):
    """data qubit touched by term t of check (kind, r)."""
    if kind == "X":
        Mt = A_TERMS[t] if t < 3 else B_TERMS[t - 3]
        off = 0 if t < 3 else NH
        return off + int(np.nonzero(Mt[r])[0][0])
    # Z row r of [B^T | A^T]: terms A_t^T live in the R block, B_t^T in the L block
    Mt = (A_TERMS[t] if t < 3 else B_TERMS[t - 3]).T
    off = NH if t < 3 else 0
    return off + int(np.nonzero(Mt[r])[0][0])


def checks(variant):
    xs, zs = VARIANTS[variant]
    return [("X", r) for r in xs] + [("Z", r) for r in zs]


def support(k):
    return [term_qubit(k[0], k[1], t) for t in range(6)]


# ----------------------------------------------------------------------------- GF(2)
def rref(Mx):
    Mx = (np.array(Mx, np.uint8) % 2).copy()
    piv = []
    r = 0
    for c in range(Mx.shape[1]):
        p = [i for i in range(r, Mx.shape[0]) if Mx[i, c]]
        if not p:
            continue
        Mx[[r, p[0]]] = Mx[[p[0], r]]
        for i in range(Mx.shape[0]):
            if i != r and Mx[i, c]:
                Mx[i] ^= Mx[r]
        piv.append(c)
        r += 1
        if r == Mx.shape[0]:
            break
    return Mx[:r], piv


def rank(Mx):
    return len(rref(Mx)[1])


def nullspace(Mx):
    R_, piv = rref(Mx)
    n = Mx.shape[1]
    free = [c for c in range(n) if c not in piv]
    out = []
    for f in free:
        v = np.zeros(n, np.uint8)
        v[f] = 1
        for i, p in enumerate(piv):
            if R_[i, f]:
                v[p] = 1
        out.append(v)
    return np.array(out, np.uint8)


def logical_basis(Hc, Hs):
    """vectors in ker(Hc) independent modulo rowspace(Hs)."""
    ker = nullspace(Hc)
    base = Hs.copy()
    out = []
    for v in ker:
        if rank(np.vstack([base, v])) > rank(base):
            out.append(v)
            base = np.vstack([base, v])
    return np.array(out, np.uint8)


def code_mats(variant):
    xs, zs = VARIANTS[variant]
    return HX_FULL[xs], HZ_FULL[zs]


def observables(variant, basis):
    """Z memory: Z-type logical operators (commute with X checks) measured on final data; X memory: X-type."""
    HX, HZ = code_mats(variant)
    if basis == "Z":
        return logical_basis(HX, HZ)
    return logical_basis(HZ, HX)


# ----------------------------------------------------------------------------- schedules
def kunlun_schedule(variant):
    """Reconstruction of SI Fig. S3 used by E-036 (IBM 2308.07915 slot order, CNOT layers 1..7)."""
    SX = [None, 1, 4, 3, 5, 0, 2]   # -, A2, B2, B1, B3, A1, A3
    SZ = [0, 2, 3, 4, 5, 1, None]   # A1T, A3T, B1T, B2T, B3T, A2T, -
    T = {}
    for k in checks(variant):
        sl = SX if k[0] == "X" else SZ
        t = [None] * 6
        for s, term in enumerate(sl):
            if term is not None:
                t[term] = s + 1
        T[k] = t
    return T, 7


def schedule_from_json(path, variant):
    """Parse a qec-schedule/v1 json: identify each listed check by its support (so a mislabelled row is caught)."""
    import json
    d = json.load(open(path))
    P = d["period"]
    T = {}
    for kind, key in (("X", "x_checks"), ("Z", "z_checks")):
        for row in d[key]:
            qs = sorted(q for q, _ in row["cnots"])
            match = [k for k in checks(variant) if k[0] == kind and sorted(support(k)) == qs]
            assert len(match) == 1, (kind, qs, match)
            k = match[0]
            assert k not in T
            assert row["prep"] == 0 and row["meas"] == P - 1, row
            lay = {q: t for q, t in row["cnots"]}
            T[k] = [lay[q] for q in support(k)]
    assert set(T) == set(checks(variant)), "checks missing"
    return T, P - 2


def legal(T, variant, S):
    """single-ancilla legality: layers in 1..S, one gate per qubit per layer, determinism parity condition."""
    ks = checks(variant)
    busy = {}
    for k in ks:
        if len(set(T[k])) != 6 or not all(1 <= t <= S for t in T[k]):
            return False, f"check {k} layers"
        for q, t in zip(support(k), T[k]):
            if (q, t) in busy:
                return False, f"qubit {q} layer {t} used twice"
            busy[(q, t)] = k
    for kx in ks:
        if kx[0] != "X":
            continue
        for kz in ks:
            if kz[0] != "Z":
                continue
            sx = dict(zip(support(kx), T[kx]))
            sz = dict(zip(support(kz), T[kz]))
            sh = set(sx) & set(sz)
            if sum(sx[q] < sz[q] for q in sh) % 2:
                return False, f"{kx},{kz} odd"
    return True, ""


# ----------------------------------------------------------------------------- own stim circuit
def stim_circuit(T, S, variant, basis, R, p=1e-3, reset=True, all_detectors=True):
    """My SD6: DEPOLARIZE2(p) after every CX, DEPOLARIZE1(p) on idle qubits in every layer (incl. prep/meas layers),
    DEPOLARIZE1(p) after H, flip p after reset, measurement record flip p (M(p) / MX(p)).
    reset=False: ancillas reset once at the start; each round X ancillas get H, CNOTs, H, M; Z ancillas CNOTs, M;
    no reset (Kunlun).  Detectors are m_j xor m_{j-2} (no reset) or m_j xor m_{j-1} (reset)."""
    import stim
    ks = checks(variant)
    nd = 18
    anc = {k: nd + i for i, k in enumerate(ks)}
    allq = list(range(nd + len(ks)))
    c = stim.Circuit()
    rec = {}
    nm = 0

    def idle(used):
        rest = [q for q in allq if q not in used]
        if rest and p > 0:
            c.append("DEPOLARIZE1", rest, p)

    # data init
    c.append("R" if basis == "Z" else "RX", list(range(nd)))
    c.append("X_ERROR" if basis == "Z" else "Z_ERROR", list(range(nd)), p)
    if not reset:
        c.append("R", [anc[k] for k in ks])
        c.append("X_ERROR", [anc[k] for k in ks], p)
    c.append("TICK")
    xa = [anc[k] for k in ks if k[0] == "X"]
    za = [anc[k] for k in ks if k[0] == "Z"]
    for j in range(R):
        # prep layer 0
        if reset:
            c.append("RX", xa)
            c.append("Z_ERROR", xa, p)
            c.append("R", za)
            c.append("X_ERROR", za, p)
            idle(set(xa + za))
        else:
            c.append("H", xa)
            c.append("DEPOLARIZE1", xa, p)
            idle(set(xa))
        c.append("TICK")
        for t in range(1, S + 1):
            used = set()
            pairs = []
            for k in ks:
                for q, tt in zip(support(k), T[k]):
                    if tt == t:
                        pairs += [anc[k], q] if k[0] == "X" else [q, anc[k]]
                        used |= {anc[k], q}
            if pairs:
                c.append("CX", pairs)
                c.append("DEPOLARIZE2", pairs, p)
            idle(used)
            c.append("TICK")
        # meas layer S+1
        if reset:
            c.append("MX", xa, p)
            c.append("M", za, p)
            idle(set(xa + za))
            order = [k for k in ks if k[0] == "X"] + [k for k in ks if k[0] == "Z"]
        else:
            c.append("H", xa)
            c.append("DEPOLARIZE1", xa, p)
            c.append("TICK")
            c.append("M", xa + za, p)
            idle(set(xa + za))
            order = [k for k in ks if k[0] == "X"] + [k for k in ks if k[0] == "Z"]
        for k in order:
            rec[(k, j)] = nm
            nm += 1
        c.append("TICK")
        for k in ks:
            mem = k[0] == basis
            if not mem and j == 0:
                continue
            if reset:
                lst = [rec[(k, j)]] + ([rec[(k, j - 1)]] if j >= 1 else [])
            else:
                # s_j = m_j ^ m_{j-1};  D_j = s_j ^ s_{j-1} = m_j ^ m_{j-2}
                lst = [rec[(k, j)]] + ([rec[(k, j - 2)]] if j >= 2 else [])
                if not mem and j == 1:
                    lst = [rec[(k, 1)]]  # X check in Z memory: s_0 random; D_1 = m_1 (shown deterministic)
            if not mem and not all_detectors:
                continue
            c.append("DETECTOR", [stim.target_rec(x - nm) for x in lst])
    # final data readout
    c.append("M" if basis == "Z" else "MX", list(range(nd)), p)
    dm = {q: nm + q for q in range(nd)}
    nm += nd
    for k in ks:
        if k[0] != basis:
            continue
        lst = [dm[q] for q in support(k)]
        if reset:
            lst.append(rec[(k, R - 1)])
        else:
            lst.append(rec[(k, R - 1)])
            if R >= 2:
                lst.append(rec[(k, R - 2)])
        c.append("DETECTOR", [stim.target_rec(x - nm) for x in lst])
    for i, v in enumerate(observables(variant, basis)):
        c.append("OBSERVABLE_INCLUDE", [stim.target_rec(dm[q] - nm) for q in np.nonzero(v)[0]], i)
    return c


def stim_mechs(circ):
    dem = circ.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    out = set()
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        d = o = 0
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                d ^= 1 << t.val
            elif t.is_logical_observable_id():
                o ^= 1 << t.val
        if d or o:
            out.add((d, o))
    return sorted(out)


# ----------------------------------------------------------------------------- symbolic fault model
class Sym:
    """Closed-form single-fault effects for the non-wrapping template.

    memory basis b; readers = checks of type b; spreaders = the other type.  Relevant Pauli: X (b = Z) / Z (b = X).
    s(c, j), j = 0..R-1: syndrome bit of reader c in round j; s(c, R) = final data parity of supp(c).
    Detectors D(c, j) = s(c, j) ^ s(c, j-1), j = 0..R (s(c, -1) = 0).
    Mechanisms (each one SD6 fault; together all relevant-part effects of SD6 faults):
      data cut  (q, j, A): relevant Pauli on q in round j after the reader CNOTs not in A and before those in A.
                s(c, j') flips for c in A, j' >= j and for c in B (readers of q not in A), j' >= j+1.
      spreader cut (k, j, p): spreader ancilla error after its p-th CNOT (p = 1..5) = data cuts on each later
                CNOT's qubit right after that CNOT.
      reader flip (c, j): s(c, j) only (reset meas error / reset error / ancilla error).
      readout flip (no reset only) (c, j): m(c, j) only -> s(c, j) and s(c, j+1) (j+1 <= R-1).
    Every effect also carries the 'tag' needed for nogood extraction."""

    def __init__(self, variant, basis, T, R, reset=True):
        self.v, self.b, self.T, self.R = variant, basis, T, R
        ks = checks(variant)
        self.readers = [k for k in ks if k[0] == basis]
        self.spreaders = [k for k in ks if k[0] != basis]
        self.ridx = {k: i for i, k in enumerate(self.readers)}
        self.obs = observables(variant, basis)
        self.reset = reset
        # reader events on each qubit
        self.rev = {q: [] for q in range(18)}
        for k in self.readers:
            for a, q in enumerate(support(k)):
                self.rev[q].append(((k, a), T[k][a]))

    def det_bit(self, c, j):
        return self.ridx[c] * (self.R + 1) + j

    def s_flip_to_D(self, sflips):
        """sflips: dict reader -> set of j with s(c,j) flipped (j in 0..R).  Return detector bitmask."""
        d = 0
        for c, js in sflips.items():
            for j in js:
                d ^= 1 << self.det_bit(c, j)
                if j + 1 <= self.R:
                    d ^= 1 << self.det_bit(c, j + 1)
        return d

    def data_err(self, q, j, after_time):
        """relevant error on q in round j at time after_time (strictly after CNOTs at <= after_time).
        Returns (detmask, obsmask, B, A) with B / A the reader events before / after."""
        R = self.R
        d = 0
        B, Aa = [], []
        for e, t in self.rev[q]:
            c = e[0]
            j0 = j if t > after_time else j + 1
            (Aa if t > after_time else B).append(e)
            if j0 <= R:
                d ^= 1 << self.det_bit(c, j0)   # persistent flip from j0 on -> only D(c, j0)
        o = 0
        for i, v in enumerate(self.obs):
            if v[q]:
                o ^= 1 << i
        return d, o, B, Aa

    def mechs(self):
        """list of (detmask, obsmask, tag).  tag = ('data', q, B, A) | ('spread', k, pre, suf) | ('meas',)"""
        out = []
        R = self.R
        S_max = max(max(v) for v in self.T.values())
        for j in range(R):
            for q in range(18):
                ts = sorted(set([0] + [t for _, t in self.rev[q]]))
                for at in ts:  # cut right after time 'at' (0 = before all CNOTs)
                    d, o, B, Aa = self.data_err(q, j, at)
                    out.append((d, o, ("data", q, tuple(B), tuple(Aa))))
            for k in self.spreaders:
                order = sorted(range(6), key=lambda a: self.T[k][a])
                for p in range(1, 6):
                    pre = [(k, a) for a in order[:p]]
                    suf = [(k, a) for a in order[p:]]
                    d = o = 0
                    for (_, a) in suf:
                        q = support(k)[a]
                        dd, oo, _, _ = self.data_err(q, j, self.T[k][a])
                        d ^= dd
                        o ^= oo
                    out.append((d, o, ("spread", k, tuple(pre), tuple(suf))))
            for c in self.readers:
                out.append((self.s_flip_to_D({c: {j}}), 0, ("meas",)))
                if not self.reset and j + 1 <= R - 1:
                    out.append((self.s_flip_to_D({c: {j, j + 1}}), 0, ("meas",)))
        # final readout flips = data cut after all readers in round R-1 (already included); data init = cut 0 round 0.
        return out

    def literals(self, tag):
        """order literals (e1 before e2) that guarantee the same effect in any schedule of the template."""
        lits = set()
        if tag[0] == "data":
            _, q, B, Aa = tag
            lits |= {(b, a) for b in B for a in Aa}
        elif tag[0] == "spread":
            _, k, pre, suf = tag
            lits |= {(f, g) for f in pre for g in suf}
            for g in suf:
                q = support(k)[g[1]]
                tg = self.T[k][g[1]]
                for e, t in self.rev[q]:
                    lits.add((e, g) if t < tg else (g, e))
        return lits


def min_weight_le(mechs, wmax=3, want_all=False, limit=200):
    """mechs: list of (d, o, ...).  Exact smallest w <= wmax with an undetectable logical; returns (w, [witness tuples])
    (all witnesses of that weight up to 'limit' if want_all)."""
    D = [m[0] for m in mechs]
    O = [m[1] for m in mechs]
    n = len(mechs)
    wits = []
    for i in range(n):
        if D[i] == 0 and O[i]:
            wits.append((i,))
            if not want_all or len(wits) >= limit:
                return 1, wits
    if wits:
        return 1, wits
    if wmax < 2:
        return None, []
    by = {}
    for i in range(n):
        by.setdefault(D[i], []).append(i)
    for key, lst in by.items():
        for a, b in itertools.combinations(lst, 2):
            if O[a] != O[b]:
                wits.append((a, b))
                if not want_all or len(wits) >= limit:
                    return 2, wits
    if wits:
        return 2, wits
    if wmax < 3:
        return None, []
    for i in range(n):
        for j in range(i + 1, n):
            lst = by.get(D[i] ^ D[j])
            if not lst:
                continue
            oo = O[i] ^ O[j]
            for k in lst:
                if k > j and O[k] != oo:
                    wits.append((i, j, k))
                    if not want_all or len(wits) >= limit:
                        return 3, wits
    if wits:
        return 3, wits
    return None, []
