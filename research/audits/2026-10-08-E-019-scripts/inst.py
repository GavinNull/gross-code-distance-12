"""E-019 audit: build DEM-based instances for mdfs from my own circuits (mycirc.py) and the frozen-path noise
module (evaluators/noise.py, read only).

instance(M, basis, T, full, model, window) -> (rows, cols, obs, orbits)
  full=True : all deterministic detectors (both bases), full stim DEM (Y components merged) -> exact d_circ
  full=False: same-basis detectors only (CSS projection)
  model     : 'sd6' or 'noidle' (= uniform_depolarizing(idle=False), same as sd6 without idle channels)
  window    : None (noise everywhere) or (t_lo, t_hi): keep noise only in layers of half-cycles t_lo..t_hi
              (half-cycle t = its reset layer [t>=2], 6 CX layers, its M layer); 'interior' variants drop
              boundary noise (initial reset layer, final readout flips) by choosing t_lo >= 2, t_hi <= T-1.
Orbit split: translations by K = ker f map the circuit to itself (checked op by op here); the induced
permutation of DEM columns is computed from detector record-sets; used only if consistent.
"""
from __future__ import annotations
import sys, itertools
import numpy as np
import stim
sys.path.insert(0, '/Users/ephemeral/Desktop/qec-ai-search/research/audits/2026-10-08-E-019-scripts')
sys.path.insert(0, '/Users/ephemeral/Desktop/qec-ai-search')
from mycirc import Morph, PARENT, natural_order, HOM, gf2_rank, logicals
from evaluators.noise import add_noise

NOISE_NAMES = ("DEPOLARIZE1", "DEPOLARIZE2", "X_ERROR", "Z_ERROR", "Y_ERROR", "PAULI_CHANNEL_1", "PAULI_CHANNEL_2")


def make(code, hom, kind, sa, sb):
    l, m, A, B = PARENT[code]
    a, b = natural_order(code, hom)
    aa = (a[0], a[2], a[1]) if sa else a
    bb = (b[0], b[2], b[1]) if sb else b
    return Morph(l, m, aa, bb, hom, kind)


def half_cycle_layers(T):
    """layer index ranges per half-cycle in mycirc.memory: layer 0 = initial reset; t=1: CX 1..6, M 7;
    t>=2: reset, 6 CX, M."""
    rng = {}
    L = 1
    for t in range(1, T + 1):
        lo = L if t == 1 else L
        n = 7 if t == 1 else 8
        rng[t] = (lo, lo + n - 1)
        L += n
    return rng


def noisy(M, basis, T, full, model, window, p=1e-3):
    c = M.memory(basis, T, full_detectors=full)
    if model == "sd6":
        nc = add_noise(c, "sd6", p)
    elif model == "noidle":
        nc = add_noise(c, "uniform_depolarizing", p, idle=False)
    else:
        raise ValueError(model)
    if window is not None:
        rng = half_cycle_layers(T)
        keep = set()
        for t in range(window[0], window[1] + 1):
            keep |= set(range(rng[t][0], rng[t][1] + 1))
        out = stim.Circuit()
        layer = 0
        for inst in nc.flattened():
            if inst.name == "TICK":
                layer += 1
            elif inst.name in NOISE_NAMES and layer not in keep:
                continue
            out.append(inst)
        nc = out
    return c, nc


def dem_columns(nc):
    dem = nc.detector_error_model(decompose_errors=False)
    cols = []
    for e in dem.flattened():
        if e.type != "error":
            continue
        D, O = [], []
        for t in e.targets_copy():
            if t.is_relative_detector_id():
                D.append(t.val)
            elif t.is_logical_observable_id():
                O.append(t.val)
        cols.append((tuple(sorted(D)), tuple(sorted(O))))
    return dem.num_detectors, dem.num_observables, cols


def det_recsets(c):
    """for each DETECTOR in circuit c: frozenset of absolute record indices."""
    out = []
    nrec = 0
    for inst in c.flattened():
        if inst.name in ("M", "MX", "MY", "MR", "MRX"):
            nrec += len(inst.targets_copy())
        elif inst.name == "DETECTOR":
            out.append(frozenset(nrec + t.value for t in inst.targets_copy()))
    return out


def orbits(M, c, cols, used_rows):
    """K-translation orbits of the columns. Returns orbit id per column or None if inconsistent."""
    f = HOM[M.hom]
    K = [g for g in M.G if f(g) == 0]
    # record index -> (t, q) and back
    inv = {v: k for k, v in M.recidx.items()}
    rs = det_recsets(c)
    rsidx = {s: i for i, s in enumerate(rs)}

    def tq(q, s):
        if q < M.N:
            g = M.G[q]
            return M.Lq(M.add(g, s))
        g = M.G[q - M.N]
        return M.Rq(M.add(g, s))

    # circuit automorphism check: layer gate sets invariant
    for i in (1, 2):
        layers, meas = M.F(i)
        for s in K:
            for lay in layers:
                S0 = set(lay)
                if {(tq(a, s), tq(b, s)) for a, b in lay} != S0:
                    return None, "layer not invariant"
            for bb in "XZ":
                if {tq(q, s) for q in meas[bb]} != set(meas[bb]):
                    return None, "meas not invariant"
    dperm = {}
    for s in K:
        pm = []
        for d, st in enumerate(rs):
            img = frozenset(M.recidx[(inv[r][0], tq(inv[r][1], s))] for r in st)
            if img not in rsidx:
                return None, "detector set not covariant"
            pm.append(rsidx[img])
        dperm[s] = pm
    colidx = {}
    for k, (D, O) in enumerate(cols):
        if D in colidx:
            return None, "duplicate detector set"
        colidx[D] = k
    orb = [-1] * len(cols)
    no = 0
    for k in range(len(cols)):
        if orb[k] >= 0:
            continue
        for s in K:
            D2 = tuple(sorted(dperm[s][d] for d in cols[k][0]))
            if D2 not in colidx:
                return None, f"column image missing (col {k})"
            j = colidx[D2]
            if orb[j] >= 0 and orb[j] != no:
                return None, "orbit conflict"
            orb[j] = no
        no += 1
    return orb, no


def write_instance(path, ndet, nobs, cols, orb=None, norb=0):
    rows = sorted({d for D, _ in cols for d in D})
    rmap = {d: i for i, d in enumerate(rows)}
    with open(path, "w") as fh:
        fh.write(f"{len(rows)} {len(cols)} {nobs} {norb if orb is not None else 0}\n")
        for k, (D, O) in enumerate(cols):
            o = orb[k] if orb is not None else 0
            fh.write(f"{o} {len(D)} " + " ".join(str(rmap[d]) for d in D) + f" {len(O)} " + " ".join(map(str, O)) + "\n")
    return len(rows)


def reorder_by_orbit(cols, orb):
    """mdfs uses the first column of each orbit as representative; any order works."""
    return cols, orb
