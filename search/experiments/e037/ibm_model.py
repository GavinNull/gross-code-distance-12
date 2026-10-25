"""E-037: IBM depth-8 BB syndrome circuit and the decoder_setup.py fault model, rebuilt from scratch.  experimenter.

Source read (read-only WebFetch, 2026-10-25): github.com/sbravyi/BivariateBicycleCodes, decoder_setup.py.  Every choice
below follows that file; the places where its simulator differs from a textbook Pauli-frame simulation are kept
(flag `ibm_faithful`) and the effect is measured (it is none, see the journal).

Code (decoder_setup.py):  x = kron(roll(I_l, 1, axis=1), I_m),  y = kron(I_l, roll(I_m, 1, axis=1));
  A1 = x^a1, A2 = y^a2, A3 = y^a3, B1 = y^b1, B2 = x^b2, B3 = x^b3;  hx = [A | B], hz = [B^T | A^T].
  X-check i neighbours 0..2 = data_left  nonzero(A_k[i, :]),  3..5 = data_right nonzero(B_k[i, :]);
  Z-check i neighbours 0..2 = data_left  nonzero(B_k[:, i]),  3..5 = data_right nonzero(A_k[:, i]).
  Qubit order (lin_order): Xcheck 0..n2-1, data_left n2.., data_right 2n2.., Zcheck 3n2..
Cycle (8 rounds; sX = ['idle',1,4,3,5,0,2], sZ = [3,5,0,1,2,4,'idle']):
  round 0  : PrepX on every X check; CNOT(data -> Zcheck) for slot sZ[0]; IDLE on data not touched
  round 1-5: CNOT(Xcheck -> data) for sX[t], then CNOT(data -> Zcheck) for sZ[t]
  round 6  : MeasZ on every Z check; CNOT(Xcheck -> data) for sX[6]; IDLE on data not touched
  round 7  : IDLE on every data qubit; MeasX on every X check; PrepZ on every Z check
Faults (only in the first R cycles; the circuit is cycle^R + cycle + cycle):
  X-type (Z-check syndrome, logical lz): MeasZ -> X BEFORE; PrepZ -> X after; IDLE -> X after (p*2/3);
     CNOT -> X on control, X on target, XX (each p*4/15), after.
  Z-type (X-check syndrome, logical lx): MeasX -> Z BEFORE; PrepX -> Z after; IDLE -> Z after; CNOT -> Z control,
     Z target, ZZ after.
Simulator (simulate_circuitX / Z): one error bit per qubit.  X: CNOT copies control -> target, PrepZ resets, MeasZ
  records (no reset); PrepX is NOT handled (an X on an X-check ancilla persists).  Z: CNOT copies target -> control,
  PrepX resets, MeasX records; PrepZ NOT handled.  ibm_faithful=False resets on every preparation instead.
Detectors: syndrome history per check (one bit per cycle, R+2 cycles); first cycle raw, then XOR with the previous
  cycle of the same check.  Logical: lz (lx) @ final data frame.  Columns: faults merged by (detectors, logicals).

Weight of a fault set = number of merged columns (one column = one single-fault class), as in decoder_setup.py and
in our stim DEMs.  "basis Z" below = Z-basis memory = X-type faults (IBM circuitsX); "basis X" = Z-type faults.
"""
from __future__ import annotations

import numpy as np

CODES = {
    # name: (l, m, (a1, a2, a3), (b1, b2, b3), n, k, d)   arXiv:2308.07915 Table 3 / decoder_setup.py
    "gross": (12, 6, (3, 1, 2), (3, 1, 2), 144, 12, 12),
    "bb108": (9, 6, (3, 1, 2), (3, 1, 2), 108, 8, 10),
}
SX = ["idle", 1, 4, 3, 5, 0, 2]
SZ = [3, 5, 0, 1, 2, 4, "idle"]


# ------------------------------------------------------------------------------------------------ GF(2)
def rref(M):
    M = (np.array(M, dtype=np.uint8) % 2).copy()
    piv, r = [], 0
    for c in range(M.shape[1]):
        if r == M.shape[0]:
            break
        nz = np.nonzero(M[r:, c])[0]
        if not len(nz):
            continue
        p = r + nz[0]
        M[[r, p]] = M[[p, r]]
        o = np.nonzero(M[:, c])[0]
        o = o[o != r]
        M[o] ^= M[r]
        piv.append(c)
        r += 1
    return M[:r], piv


def rank(M):
    return len(rref(M)[1])


def nullspace(M):
    R, piv = rref(M)
    n = M.shape[1]
    free = [c for c in range(n) if c not in set(piv)]
    B = np.zeros((len(free), n), dtype=np.uint8)
    for t, f in enumerate(free):
        B[t, f] = 1
        for i, pc in enumerate(piv):
            if R[i, f]:
                B[t, pc] = 1
    return B


def logicals(H_same, H_other):
    """k independent logicals in ker(H_other) modulo rowspace(H_same)."""
    cur = np.array(H_same, dtype=np.uint8)
    r0 = rank(cur)
    out = []
    for v in nullspace(H_other):
        t = np.vstack([cur, v[None]])
        if rank(t) > r0 + len(out):
            out.append(v)
            cur = t
    return np.array(out, dtype=np.uint8)


# ------------------------------------------------------------------------------------------------ code
class Code:
    def __init__(self, name):
        l, m, a, b, n, k, d = CODES[name]
        self.name, self.l, self.m, self.n_exp, self.k_exp, self.d_pub = name, l, m, n, k, d
        Il, Im = np.eye(l, dtype=np.uint8), np.eye(m, dtype=np.uint8)
        x = lambda e: np.kron(np.roll(Il, e, axis=1), Im)
        y = lambda e: np.kron(Il, np.roll(Im, e, axis=1))
        self.Ak = [x(a[0]), y(a[1]), y(a[2])]
        self.Bk = [y(b[0]), x(b[1]), x(b[2])]
        A = sum(self.Ak) % 2
        B = sum(self.Bk) % 2
        self.n2 = l * m
        self.n = 2 * self.n2
        self.hx = np.hstack([A, B]).astype(np.uint8)
        self.hz = np.hstack([B.T, A.T]).astype(np.uint8)
        assert not ((self.hx @ self.hz.T) % 2).any()
        self.k = self.n - rank(self.hx) - rank(self.hz)
        self.lz = logicals(self.hz, self.hx)      # Z logicals: commute with hx
        self.lx = logicals(self.hx, self.hz)
        assert self.lz.shape[0] == self.k == self.lx.shape[0]
        # qubit ids (lin_order)
        n2 = self.n2
        self.Xq = list(range(0, n2))
        self.Lq = list(range(n2, 2 * n2))
        self.Rq = list(range(2 * n2, 3 * n2))
        self.Zq = list(range(3 * n2, 4 * n2))
        self.Q = 4 * n2

    def xnb(self, i, s):
        """data qubit id of neighbour s of X-check i"""
        if s < 3:
            return self.Lq[int(np.nonzero(self.Ak[s][i, :])[0][0])]
        return self.Rq[int(np.nonzero(self.Bk[s - 3][i, :])[0][0])]

    def znb(self, i, s):
        if s < 3:
            return self.Lq[int(np.nonzero(self.Bk[s][:, i])[0][0])]
        return self.Rq[int(np.nonzero(self.Ak[s - 3][:, i])[0][0])]

    def translation(self, s, t):
        """qubit permutation of x^s y^t (index m*a + b in every block)"""
        l, m, n2 = self.l, self.m, self.n2
        g = np.array([((a + s) % l) * m + (b + t) % m for a in range(l) for b in range(m)])
        return np.concatenate([g + off for off in (0, n2, 2 * n2, 3 * n2)])


# ------------------------------------------------------------------------------------------------ circuit
def cycle(code):
    """One syndrome cycle as decoder_setup.py builds it: list of rounds, each a list of gates in IBM order.
    Gates: ('PrepX', q) ('PrepZ', q) ('MeasX', q) ('MeasZ', q) ('IDLE', q) ('CNOT', c, t)."""
    rounds = []
    data = code.Lq + code.Rq
    # round 0
    g = [("PrepX", q) for q in code.Xq]
    used = set()
    for i, q in enumerate(code.Zq):
        d = code.znb(i, SZ[0]); g.append(("CNOT", d, q)); used.add(d)
    g += [("IDLE", d) for d in data if d not in used]
    rounds.append(g)
    for t in range(1, 6):
        g = []
        for i, q in enumerate(code.Xq):
            g.append(("CNOT", q, code.xnb(i, SX[t])))
        for i, q in enumerate(code.Zq):
            g.append(("CNOT", code.znb(i, SZ[t]), q))
        rounds.append(g)
    g = [("MeasZ", q) for q in code.Zq]
    used = set()
    for i, q in enumerate(code.Xq):
        d = code.xnb(i, SX[6]); g.append(("CNOT", q, d)); used.add(d)
    g += [("IDLE", d) for d in data if d not in used]
    rounds.append(g)
    g = [("IDLE", d) for d in data] + [("MeasX", q) for q in code.Xq] + [("PrepZ", q) for q in code.Zq]
    rounds.append(g)
    # parallelism: every qubit at most once per round (except IDLE, which never coincides with a gate)
    for r in rounds:
        qs = [q for gt in r for q in gt[1:]]
        assert len(qs) == len(set(qs)), "qubit used twice in a round"
    return rounds


def faults_for(gate, typ):
    """(before?, list of fault qubit tuples) for one gate, decoder_setup.py circuitsX (typ 'X') / circuitsZ ('Z')."""
    k = gate[0]
    meas, prep = ("MeasZ", "PrepZ") if typ == "X" else ("MeasX", "PrepX")
    if k == meas:
        return True, [(gate[1],)]
    if k == prep or k == "IDLE":
        return False, [(gate[1],)]
    if k == "CNOT":
        return False, [(gate[1],), (gate[2],), (gate[1], gate[2])]
    return False, []


def build_dem(code, typ, R, ibm_faithful=True, return_raw=False):
    """Single-fault columns of the IBM model.  typ 'X' = X-type faults (Z-basis memory), 'Z' = Z-type faults.
    Returns dict with D (list of detector tuples per merged column), L (list of logical tuples), plus meta."""
    cyc = cycle(code)
    ops = []                       # flattened (cycle, round, gate)
    for c in range(R + 2):
        for r, g in enumerate(cyc):
            for gt in g:
                ops.append((c, r, gt))
    # fault list
    fq, fpos, fbefore, fdesc = [], [], [], []
    for oi, (c, r, gt) in enumerate(ops):
        if c >= R:
            continue
        before, fl = faults_for(gt, typ)
        for qs in fl:
            fq.append(qs); fpos.append(oi); fbefore.append(before); fdesc.append((c, r, gt, qs))
    F = len(fq)
    inj_before, inj_after = {}, {}
    for f in range(F):
        (inj_before if fbefore[f] else inj_after).setdefault(fpos[f], []).append(f)
    state = np.zeros((code.Q, F), dtype=np.uint8)
    meas_rec = {}                  # (check qubit, cycle) -> row of bits
    meas_kind = "MeasZ" if typ == "X" else "MeasX"
    reset_kind = {"PrepZ"} if typ == "X" else {"PrepX"}
    if not ibm_faithful:
        reset_kind = {"PrepX", "PrepZ"}

    def inject(lst):
        for f in lst:
            for q in fq[f]:
                state[q, f] ^= 1
    for oi, (c, r, gt) in enumerate(ops):
        if oi in inj_before:
            inject(inj_before[oi])
        k = gt[0]
        if k == "CNOT":
            if typ == "X":
                state[gt[2]] ^= state[gt[1]]
            else:
                state[gt[1]] ^= state[gt[2]]
        elif k in reset_kind:
            state[gt[1]] = 0
        elif k == meas_kind:
            meas_rec[(gt[1], c)] = state[gt[1]].copy()
        if oi in inj_after:
            inject(inj_after[oi])
    checks = code.Zq if typ == "X" else code.Xq
    ndet = len(checks) * (R + 2)
    det = np.zeros((ndet, F), dtype=np.uint8)
    for c in range(R + 2):
        for i, q in enumerate(checks):
            v = meas_rec[(q, c)].copy()
            if c:
                v ^= meas_rec[(q, c - 1)]
            det[c * len(checks) + i] = v
    data = code.Lq + code.Rq
    Lop = code.lz if typ == "X" else code.lx
    final = state[data]                                          # n x F
    logi = (Lop.astype(np.int64) @ final.astype(np.int64)) % 2  # k x F
    if return_raw:
        return dict(det=det, logi=logi, final=final, fdesc=fdesc, ops=ops)
    return merge(det, logi, final, fdesc, code, R, typ)


def merge(det, logi, final, fdesc, code, R, typ):
    key, D, L, members, finals = {}, [], [], [], []
    for f in range(det.shape[1]):
        d = tuple(np.nonzero(det[:, f])[0].tolist())
        lv = tuple(np.nonzero(logi[:, f])[0].tolist())
        if not d and not lv:
            continue
        assert d, ("undetectable single fault flips a logical", fdesc[f])
        kk = (d, lv)
        if kk not in key:
            key[kk] = len(D); D.append(d); L.append(lv); members.append([]); finals.append(final[:, f].copy())
        members[key[kk]].append(f)
    checks = code.Zq if typ == "X" else code.Xq
    return dict(D=D, L=L, members=members, final=np.array(finals, dtype=np.uint8).T if finals else None,
                ndet=det.shape[0], nchk=len(checks), R=R, typ=typ, nfaults=det.shape[1], k=logi.shape[0])


def det_coords(code, typ, R):
    """detector index -> (check index, cycle)"""
    nc = code.n2
    return [(i % nc, i // nc) for i in range((R + 2) * nc)]


# ------------------------------------------------------------------------------------------------ stim version
def stim_circuit(code, typ, R, p=1e-3):
    """Independent second implementation: the same gate list as a stim circuit (stim's own frame simulation, which
    resets on every preparation), X_ERROR / Z_ERROR and CORRELATED_ERROR for the two-qubit fault."""
    import stim
    cyc = cycle(code)
    c = stim.Circuit()
    data = code.Lq + code.Rq
    c.append("R" if typ == "X" else "RX", data)
    c.append("R", code.Zq)                 # Z checks implicitly |0> before the first cycle (state zeros)
    c.append("RX", code.Xq)
    E = "X" if typ == "X" else "Z"
    nm = 0
    rec = {}
    for cc in range(R + 2):
        noisy = cc < R
        for r, g in enumerate(cyc):
            for gt in g:
                k = gt[0]
                before, fl = faults_for(gt, typ) if noisy else (False, [])
                if before:
                    for qs in fl:
                        c.append(E + "_ERROR", [qs[0]], p)
                if k == "CNOT":
                    c.append("CX", [gt[1], gt[2]])
                elif k == "PrepX":
                    c.append("RX", [gt[1]])
                elif k == "PrepZ":
                    c.append("R", [gt[1]])
                elif k == "MeasZ":
                    c.append("M", [gt[1]]); rec[(gt[1], cc)] = nm; nm += 1
                elif k == "MeasX":
                    c.append("MX", [gt[1]]); rec[(gt[1], cc)] = nm; nm += 1
                if not before:
                    for qs in fl:
                        if len(qs) == 1:
                            c.append(E + "_ERROR", [qs[0]], p)
                        else:
                            c.append("CORRELATED_ERROR", [stim.target_x(qs[0]) if E == "X" else stim.target_z(qs[0]),
                                                          stim.target_x(qs[1]) if E == "X" else stim.target_z(qs[1])], p)
    checks = code.Zq if typ == "X" else code.Xq
    c.append("M" if typ == "X" else "MX", data)
    drec = {q: nm + j for j, q in enumerate(data)}
    nm += len(data)
    for cc in range(R + 2):
        for i, q in enumerate(checks):
            t = [stim.target_rec(rec[(q, cc)] - nm)]
            if cc:
                t.append(stim.target_rec(rec[(q, cc - 1)] - nm))
            c.append("DETECTOR", t, [i, cc])
    Lop = code.lz if typ == "X" else code.lx
    for kk, row in enumerate(Lop):
        c.append("OBSERVABLE_INCLUDE", [stim.target_rec(drec[data[j]] - nm) for j in np.nonzero(row)[0]], kk)
    return c


def stim_columns(circ):
    dem = circ.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    out = set()
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        d, o = set(), set()
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                d ^= {t.val}
            elif t.is_logical_observable_id():
                o ^= {t.val}
        out.add((tuple(sorted(d)), tuple(sorted(o))))
    return out
