"""Extended codes, the colour-preserving translation group, augmented detector error models, the lift test.

Conventions.  A Z-basis memory sees X errors: H = HZ, L = LZ, and the residuals come from the X-check CNOT orders
(an X error on an X-check ancilla after its k-th CNOT spreads to the suffix q_{k+1..6}).  The X basis is symmetric
(H = HX, L = LX, Z-check orders).  A column of the extended code is a nonzero pair (H s, L s) for s a single data
qubit or a proper suffix of a check order; equal pairs are merged.  Column order (used by all data files):
data qubits 0..143 first, then for every check in row order its suffixes of length 5, 4, 3, 2, 1, keeping the first
occurrence of each (H s, L s).
"""
from __future__ import annotations

import json
from collections import defaultdict

import numpy as np
import stim

from .code import Code
from .noise import add_sd6
from .paths import EXT, LOGICALS
from .schedule import Schedule, build_circuits

BASES = ("Z", "X")


def hl(code: Code, basis: str):
    return (code.HZ, code.LZ) if basis == "Z" else (code.HX, code.LX)


def key_of(code: Code, basis: str, support) -> bytes:
    H, L = hl(code, basis)
    v = np.zeros(code.n, np.uint8)
    v[list(support)] = 1
    return ((H @ v) % 2).astype(np.uint8).tobytes() + ((L @ v) % 2).astype(np.uint8).tobytes()


def ext_columns(code: Code, basis: str, spec: Schedule):
    """returns (keys, supports, supkey): keys[j] = column j as bytes (H part then L part), supports[j] = the
    representative support of column j, supkey = {support: key} for every nonzero support (data or residual)."""
    xo, zo = spec.orders()
    ords = xo if basis == "Z" else zo
    sups = [(j,) for j in range(code.n)] + [tuple(sorted(o[k:])) for o in ords for k in range(1, 6)]
    keys, supports, seen, supkey = [], [], set(), {}
    for s in sups:
        k = key_of(code, basis, s)
        if not any(k):
            continue
        supkey[s] = k
        if k not in seen:
            seen.add(k)
            keys.append(k)
            supports.append(s)
    return keys, supports, supkey


def translation(a: int, b: int) -> list[int]:
    """translation by x^a y^b on the 144 data qubits (both blocks)."""
    p = [((i // 6 + a) % 12) * 6 + (i % 6 + b) % 6 for i in range(72)]
    return p + [x + 72 for x in p]


def colour(i: int) -> int:
    return (i // 6 + i % 6) % 3


def order_group(spec: Schedule) -> list[tuple[int, int]]:
    """translations (a, b) with a + b = 0 mod 3 (colour preserving) that map every check order to the order of the
    image check (both check types)."""
    xo, zo = spec.orders()
    G = []
    for a in range(12):
        for b in range(6):
            if (a + b) % 3:
                continue
            pq = translation(a, b)
            ok = True
            for ords in (xo, zo):
                idx = {tuple(o): i for i, o in enumerate(ords)}
                for i, o in enumerate(ords):
                    img = tuple(pq[q] for q in o)
                    j = idx.get(img)
                    if j is None or j != ((i // 6 + a) % 12) * 6 + (i % 6 + b) % 6:
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                G.append((a, b))
    return G


def column_perms(code, basis, spec, keys, supports, supkey, G):
    kidx = {k: j for j, k in enumerate(keys)}
    perms = []
    for a, b in G:
        pq = translation(a, b)
        perms.append([kidx[supkey[tuple(sorted(pq[q] for q in s))]] for s in supports])
    return perms


def orbits(perms, N):
    """orbit classes of columns, in order of their smallest column index."""
    classes, seen = [], set()
    for j in range(N):
        if j in seen:
            continue
        o = sorted({p[j] for p in perms})
        seen |= set(o)
        classes.append(o)
    return classes


# ---------------------------------------------------------------------------------------------------------------
# data files

def load_ext(basis: str) -> dict:
    return json.load(open(EXT / f"extended_code_{basis}_memory.json"))


def ext_keys_from_file(code: Code, basis: str) -> list[bytes]:
    d = load_ext(basis)
    H, L = hl(code, basis)
    out = []
    for c in d["columns"]:
        h = np.zeros(H.shape[0], np.uint8); h[c["H"]] = 1
        lv = np.zeros(L.shape[0], np.uint8); lv[c["L"]] = 1
        assert key_of(code, basis, c["support"]) == h.tobytes() + lv.tobytes(), c
        out.append(h.tobytes() + lv.tobytes())
    return out


def load_w11(basis: str) -> list[list[int]]:
    d = json.load(open(LOGICALS / f"weight11_logicals_{basis}_memory.json"))
    return [e["columns"] for e in d["logicals"]]


# ---------------------------------------------------------------------------------------------------------------
# augmented detector error model

def noisy_circuit(spec: Schedule, code: Code, R: int, basis: str) -> stim.Circuit:
    return add_sd6(build_circuits(spec.canonical(), code, R)[basis]).flattened()


def dem_groups(spec: Schedule, code: Code, R: int, basis: str, with_terms: bool = False):
    """SD6 detector error model of the memory circuit, augmented with one observable per row of H and of L on the
    final data readout.  Returns ({image key: [detector frozenset, ...]}, stats).  Also checks, for every mechanism:
    its per-check detector parity equals the H part of its image (template identity) and its logical effect equals
    the L part (stats telescoping_bad, bad_obs).  with_terms: also return the augmented circuit and, per key, the
    DEM error instructions (parallel to the detector sets), for locating circuit faults."""
    c = noisy_circuit(spec, code, R, basis)
    H, L = hl(code, basis)
    n = code.n
    last = [op for op in c if op.name in ("M", "MX")][-1]
    assert [t.value for t in last.targets_copy()] == list(range(n))
    k0 = c.num_observables
    aug = c.copy()
    for r, row in enumerate(list(H) + list(L)):
        aug.append("OBSERVABLE_INCLUDE", [stim.target_rec(int(q) - n) for q in np.nonzero(row)[0]], k0 + r)
    dem = aug.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    coords = dem.get_detector_coordinates()
    nH = H.shape[0]
    groups, terms = {}, {}
    nz = nt = bad_obs = tele_bad = 0
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        nt += 1
        dets = set()
        hb = np.zeros(nH, np.uint8); lb = np.zeros(L.shape[0], np.uint8); ob = np.zeros(k0, np.uint8)
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                dets ^= {t.val}
            elif t.is_logical_observable_id():
                v = t.val
                if v < k0:
                    ob[v] ^= 1
                elif v < k0 + nH:
                    hb[v - k0] ^= 1
                else:
                    lb[v - k0 - nH] ^= 1
        if not (ob == lb).all():
            bad_obs += 1
        par = np.zeros(nH, np.uint8)
        for d in dets:
            par[int(coords[d][0])] ^= 1
        if not (par == hb).all():
            tele_bad += 1
        if not hb.any() and not lb.any():
            nz += 1
            continue
        groups.setdefault(hb.tobytes() + lb.tobytes(), []).append(frozenset(dets))
        if with_terms:
            terms.setdefault(hb.tobytes() + lb.tobytes(), []).append(inst)
    st = dict(mechanisms=nt, zero_image=nz, bad_obs=bad_obs, telescoping_bad=tele_bad,
                        detectors=c.num_detectors, image_keys=len(groups))
    if with_terms:
        return groups, st, aug, terms
    return groups, st


def lift_model(S_keys, groups):
    """CP-SAT model: one Boolean per mechanism of each of the 11 image groups, exactly one per group, and the XOR
    of the chosen mechanisms' detectors vanishes on every detector.  Returns (model, variables per group)."""
    from ortools.sat.python import cp_model
    M = cp_model.CpModel()
    one = M.NewConstant(1)
    det_lits = defaultdict(list)
    var = []
    for key in S_keys:
        vs = []
        for dets in groups[key]:
            v = M.NewBoolVar("")
            vs.append(v)
            for d in dets:
                det_lits[d].append(v)
        M.AddExactlyOne(vs)
        var.append(vs)
    for d, ls in det_lits.items():
        M.AddBoolXOr(ls + [one])      # XOR(ls) xor 1 = 1  <=>  XOR(ls) = 0
    return M, var


def lift(S_keys, groups, want_solution=False):
    from ortools.sat.python import cp_model
    M, var = lift_model(S_keys, groups)
    s = cp_model.CpSolver()
    s.parameters.num_workers = 1
    s.parameters.random_seed = 7
    st = s.Solve(M)
    assert st in (cp_model.OPTIMAL, cp_model.INFEASIBLE, cp_model.FEASIBLE), s.StatusName(st)
    if st == cp_model.INFEASIBLE:
        return None
    if not want_solution:
        return True
    return [next(m for m, v in enumerate(vs) if s.Value(v)) for vs in var]
