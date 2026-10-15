"""[[90,8,10]]: circuits, translations, extended codes, augmented detector error model and the exact lift test.

Conventions as for the gross code (code/gross12/ext.py): the Z-basis memory sees X errors, uses H = HZ, L = LZ and the
residuals (proper suffixes) of the X-check CNOT orders; the X basis is the mirror image.  A column of the extended code
is a nonzero pair (H s, L s) for s a single data qubit or a proper suffix of a check order; equal pairs are merged.
Column order (used by all data files): data qubits 0..89 first, then for every check in row order its suffixes of
length 5, 4, 3, 2, 1, keeping the first occurrence of each (H s, L s) (gross12.ext.ext_columns).

Lift test with one zero-image fault (case b).  Every DEM mechanism of the augmented model carries its image (the
X part, resp. Z part, of its residual data error at the end, as (H, L) syndrome).  For c16 the image is 0 or one
extended column (asserted for every mechanism).  An undetected logical F of weight 9 with d_ext = 8 has either 9
distinct non-zero images forming a weight-9 extended logical (case a), or 8 distinct non-zero images forming a
weight-8 extended logical plus one mechanism of zero image (case b): with z zero images and c cancelling pairs the
remaining columns form an extended logical of weight 9 - z - 2c >= 8.  lift() decides, for one list entry S, whether
one mechanism per column (and, in case b, at most one zero-image mechanism) can be chosen with every detector sum 0.
"""
from __future__ import annotations

import json

import numpy as np
import stim
from pysat.card import CardEnc, EncType
from pysat.solvers import Solver

from gross12.ext import ext_columns, hl, key_of, orbits      # noqa: F401  (re-exported)
from gross12.noise import add_sd6
from gross12.paths import CIRCUITS, DATA
from gross12.schedule import build_circuits, load_schedule

from .bbcode import L_, M_, N, N2

CIRCUIT_FILES = {"c16": CIRCUITS / "bb90_c16.json", "u16": CIRCUITS / "bb90_u16.json", "s16": CIRCUITS / "bb90_s16.json"}
EXT = DATA / "extended_code"
LOGICALS = DATA / "logicals"


def circuit(name: str):
    return load_schedule(CIRCUIT_FILES[name])


def translation(a: int, b: int) -> list[int]:
    """translation by x^a y^b on the 90 data qubits (both blocks); also the map of check indices (first 45)."""
    p = [((i // M_ + a) % L_) * M_ + (i % M_ + b) % M_ for i in range(N2)]
    return p + [x + N2 for x in p]


GROUP = [(a, b) for a in range(L_) for b in range(M_)]


def order_group(spec) -> list[tuple[int, int]]:
    """translations that map the CNOT order of every check to the order of the image check (both check types)."""
    xo, zo = spec.orders()
    G = []
    for a, b in GROUP:
        pq = translation(a, b)
        if all(tuple(pq[q] for q in ords[i]) == tuple(ords[pq[i]]) for ords in (xo, zo) for i in range(N2)):
            G.append((a, b))
    return G


def column_perms(code, basis, keys, supports, supkey, G):
    kidx = {k: j for j, k in enumerate(keys)}
    perms = []
    for a, b in G:
        pq = translation(a, b)
        perms.append([kidx[supkey[tuple(sorted(pq[q] for q in s))]] for s in supports])
    return perms


def column_perms_data(code, basis, keys, G):
    """column permutations computed from the column keys alone (translation of a representative support)."""
    d = load_ext(basis)
    kidx = {k: j for j, k in enumerate(keys)}
    perms = []
    for a, b in G:
        pq = translation(a, b)
        perms.append([kidx[key_of(code, basis, [pq[q] for q in c["support"]])] for c in d["columns"]])
    return perms


# ---------------------------------------------------------------------------------------------------------------
# data files

def load_ext(basis: str) -> dict:
    return json.load(open(EXT / f"bb90_extended_code_{basis}_memory.json"))


def ext_keys_from_file(code, basis: str) -> list[bytes]:
    d = load_ext(basis)
    H, L = hl(code, basis)
    out = []
    for c in d["columns"]:
        h = np.zeros(H.shape[0], np.uint8); h[c["H"]] = 1
        lv = np.zeros(L.shape[0], np.uint8); lv[c["L"]] = 1
        assert key_of(code, basis, c["support"]) == h.tobytes() + lv.tobytes(), c
        out.append(h.tobytes() + lv.tobytes())
    return out


def load_list(w: int, basis: str) -> list[list[int]]:
    d = json.load(open(LOGICALS / f"bb90_weight{w}_logicals_{basis}_memory.json"))
    assert d["count"] == len(d["logicals"])
    return [e["columns"] for e in d["logicals"]]


def key_matrices(keys, nH):
    Hm = np.array([np.frombuffer(k[:nH], np.uint8) for k in keys]).T
    Lm = np.array([np.frombuffer(k[nH:], np.uint8) for k in keys]).T
    return Hm, Lm


# ---------------------------------------------------------------------------------------------------------------
# augmented detector error model

def noisy_circuit(spec, code, R: int, basis: str) -> stim.Circuit:
    return add_sd6(build_circuits(spec.canonical(), code, R)[basis]).flattened()


def dem_terms(spec, code, R: int, basis: str, keys):
    """SD6 DEM of the memory circuit augmented with one observable per row of H and of L on the final data readout.
    Returns (groups, zeros, stats): groups[j] = sorted list of the distinct detector sets (as int bit masks) of the
    mechanisms whose image is extended column j; zeros = set of detector masks of the zero-image mechanisms that
    have detectors.  Asserts that every image is 0 or a column of `keys` (Lemma 1 for this circuit) and counts:
    template identity (per-check detector parity = H part of the image), logical effect = L part, unrealised
    columns, and zero-image mechanisms of the readout pattern {(c, j), (c, j + 1)}."""
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
    kidx = {k: j for j, k in enumerate(keys)}
    groups = {j: set() for j in range(len(keys))}
    zeros = set()
    nt = nz = nz_nodet = bad_obs = tele_bad = not_column = readout = 0
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
        bad_obs += not (ob == lb).all()
        par = np.zeros(nH, np.uint8)
        for d in dets:
            par[int(coords[d][0])] ^= 1
        tele_bad += not (par == hb).all()
        mask = sum(1 << d for d in dets)
        if not hb.any() and not lb.any():
            nz += 1
            if dets:
                zeros.add(mask)
                ds = sorted(dets)
                if len(ds) == 2 and coords[ds[0]][0] == coords[ds[1]][0] and coords[ds[1]][1] == coords[ds[0]][1] + 1:
                    readout += 1
            else:
                nz_nodet += 1
            continue
        k = hb.tobytes() + lb.tobytes()
        if k not in kidx:
            not_column += 1
            continue
        groups[kidx[k]].add(mask)
    st = dict(mechanisms=nt, detectors=c.num_detectors, zero_image=nz, zero_image_no_detector=nz_nodet,
              zero_image_with_detectors=len(zeros), zero_image_readout_pattern=readout, bad_obs=bad_obs,
              telescoping_bad=tele_bad, image_not_a_column=not_column,
              unrealised_columns=sum(1 for g in groups.values() if not g))
    return {j: sorted(g) for j, g in groups.items()}, zeros, st


def _masks(m):
    out = []
    while m:
        low = m & -m
        out.append(low.bit_length() - 1)
        m ^= low
    return out


def lift(group_list, extra=None) -> bool:
    """SAT (CaDiCaL 1.5.3 via python-sat): exactly one mechanism from each group of group_list, at most one from
    `extra` (list of detector masks, case b), and every detector sum = 0.  Exact (SAT / UNSAT)."""
    var = 0
    cls = []
    det_of = {}
    blocks = list(group_list) + ([extra] if extra else [])
    vs_extra = []
    for gi, g in enumerate(blocks):
        vs = []
        for m in g:
            var += 1
            vs.append(var)
            for x in _masks(m):
                det_of.setdefault(x, []).append(var)
        if extra and gi == len(blocks) - 1:
            vs_extra = vs
        else:
            cls.append(vs)
            cls += [[-vs[i], -vs[j]] for i in range(len(vs)) for j in range(i + 1, len(vs))]
    top = var
    for x, vs in det_of.items():
        cur = vs[0]
        for v in vs[1:]:
            top += 1
            y = top
            cls += [[-cur, -v, -y], [cur, v, -y], [cur, -v, y], [-cur, v, y]]
            cur = y
        cls.append([-cur])
    if len(vs_extra) > 1:
        am = CardEnc.atmost(vs_extra, 1, top_id=top, encoding=EncType.seqcounter)
        cls += am.clauses
    with Solver(name="cd15", bootstrap_with=cls) as s:
        return s.solve()


def lift_counts(groups, zeros, l8, l9, stop_first=False):
    """counts of weight-8 list entries that lift (w8), that lift with one zero-image mechanism (w8z), and of weight-9
    entries that lift (w9).  Case b only uses zero-image mechanisms whose detectors lie in the union of the detectors
    of the eight groups (a detector outside that union could not be cancelled)."""
    out = {"w8": 0, "w8z": 0, "w9": 0, "hits": {"w8": [], "w8z": [], "w9": []}}
    for cat, lst in (("w8", l8), ("w8z", l8), ("w9", l9)):
        for i, S in enumerate(lst):
            gl = [groups[j] for j in S]
            if cat == "w8z":
                supp = 0
                for g in gl:
                    for m in g:
                        supp |= m
                ex = [z for z in zeros if z & ~supp == 0]
                if not ex:
                    continue
                hit = lift(gl, ex)
            else:
                hit = lift(gl)
            if hit:
                out[cat] += 1
                if len(out["hits"][cat]) < 5:
                    out["hits"][cat].append(i)
                if stop_first:
                    break
    return out
