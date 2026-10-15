"""Audit rev-g (1): per-fault data images (Table I / SM S5), checked directly on the DEM.

Augments the evaluator's noisy SD6 circuit with one observable per row of H and of L on the final data readout
(single data readouts are not deterministic, the rows are), so every DEM mechanism carries its exact image
(H s, L s); mechanisms merge only when detectors AND image coincide, so each fault's image is read off exactly.
Checks: image is zero or equals (H s, L s) for s a singleton or a suffix {q_k..q_6}, k=2..6, of one hook-spreading
check's order (template time order); records which s-types occur; per-check detector parity == H part
(telescoping); the circuit's own observables == L part.
    PYTHONPATH=.:tests uv run python research/audits/2026-10-14-revg-scripts/g1_images.py
"""
import json, sys
from collections import Counter
import numpy as np, stim
sys.path.insert(0, "tests")
from evaluators.tasks import build_code, get_task
from evaluators.candidate import parse_schedule, build_circuits
from evaluators.noise import add_noise
from schedule_helpers import from_baseline
from baselines.bb_code import gross_code
from baselines.strikis import strikis_fig12

code, _ = build_code(get_task("gross-dcirc"), None)
HX, HZ, LX, LZ = [np.asarray(m, np.uint8) % 2 for m in (code.HX, code.HZ, code.LX, code.LZ)]
n = 144
specA = parse_schedule(json.load(open("search/experiments/e024a/cs_P18_H24.json")))
specF = from_baseline(strikis_fig12(gross_code())[0])


def orders(spec, typ):
    P = spec.period
    cks = spec.x_checks if typ == "X" else spec.z_checks
    return [[col for _, col in sorted(((t - c.prep) % P, col) for col, t in c.cnots)] for c in cks]


def run(spec, R, basis):
    H, L = (HZ, LZ) if basis == "Z" else (HX, LX)
    hook = orders(spec, "X" if basis == "Z" else "Z")   # checks whose ancilla is control-like for this frame
    suff = {}
    for ci, o in enumerate(hook):
        for k in range(6):
            suff.setdefault(frozenset(o[k:]), []).append((ci, k + 1))
    c = add_noise(build_circuits(spec.canonical(), code, R)[basis], "sd6", 1e-3).flattened()
    last = [op for op in c if op.name in ("M", "MX")][-1]
    assert [t.value for t in last.targets_copy()] == list(range(n))
    k0 = c.num_observables
    aug = c.copy()
    rows = list(H) + list(L)
    for r, row in enumerate(rows):
        aug.append("OBSERVABLE_INCLUDE", [stim.target_rec(q - n) for q in np.nonzero(row)[0]], k0 + r)
    nH = H.shape[0]
    key = lambda v: ((H @ v) % 2).tobytes() + ((L @ v) % 2).tobytes()
    allowed = {}
    for q in range(n):
        v = np.zeros(n, np.uint8); v[q] = 1; allowed.setdefault(key(v), []).append(("single", q))
    for fs, lst in suff.items():
        v = np.zeros(n, np.uint8); v[list(fs)] = 1
        if len(fs) < 6: allowed.setdefault(key(v), []).append((f"suffix_len{len(fs)}", lst))
    dem = aug.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    coords = dem.get_detector_coordinates()
    cnt = Counter(); bad = []; tele_bad = obs_bad = 0; hit = set()
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        dets, ob = set(), np.zeros(k0, np.uint8)
        hb = np.zeros(nH, np.uint8); lb = np.zeros(L.shape[0], np.uint8)
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                dets ^= {t.val}
            elif t.is_logical_observable_id():
                if t.val < k0: ob[t.val] ^= 1
                elif t.val < k0 + nH: hb[t.val - k0] ^= 1
                else: lb[t.val - k0 - nH] ^= 1
        par = np.zeros(nH, np.uint8)
        for d in dets:
            par[int(coords[d][0])] ^= 1
        tele_bad += int(not (hb == par).all())
        obs_bad += int(not (lb == ob).all())
        kk = hb.tobytes() + lb.tobytes()
        if not hb.any() and not lb.any(): cnt["zero"] += 1
        elif kk in allowed:
            hit.add(kk); typs = sorted({a for a, _ in allowed[kk]}); cnt["/".join(typs)] += 1
        else:
            bad.append((int(hb.sum()), int(lb.sum())))
    kseen = {"distinct_columns_hit": len(hit), "allowed_keys": len(allowed)}
    return dict(mechanisms=sum(cnt.values()) + len(bad), classes=dict(cnt), columns=kseen,
                not_allowed=len(bad), examples=bad[:5], telescoping_bad=tele_bad, logical_bad=obs_bad)


out = {}
for name, spec in (("circuitA", specA), ("fig12", specF)):
    for R in (1, 2, 3):
        for basis in "ZX":
            r = run(spec, R, basis)
            out[f"{name}_R{R}_{basis}"] = r
            print(name, R, basis, r, flush=True)
json.dump(out, open("research/audits/2026-10-14-revg-scripts/g1_images.json", "w"), indent=1)
