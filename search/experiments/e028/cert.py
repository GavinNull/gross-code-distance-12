"""E-028 certification with the AUDITOR's lift implementation adapted to [[90,8,10]]
(research/audits/2026-10-10-E-021-scripts: b_common.ext_keys / dem_groups and b3_lift.lifts copied, only the code and
sizes changed), extended by one case for d_ext = 8:

  weight <= 9 undetected logical  <=>  one of
    (a) a weight-8 extended logical S with one DEM term per column whose detector sets XOR to 0       [lifts]
    (b) a weight-8 extended logical S + exactly one zero-image DEM term (detectors only), XOR 0      [lifts_z]
    (c) a weight-9 extended logical S with one DEM term per column, XOR 0                             [lifts]
  (template identity: product of each check's detectors = row of H on the end-of-circuit image; Table I: every term's
  image key is 0 or an extended column; d_ext = 8 on the side; see lift9.py for the case analysis).
Asserted per (R, basis): the image-key set equals the class's extended column set, bad_obs = 0, telescoping_bad = 0.

    PYTHONPATH=.:tests uv run python -m search.experiments.e028.cert SPEC.json Z A1A2A3B2B1B3 1 2 3 ...
"""
import json
import pickle
import sys
import time

import numpy as np
import stim
from ortools.sat.python import cp_model

from evaluators.candidate import build_circuits, parse_schedule
from evaluators.noise import add_noise
from evaluators.tasks import build_code, get_task

OUT = "results/E-028-bb90-interleaved"
code, _ = build_code(get_task("bb90-dcirc"), None)
HX, HZ, LX, LZ = [np.asarray(m, np.uint8) % 2 for m in (code.HX, code.HZ, code.LX, code.LZ)]
NQ = 90


def orders(spec):
    P = spec.period
    f = lambda c: [col for _, col in sorted(((t - c.prep) % P, col) for col, t in c.cnots)]  # noqa: E731
    return [f(c) for c in spec.x_checks], [f(c) for c in spec.z_checks]


def ext_keys(kind, xo, zo):
    H, L, ords = (HZ, LZ, xo) if kind == "X" else (HX, LX, zo)
    sups = [(j,) for j in range(NQ)] + [tuple(sorted(o[k:])) for o in ords for k in range(1, 6)]
    keys = {}
    for s in sups:
        v = np.zeros(NQ, np.uint8); v[list(s)] = 1
        hb, lb = (H @ v) % 2, (L @ v) % 2
        if hb.any() or lb.any():
            keys.setdefault(hb.tobytes() + lb.tobytes(), s)
    return keys


def dem_groups(spec, R, basis, noise="sd6"):
    c = add_noise(build_circuits(spec.canonical(), code, R)[basis], noise, 1e-3).flattened()
    H, L = (HZ, LZ) if basis == "Z" else (HX, LX)
    n = NQ
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
    groups, zeros, nz, nt, bad_obs, tele_bad = {}, set(), 0, 0, 0, 0
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
            nz += 1
            if dets:
                zeros.add(frozenset(dets))
            continue
        groups.setdefault(hb.tobytes() + lb.tobytes(), []).append(frozenset(dets))
    return groups, sorted(zeros, key=sorted), dict(terms=nt, zero_image=nz, zero_masks=len(zeros), bad_obs=bad_obs,
                                                  telescoping_bad=tele_bad, detectors=c.num_detectors, keys=len(groups))


def _solve(M):
    s = cp_model.CpSolver(); s.parameters.num_workers = 1; s.parameters.random_seed = 7
    st = s.Solve(M)
    assert st in (cp_model.OPTIMAL, cp_model.INFEASIBLE, cp_model.FEASIBLE), s.StatusName(st)
    return st != cp_model.INFEASIBLE


def lifts(S, groups):   # verbatim from b3_lift.py (auditor), solver call factored out
    M = cp_model.CpModel()
    one = M.NewConstant(1)
    det_lits = {}
    for key in S:
        vs = []
        for dets in groups[key]:
            v = M.NewBoolVar("")
            vs.append(v)
            for d in dets:
                det_lits.setdefault(d, []).append(v)
        M.AddExactlyOne(vs)
    for d, ls in det_lits.items():
        M.AddBoolXOr(ls + [one])
    return _solve(M)


def lifts_z(S, groups, zeros):
    """(b): one term per column of S plus exactly one zero-image term (restricted to terms inside the support)."""
    sup = set()
    for key in S:
        for dets in groups[key]:
            sup |= dets
    zs = [z for z in zeros if z <= sup]
    if not zs:
        return False
    M = cp_model.CpModel()
    one = M.NewConstant(1)
    det_lits = {}
    for key in S:
        vs = []
        for dets in groups[key]:
            v = M.NewBoolVar("")
            vs.append(v)
            for d in dets:
                det_lits.setdefault(d, []).append(v)
        M.AddExactlyOne(vs)
    zv = []
    for z in zs:
        v = M.NewBoolVar("")
        zv.append(v)
        for d in z:
            det_lits.setdefault(d, []).append(v)
    M.AddExactlyOne(zv)
    for d, ls in det_lits.items():
        M.AddBoolXOr(ls + [one])
    return _solve(M)


def main():
    path, basis, orders_s, Rs = sys.argv[1], sys.argv[2], sys.argv[3], [int(x) for x in sys.argv[4:]]
    kind = {"Z": "X", "X": "Z"}[basis]
    spec = parse_schedule(json.load(open(path)))
    xo, zo = orders(spec.canonical())
    l8 = pickle.load(open(f"{OUT}/w8_{kind}_all_{orders_s}.pkl", "rb"))
    l9 = pickle.load(open(f"{OUT}/w9_{kind}_all_{orders_s}.pkl", "rb"))
    kb = set(ext_keys(kind, xo, zo))
    assert kb == set(l8["colset"]) == set(l9["colset"]), "extended code differs from the class"
    L8 = [tuple(S) for S in l8["keys"]]
    L9 = [tuple(S) for S in l9["keys"]]
    tag = path.split("/")[-1].replace(".json", "")
    for R in Rs:
        t0 = time.time()
        groups, zeros, st = dem_groups(spec, R, basis)
        assert set(groups) == kb and st["bad_obs"] == 0 and st["telescoping_bad"] == 0, st
        a = [i for i, S in enumerate(L8) if lifts(S, groups)]
        b = [i for i, S in enumerate(L8) if lifts_z(S, groups, zeros)]
        c = [i for i, S in enumerate(L9) if lifts(S, groups)]
        rec = {"spec": path, "basis": basis, "R": R, "w8": len(a), "w8z": len(b), "w9": len(c), "n8": len(L8),
               "n9": len(L9), **st, "sec": round(time.time() - t0, 1), "first": [a[:5], b[:5], c[:5]]}
        print(json.dumps(rec), flush=True)
        with open(f"{OUT}/cert_{tag}_{basis}.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")


if __name__ == "__main__":
    main()
