"""E-037 audit: independent DEM construction.  auditor (written without importing e037 code).

Sources (same naming as E-037 so instances can be compared):
  ibm:CODE:TYP:R   decoder_setup.py fault model, own bit-parallel frame simulator, TYP X = X faults (Z-basis memory)
  ibmreset:...     same, but every preparation resets the frame (textbook Pauli frame)
  ibmstim:...      same gate list as a stim circuit, stim's DEM
  sd6:CODE:BASIS:R evaluator public entry (memory_circuit of baselines ibm_depth8, add_noise sd6), stim DEM

Returns dict(D=list of detector tuples, L=list of observable tuples, ndet, nobs, coords=[(check, cycle)], l, m,
Lmat=observable matrix used, frame info).  Columns merged by (D, L); all-zero columns dropped (they can never be part of
a minimum-weight undetectable logical; decoder_setup.py keeps them as zero columns, which changes nothing).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
for p in (str(ROOT), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

PARAMS = {"gross": (12, 6), "bb108": (9, 6)}   # A = x^3 + y + y^2, B = y^3 + x + x^2 (arXiv:2308.07915 Table 3)
SX = [None, 1, 4, 3, 5, 0, 2]
SZ = [3, 5, 0, 1, 2, 4, None]


def gf2_rank(M):
    M = np.array(M, dtype=np.uint8) % 2
    r = 0
    rows, cols = M.shape
    for c in range(cols):
        p = None
        for i in range(r, rows):
            if M[i, c]:
                p = i
                break
        if p is None:
            continue
        M[[r, p]] = M[[p, r]]
        for i in range(rows):
            if i != r and M[i, c]:
                M[i] ^= M[r]
        r += 1
        if r == rows:
            break
    return r


def gf2_null(M):
    M = np.array(M, dtype=np.uint8) % 2
    rows, cols = M.shape
    piv = []
    r = 0
    for c in range(cols):
        p = next((i for i in range(r, rows) if M[i, c]), None)
        if p is None:
            continue
        M[[r, p]] = M[[p, r]]
        for i in range(rows):
            if i != r and M[i, c]:
                M[i] ^= M[r]
        piv.append(c)
        r += 1
    free = [c for c in range(cols) if c not in piv]
    out = []
    for f in free:
        v = np.zeros(cols, dtype=np.uint8)
        v[f] = 1
        for i, pc in enumerate(piv):
            if M[i, f]:
                v[pc] = 1
        out.append(v)
    return np.array(out)


class BB:
    def __init__(self, name):
        l, m = PARAMS[name]
        self.l, self.m, self.n2 = l, m, l * m
        S = lambda k, e: np.roll(np.eye(k, dtype=np.uint8), e, axis=1)
        X = lambda e: np.kron(S(l, e), np.eye(m, dtype=np.uint8))
        Y = lambda e: np.kron(np.eye(l, dtype=np.uint8), S(m, e))
        self.A = [X(3), Y(1), Y(2)]
        self.B = [Y(3), X(1), X(2)]
        A = (self.A[0] + self.A[1] + self.A[2]) % 2
        B = (self.B[0] + self.B[1] + self.B[2]) % 2
        self.hx = np.hstack([A, B])
        self.hz = np.hstack([B.T, A.T])
        assert not (self.hx.astype(int) @ self.hz.T.astype(int) % 2).any()
        n = 2 * self.n2
        self.k = n - gf2_rank(self.hx) - gf2_rank(self.hz)
        # logical Z: ker hx not in rowspace hz  (independent greedy selection)
        self.lz = self._logicals(self.hz, self.hx)
        self.lx = self._logicals(self.hx, self.hz)
        # qubit ids: Xcheck 0.., data_left n2.., data_right 2n2.., Zcheck 3n2..
        n2 = self.n2
        self.xc = list(range(n2)); self.dl = list(range(n2, 2 * n2)); self.dr = list(range(2 * n2, 3 * n2))
        self.zc = list(range(3 * n2, 4 * n2)); self.Q = 4 * n2

    def _logicals(self, Hs, Ho):
        base = gf2_rank(Hs)
        cur = Hs.copy()
        out = []
        for v in gf2_null(Ho):
            t = np.vstack([cur, v])
            if gf2_rank(t) == base + len(out) + 1:
                out.append(v); cur = t
            if len(out) == self.k:
                break
        assert len(out) == self.k
        return np.array(out, dtype=np.uint8)

    def nbX(self, i, s):           # X-check i, slot s
        return self.dl[int(np.flatnonzero(self.A[s][i])[0])] if s < 3 else self.dr[int(np.flatnonzero(self.B[s - 3][i])[0])]

    def nbZ(self, i, s):
        return self.dl[int(np.flatnonzero(self.B[s][:, i])[0])] if s < 3 else self.dr[int(np.flatnonzero(self.A[s - 3][:, i])[0])]

    def cycle(self, with_round=False):
        cyc = []
        bounds = []
        r0 = [("PrepX", q) for q in self.xc]
        busy = set()
        for i, q in enumerate(self.zc):
            d = self.nbZ(i, SZ[0]); r0.append(("CNOT", d, q)); busy.add(d)
        r0 += [("IDLE", d) for d in self.dl + self.dr if d not in busy]
        cyc += r0
        bounds.append(len(cyc))
        for t in range(1, 6):
            for i, q in enumerate(self.xc):
                cyc.append(("CNOT", q, self.nbX(i, SX[t])))
            for i, q in enumerate(self.zc):
                cyc.append(("CNOT", self.nbZ(i, SZ[t]), q))
            bounds.append(len(cyc))
        r6 = [("MeasZ", q) for q in self.zc]
        busy = set()
        for i, q in enumerate(self.xc):
            d = self.nbX(i, SX[6]); r6.append(("CNOT", q, d)); busy.add(d)
        r6 += [("IDLE", d) for d in self.dl + self.dr if d not in busy]
        cyc += r6
        bounds.append(len(cyc))
        cyc += [("IDLE", d) for d in self.dl + self.dr] + [("MeasX", q) for q in self.xc] + [("PrepZ", q) for q in self.zc]
        bounds.append(len(cyc))
        if with_round:
            import bisect
            return [(bisect.bisect_right(bounds, i), g) for i, g in enumerate(cyc)]
        return cyc


def fault_sites(gate, typ):
    """decoder_setup.py circuitsX (typ X) / circuitsZ (typ Z): list of (before, qubits)"""
    meas, prep = ("MeasZ", "PrepZ") if typ == "X" else ("MeasX", "PrepX")
    g = gate[0]
    if g == meas:
        return [(True, (gate[1],))]
    if g in (prep, "IDLE"):
        return [(False, (gate[1],))]
    if g == "CNOT":
        return [(False, (gate[1],)), (False, (gate[2],)), (False, (gate[1], gate[2]))]
    return []


def ibm_columns(name, typ, R, reset_all=False):
    code = BB(name)
    cyc = code.cycle()
    ops = [(c, g) for c in range(R + 2) for g in cyc]
    # enumerate faults
    sites = []
    for oi, (c, g) in enumerate(ops):
        if c < R:
            for before, qs in fault_sites(g, typ):
                sites.append((oi, before, qs))
    F = len(sites)
    W = (F + 63) // 64
    st = np.zeros((code.Q, W), dtype=np.uint64)
    before_at, after_at = {}, {}
    for f, (oi, b, qs) in enumerate(sites):
        (before_at if b else after_at).setdefault(oi, []).append((f, qs))

    def inj(lst):
        for f, qs in lst:
            for q in qs:
                st[q, f >> 6] ^= np.uint64(1) << np.uint64(f & 63)
    measg = "MeasZ" if typ == "X" else "MeasX"
    resets = {"PrepX", "PrepZ"} if reset_all else ({"PrepZ"} if typ == "X" else {"PrepX"})
    rec = {}
    for oi, (c, g) in enumerate(ops):
        if oi in before_at:
            inj(before_at[oi])
        k = g[0]
        if k == "CNOT":
            if typ == "X":
                st[g[2]] ^= st[g[1]]          # X: control -> target
            else:
                st[g[1]] ^= st[g[2]]          # Z: target -> control
        elif k in resets:
            st[g[1]] = 0
        elif k == measg:
            rec[(g[1], c)] = st[g[1]].copy()
        if oi in after_at:
            inj(after_at[oi])
    chk = code.zc if typ == "X" else code.xc
    nd = len(chk) * (R + 2)
    det = np.zeros((nd, W), dtype=np.uint64)
    for c in range(R + 2):
        for i, q in enumerate(chk):
            v = rec[(q, c)].copy()
            if c:
                v ^= rec[(q, c - 1)]
            det[c * len(chk) + i] = v
    data = code.dl + code.dr
    Lop = code.lz if typ == "X" else code.lx

    def unpack(rows):
        b = np.unpackbits(rows.view(np.uint8), axis=1, bitorder="little")[:, :F]
        return b
    D = unpack(det)
    fin = unpack(st[data])
    Lm = (Lop.astype(np.int64) @ fin.astype(np.int64)) % 2
    cols = {}
    for f in range(F):
        d = tuple(np.flatnonzero(D[:, f]).tolist())
        o = tuple(np.flatnonzero(Lm[:, f]).tolist())
        if d or o:
            cols.setdefault((d, o), []).append(sites[f])
    keys = sorted(cols)
    return dict(D=[k[0] for k in keys], L=[k[1] for k in keys], ndet=nd, nobs=code.k,
                coords=[(i % code.n2, i // code.n2) for i in range(nd)], l=code.l, m=code.m,
                members=[cols[k] for k in keys], nfaults=F, code=code, ops=ops)


def ibm_stim(name, typ, R, p=1e-3):
    import stim
    code = BB(name)
    cyc = code.cycle()
    c = stim.Circuit()
    data = code.dl + code.dr
    c.append("R" if typ == "X" else "RX", data)
    c.append("R", code.zc); c.append("RX", code.xc)
    E = typ
    tgt = stim.target_x if E == "X" else stim.target_z
    nm, rec = 0, {}
    for cc in range(R + 2):
        for g in cyc:
            fs = fault_sites(g, typ) if cc < R else []
            for b, qs in fs:
                if b:
                    c.append(E + "_ERROR", list(qs), p)
            k = g[0]
            if k == "CNOT":
                c.append("CX", [g[1], g[2]])
            elif k == "PrepX":
                c.append("RX", [g[1]])
            elif k == "PrepZ":
                c.append("R", [g[1]])
            elif k in ("MeasZ", "MeasX"):
                c.append("M" if k == "MeasZ" else "MX", [g[1]]); rec[(g[1], cc)] = nm; nm += 1
            for b, qs in fs:
                if not b:
                    if len(qs) == 1:
                        c.append(E + "_ERROR", list(qs), p)
                    else:
                        c.append("CORRELATED_ERROR", [tgt(qs[0]), tgt(qs[1])], p)
    chk = code.zc if typ == "X" else code.xc
    c.append("M" if typ == "X" else "MX", data)
    drec = {q: nm + j for j, q in enumerate(data)}
    nm += len(data)
    for cc in range(R + 2):
        for i, q in enumerate(chk):
            t = [stim.target_rec(rec[(q, cc)] - nm)]
            if cc:
                t.append(stim.target_rec(rec[(q, cc - 1)] - nm))
            c.append("DETECTOR", t, [i, cc])
    Lop = code.lz if typ == "X" else code.lx
    for kk, row in enumerate(Lop):
        c.append("OBSERVABLE_INCLUDE", [stim.target_rec(drec[data[j]] - nm) for j in np.flatnonzero(row)], kk)
    return dem_columns(c, code.l, code.m, two=True)


def dem_columns(circ, l, m, two=False):
    dem = circ.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    cols = set()
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        d, o = set(), set()
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                d ^= {t.val}
            elif t.is_logical_observable_id():
                o ^= {t.val}
        if d or o:
            cols.add((tuple(sorted(d)), tuple(sorted(o))))
    keys = sorted(cols)
    co = dem.get_detector_coordinates()
    return dict(D=[k[0] for k in keys], L=[k[1] for k in keys], ndet=dem.num_detectors, nobs=dem.num_observables,
                coords=[(int(co[i][0]), int(co[i][1])) for i in range(dem.num_detectors)], l=l, m=m, circuit=circ)


def sd6(name, basis, R, p=1e-3):
    from evaluators import candidate as cand
    from evaluators.noise import add_noise
    from evaluators.tasks import build_code, get_task
    from baselines.bb_code import BBCode
    from baselines.schedule import ibm_depth8
    from schedule_helpers import from_baseline
    task = {"gross": "gross-dcirc", "bb108": "bb108-dcirc"}[name]
    code, _ = build_code(get_task(task), None)
    l, m = PARAMS[name]
    spec = from_baseline(ibm_depth8(BBCode(l, m, ["x^3", "y", "y^2"], ["y^3", "x", "x^2"]))).canonical()
    assert not cand.validate_schedule(spec, code)
    circ = add_noise(cand.memory_circuit(spec, code, basis, R), "sd6", p)
    return dem_columns(circ, l, m)


def load(src):
    kind, name, b, R = src.split(":")
    R = int(R)
    if kind == "ibm":
        return ibm_columns(name, b, R)
    if kind == "ibmreset":
        return ibm_columns(name, b, R, reset_all=True)
    if kind == "ibmstim":
        return ibm_stim(name, b, R)
    if kind == "sd6":
        return sd6(name, b, R)
    raise ValueError(src)


# ---------------------------------------------------------------- logical equivalence modulo detectors
def bitrows(cols_idx_lists, ncols):
    """list of python-int row vectors from per-column index lists (rows indexed by detector / observable)"""
    return cols_idx_lists


def rows_from(D, nrows):
    rows = [0] * nrows
    for j, d in enumerate(D):
        for x in d:
            rows[x] |= 1 << j
    return rows


class Span:
    def __init__(self):
        self.piv = {}

    def red(self, v):
        while v:
            b = v.bit_length() - 1
            if b not in self.piv:
                return v
            v ^= self.piv[b]
        return 0

    def add(self, v):
        v = self.red(v)
        if v:
            self.piv[v.bit_length() - 1] = v
            return True
        return False


def same_logicals_mod_det(Drows, L1rows, L2rows):
    """on ker D:  L1 x = 0  <=>  L2 x = 0   iff  span(D,L1) == span(D,L2)"""
    s = Span()
    for r in Drows:
        s.add(r)
    s1 = Span(); s1.piv = dict(s.piv)
    r1 = sum(s1.add(v) for v in L1rows)
    s2 = Span(); s2.piv = dict(s.piv)
    r2 = sum(s2.add(v) for v in L2rows)
    r12 = r1 + sum(s1.add(v) for v in L2rows)
    return r1 == r2 == r12, (r1, r2, r12)
