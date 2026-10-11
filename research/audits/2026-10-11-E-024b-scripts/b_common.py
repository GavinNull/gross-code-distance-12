"""Audit E-021 shared helpers (own code; reuses only the E-018 AUDIT's own extended code / DFS outputs)."""
import json, sys, glob
import numpy as np
import stim
sys.path.insert(0, "tests"); sys.path.insert(0, "research/audits/2026-10-08-E-018-scripts")
from evaluators.tasks import build_code, get_task
from evaluators.candidate import parse_schedule, build_circuits
from evaluators.noise import add_noise
import a1_common as A1          # E-018 audit: Fig. 12 spec/orders (from evaluator-format baseline)
import a2_stage_a as A2         # E-018 audit: own extended code + DFS-output collection

code, _ = build_code(get_task("gross-dcirc"), None)
HX, HZ, LX, LZ = [np.asarray(m, np.uint8) % 2 for m in (code.HX, code.HZ, code.LX, code.LZ)]
import os
CAND = os.environ.get("SPEC", "search/experiments/e021/cand1_spec.json")
TAG = os.environ.get("TAG", "")
OUT = "results/E-024b-audit" + (f"/{TAG}" if TAG else "")
os.makedirs(OUT, exist_ok=True)
# kind = type of the hook-spreading check: kind X <-> Z-basis memory (X errors, H = HZ); kind Z <-> X basis
BASIS_OF_KIND = {"X": "Z", "Z": "X"}


def load_spec(path=CAND):
    return parse_schedule(json.load(open(path)))


def orders(spec):
    P = spec.period
    f = lambda c: [col for _, col in sorted(((t - c.prep) % P, col) for col, t in c.cnots)]
    return [f(c) for c in spec.x_checks], [f(c) for c in spec.z_checks]


def ext_keys(kind, xo, zo):
    """own extended-code column keys: data qubits + every proper suffix of each hook-spreading check's order."""
    H, L, ords = (HZ, LZ, xo) if kind == "X" else (HX, LX, zo)
    sups = [(j,) for j in range(144)] + [tuple(sorted(o[k:])) for o in ords for k in range(1, 6)]
    keys = {}
    for s in sups:
        v = np.zeros(144, np.uint8); v[list(s)] = 1
        hb, lb = (H @ v) % 2, (L @ v) % 2
        if hb.any() or lb.any():
            keys.setdefault(hb.tobytes() + lb.tobytes(), s)
    return keys


def dem_groups(spec, R, basis, noise="sd6"):
    """own augmented DEM: per nonzero image key -> list of detector frozensets; plus stats."""
    c = add_noise(build_circuits(spec.canonical(), code, R)[basis], noise, 1e-3).flattened()
    H, L = (HZ, LZ) if basis == "Z" else (HX, LX)
    nm = c.num_measurements; n = 144
    # final data readout is the last measurement instruction over all 144 data qubits (template)
    last = [op for op in c if op.name in ("M", "MX")][-1]
    tq = [t.value for t in last.targets_copy()]
    assert tq == list(range(n))
    k0 = c.num_observables
    aug = c.copy()
    for r, row in enumerate(list(H) + list(L)):
        aug.append("OBSERVABLE_INCLUDE", [stim.target_rec(q - n) for q in np.nonzero(row)[0]], k0 + r)
    dem = aug.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    coords = dem.get_detector_coordinates()
    nH = H.shape[0]
    groups, nz, nt, bad_obs, tele_bad = {}, 0, 0, 0, 0
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        nt += 1
        dets = set(); hb = np.zeros(nH, np.uint8); lb = np.zeros(L.shape[0], np.uint8); ob = np.zeros(k0, np.uint8)
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                dets ^= {t.val}
            elif t.is_logical_observable_id():
                v = t.val
                if v < k0: ob[v] ^= 1
                elif v < k0 + nH: hb[v - k0] ^= 1
                else: lb[v - k0 - nH] ^= 1
        if not (ob == lb).all():
            bad_obs += 1
        par = np.zeros(nH, np.uint8)
        for d in dets:
            par[int(coords[d][0])] ^= 1
        if not (par == hb).all():
            tele_bad += 1
        if not hb.any() and not lb.any():
            nz += 1; continue
        groups.setdefault(hb.tobytes() + lb.tobytes(), []).append(frozenset(dets))
    return groups, dict(terms=nt, zero_image=nz, bad_obs=bad_obs, telescoping_bad=tele_bad,
                        detectors=c.num_detectors, keys=len(groups))


def audit018_lists(kind):
    """E-018 audit's own complete weight-11 list (DFS outputs + 24-element group), as tuples of column KEYS."""
    keys, kidx, colsup, supkey = A2.build_cache.setdefault(kind, A2.build(kind))
    G = A2.group(kind)
    perms = [A2.colperm(kind, pp, kidx, colsup) for pp in G]
    found = set()
    for fn in glob.glob(f"results/E-018-audit/dfs_{kind}_*.txt"):
        for line in open(fn):
            if line.startswith("SUMMARY"):
                continue
            S = tuple(map(int, line.split()))
            for p in perms:
                found.add(tuple(sorted(p[j] for j in S)))
    kb = [hb.tobytes() + lb.tobytes() for hb, lb in keys]
    return [tuple(kb[j] for j in S) for S in sorted(found)], kb
