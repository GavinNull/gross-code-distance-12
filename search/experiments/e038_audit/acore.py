"""E-038 audit (fresh auditor, 2026-10-26): own core.  Imports nothing from search/experiments/e038 or evaluators/.

Code: Kunlun [[18,4,4]] (arXiv 2505.09684 SI Sec. I.1): l = m = 3, x = S (x) I, y = I (x) S, A = x + 1 + y^2,
B = y + 1 + x^2, H_X = [A | B], H_Z = [B^T | A^T]; measured checks X{0,1,3,4,5,6,7}, Z{0,1,2,5,6,7,8} (X2, X8, Z3, Z4
dropped).  Data 0..8 = L block, 9..17 = R block.  Built here from scratch; cross-checked against e036_audit.core.

Schedules are read from the evaluator json (qec-schedule/v1): every row is identified by its support.
Circuits: my own stim memory circuit, SD6 (DEPOLARIZE2(p) after each CX, DEPOLARIZE1(p) on every qubit idle in a
layer, DEPOLARIZE1(p) after H, reset flip, measurement flip, data init / readout flip), both detector types,
reset or no-reset ancillas.  Exact min weight <= wmax by my own meet-in-the-middle over the DEM mechanisms.
"""
from __future__ import annotations

import itertools
import json
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np

MEASURED = {"X": [0, 1, 3, 4, 5, 6, 7], "Z": [0, 1, 2, 5, 6, 7, 8]}
FULL = {"X": list(range(9)), "Z": list(range(9))}


def _cyc(n):
    S = np.zeros((n, n), np.uint8)
    for i in range(n):
        S[i, (i + 1) % n] = 1
    return S


_x = np.kron(_cyc(3), np.eye(3, dtype=np.uint8))
_y = np.kron(np.eye(3, dtype=np.uint8), _cyc(3))
_I = np.eye(9, dtype=np.uint8)
A_ = (_x + _I + _y @ _y) % 2
B_ = (_y + _I + _x @ _x) % 2
HXF = np.hstack([A_, B_]) % 2
HZF = np.hstack([B_.T, A_.T]) % 2


def check_list(meas=MEASURED):
    return [("X", r) for r in meas["X"]] + [("Z", r) for r in meas["Z"]]


def supp(k):
    H = HXF if k[0] == "X" else HZF
    return [int(q) for q in np.nonzero(H[k[1]])[0]]


def gf2_rank(M):
    M = (np.array(M, np.uint8) % 2).copy()
    r = 0
    for c in range(M.shape[1]):
        piv = [i for i in range(r, M.shape[0]) if M[i, c]]
        if not piv:
            continue
        M[[r, piv[0]]] = M[[piv[0], r]]
        for i in range(M.shape[0]):
            if i != r and M[i, c]:
                M[i] ^= M[r]
        r += 1
    return r


def logicals(basis, meas=MEASURED):
    """Z memory: Z-type logical representatives (in ker H_X, independent mod rowspace H_Z); X memory: X-type."""
    HX = HXF[meas["X"]]
    HZ = HZF[meas["Z"]]
    Hc, Hs = (HX, HZ) if basis == "Z" else (HZ, HX)
    out = []
    base = Hs.copy()
    rb = gf2_rank(base)
    for v in itertools.product([0, 1], repeat=18):
        pass  # (not used; brute-force below via nullspace basis)
        break
    # nullspace of Hc
    n = 18
    M = Hc.copy() % 2
    # gaussian elimination for nullspace
    M = M.astype(np.uint8)
    piv = []
    R = M.copy()
    r = 0
    for c in range(n):
        p = [i for i in range(r, R.shape[0]) if R[i, c]]
        if not p:
            continue
        R[[r, p[0]]] = R[[p[0], r]]
        for i in range(R.shape[0]):
            if i != r and R[i, c]:
                R[i] ^= R[r]
        piv.append(c)
        r += 1
    free = [c for c in range(n) if c not in piv]
    ker = []
    for f in free:
        v = np.zeros(n, np.uint8)
        v[f] = 1
        for i, pc in enumerate(piv):
            if R[i, f]:
                v[pc] = 1
        ker.append(v)
    for v in ker:
        nb = np.vstack([base, v])
        if gf2_rank(nb) > rb:
            out.append(v)
            base = nb
            rb += 1
    return np.array(out, np.uint8)


# ----------------------------------------------------------------------------- schedule json
def parse_spec(path, meas=MEASURED):
    d = json.load(open(path)) if isinstance(path, str) else path
    P = d["period"]
    ks = check_list(meas)
    sch = {}
    for kind, key in (("X", "x_checks"), ("Z", "z_checks")):
        for row in d[key]:
            qs = sorted(q for q, _ in row["cnots"])
            m = [k for k in ks if k[0] == kind and sorted(supp(k)) == qs]
            assert len(m) == 1, ("row not a measured check support", kind, qs)
            assert m[0] not in sch, ("duplicate check", m[0])
            assert len(row["cnots"]) == 6
            sch[m[0]] = {"prep": row["prep"], "meas": row["meas"], "cx": {q: t for q, t in row["cnots"]}}
    assert set(sch) == set(ks), "missing checks"
    return P, sch


def check_legal(P, sch):
    """structural legality of a non-wrapping single-ancilla round: CNOT layers strictly inside (prep, meas) of each
    check, < P, one gate per qubit per layer, each check's 6 CNOTs on its own support (by construction of parse)."""
    probs = []
    busy = {}
    for k, r in sch.items():
        lay = list(r["cx"].values())
        if len(set(lay)) != 6:
            probs.append(f"{k}: two CNOTs in one layer")
        if not all(r["prep"] < t < r["meas"] for t in lay):
            probs.append(f"{k}: CNOT outside window")
        if not (0 <= r["prep"] and r["meas"] <= P - 1):
            probs.append(f"{k}: window wraps")
        for q, t in r["cx"].items():
            if (q, t) in busy:
                probs.append(f"data {q} layer {t}: {busy[(q, t)]} and {k}")
            busy[(q, t)] = k
    return probs


def parity_condition(sch):
    bad = []
    for kx in sch:
        if kx[0] != "X":
            continue
        for kz in sch:
            if kz[0] != "Z":
                continue
            sh = set(sch[kx]["cx"]) & set(sch[kz]["cx"])
            if sum(sch[kx]["cx"][q] < sch[kz]["cx"][q] for q in sh) % 2:
                bad.append((kx, kz))
    return bad


# ----------------------------------------------------------------------------- stim circuit
def build(P, sch, basis, R, p=1e-3, reset=True, all_dets=True, inject=None, meas=MEASURED):
    """non-wrapping memory circuit (all rounds identical, round j occupies layers jP .. jP+P-1).
    inject: optional (round, qubit, pauli) -> deterministic Pauli on a data qubit right before round `round`."""
    import stim
    ks = check_list(meas)
    nd = 18
    anc = {k: nd + i for i, k in enumerate(ks)}
    allq = list(range(nd + len(ks)))
    c = stim.Circuit()
    c.append("R" if basis == "Z" else "RX", list(range(nd)))
    if p:
        c.append("X_ERROR" if basis == "Z" else "Z_ERROR", list(range(nd)), p)
    if not reset:
        c.append("R", [anc[k] for k in ks])
        if p:
            c.append("X_ERROR", [anc[k] for k in ks], p)
    c.append("TICK")
    nm = 0
    rec = {}

    def idle(used):
        rest = [q for q in allq if q not in used]
        if rest and p:
            c.append("DEPOLARIZE1", rest, p)

    for j in range(R):
        if inject is not None and inject[0] == j:
            c.append(inject[2] + "_ERROR", [inject[1]], 1.0)
        for t in range(P):
            used = set()
            # preparation
            for k in ks:
                if sch[k]["prep"] == t:
                    a = anc[k]
                    if reset:
                        c.append("RX" if k[0] == "X" else "R", [a])
                        if p:
                            c.append("Z_ERROR" if k[0] == "X" else "X_ERROR", [a], p)
                        used.add(a)
                    elif k[0] == "X":
                        c.append("H", [a])
                        if p:
                            c.append("DEPOLARIZE1", [a], p)
                        used.add(a)
            pairs = []
            for k in ks:
                for q, tt in sch[k]["cx"].items():
                    if tt == t:
                        a = anc[k]
                        assert a not in used and q not in used
                        pairs += [a, q] if k[0] == "X" else [q, a]
                        used |= {a, q}
            if pairs:
                c.append("CX", pairs)
                if p:
                    c.append("DEPOLARIZE2", pairs, p)
            mk = [k for k in ks if sch[k]["meas"] == t]
            if mk and not reset:
                xs = [anc[k] for k in mk if k[0] == "X"]
                if xs:
                    c.append("H", xs)
                    if p:
                        c.append("DEPOLARIZE1", xs, p)
                    idle(set(xs) | used)
                    c.append("TICK")
            for k in mk:
                a = anc[k]
                assert a not in used or not reset
                if reset:
                    c.append("MX" if k[0] == "X" else "M", [a], p)
                else:
                    c.append("M", [a], p)
                used.add(a)
                rec[(k, j)] = nm
                nm += 1
            idle(used)
            c.append("TICK")
        for k in ks:
            mem = k[0] == basis
            if not mem and (j == 0) and reset:
                continue
            if not mem and not all_dets:
                continue
            if reset:
                lst = [rec[(k, j)]] + ([rec[(k, j - 1)]] if j else [])
            else:
                if mem:
                    lst = [rec[(k, j)]] + ([rec[(k, j - 2)]] if j >= 2 else [])
                else:
                    if j == 0:
                        continue
                    lst = [rec[(k, j)]] + ([rec[(k, j - 2)]] if j >= 2 else [])
            c.append("DETECTOR", [stim.target_rec(x - nm) for x in lst])
    c.append("M" if basis == "Z" else "MX", list(range(nd)), p)
    dm = {q: nm + q for q in range(nd)}
    nm += nd
    for k in ks:
        if k[0] != basis:
            continue
        lst = [dm[q] for q in supp(k)] + [rec[(k, R - 1)]]
        if not reset and R >= 2:
            lst.append(rec[(k, R - 2)])
        c.append("DETECTOR", [stim.target_rec(x - nm) for x in lst])
    for i, v in enumerate(logicals(basis, meas)):
        c.append("OBSERVABLE_INCLUDE", [stim.target_rec(dm[q] - nm) for q in np.nonzero(v)[0]], i)
    return c


def mechs(circ):
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


def min_weight(ms, wmax=3):
    """exact: smallest w <= wmax such that some w mechanisms XOR to (0, nonzero obs); None if none."""
    single = {}
    for d, o in ms:
        single.setdefault(d, set()).add(o)
    if any(o for o in single.get(0, ())):
        return 1
    if wmax < 2:
        return None
    for d, os_ in single.items():
        if len(os_) >= 2:
            return 2
    if wmax < 3:
        return None
    n = len(ms)
    for i in range(n):
        di, oi = ms[i]
        for j in range(i + 1, n):
            dj, oj = ms[j]
            s = single.get(di ^ dj)
            if s is None:
                continue
            oo = oi ^ oj
            if any(o != oo for o in s):
                return 3
    if wmax < 4:
        return None
    pairs = {}
    for i in range(n):
        di, oi = ms[i]
        for j in range(i + 1, n):
            dj, oj = ms[j]
            key = di ^ dj
            st = pairs.setdefault(key, set())
            st.add(oi ^ oj)
            if len(st) >= 2:
                return 4
    return None
