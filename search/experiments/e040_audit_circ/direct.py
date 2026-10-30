"""Item (3b): direct exhaustive search on the evaluator's SD6 DEM (no extended code, no lists, no lemmas).

Columns = DEM error terms (detector set, observable set) of add_noise(memory_circuit(spec, basis, R), "sd6").
Spatial translation symmetry is established term by term: the 72 check translations permute detectors
((row, round) -> (row', round)); every term must map to a term, and observable sets must transform by ONE linear
map M over GF(2) (solved and verified on all terms, M invertible), so undetectable logicals map to undetectable
logicals.  Then mitmsearch (decide, look 2) with orbit root cases, each orbit in its own process (pool <= procs).
A minimum-weight undetectable logical has no proper zero-syndrome subset, so "no solution with W" <=> d_circ > W.

  uv run python -m search.experiments.e040_audit_circ.direct g10 Z 1 11 --procs 2
"""
from __future__ import annotations

import argparse
import subprocess
import time

import numpy as np

from search.experiments.e040_audit_circ.common import OUT, gross, jdump, load


def gf2_solve_map(X, Y):
    """find A with Y = X @ A (mod 2) on all rows (X: n x f features, Y: n x k); return A or None if inconsistent."""
    X = X.astype(np.uint8) % 2
    Y = Y.astype(np.uint8) % 2
    n, f = X.shape
    A = np.concatenate([X, Y], axis=1).copy()
    piv = []
    r = 0
    for c in range(f):
        if r == n:
            break
        rows = np.flatnonzero(A[r:, c]) + r
        if not len(rows):
            continue
        p = rows[0]
        A[[r, p]] = A[[p, r]]
        for i in np.flatnonzero(A[:, c]):
            if i != r:
                A[i] ^= A[r]
        piv.append(c)
        r += 1
    if A[r:, f:].any():
        return None
    M = np.zeros((f, Y.shape[1]), np.uint8)
    for i, c in enumerate(piv):
        M[c] = A[i, f:]
    assert np.array_equal(X.astype(np.int64) @ M % 2, Y)
    return M


def build(name, basis, R):
    from evaluators import candidate as cand
    from evaluators.noise import add_noise
    from search.theory.B_audit.common import Bulk
    from search.theory.B_audit.enum_driver import translations
    code = gross()
    sd = load(name)
    circ = add_noise(cand.memory_circuit(cand.parse_schedule(sd), code, basis, R), "sd6", 1e-3)
    coords = circ.get_detector_coordinates()
    dem = circ.detector_error_model(approximate_disjoint_errors=True, flatten_loops=True)
    errs = {}
    for e in dem.flattened():
        if e.type != "error":
            continue
        ds, os_ = set(), set()
        for t in e.targets_copy():
            if t.is_relative_detector_id():
                ds ^= {t.val}
            elif t.is_logical_observable_id():
                os_ ^= {t.val}
        if ds or os_:
            assert ds, "detector-free logical term"
            k = frozenset(ds)
            assert errs.get(k, frozenset(os_)) == frozenset(os_), "same detectors, different observables"
            errs[k] = frozenset(os_)
    keys = sorted(errs, key=sorted)
    kid = {k: i for i, k in enumerate(keys)}
    det_of = {(int(c[0]), int(c[1])): d for d, c in coords.items()}
    B = Bulk(sd, code, basis)
    perms = translations("gross", B, sd)
    K = dem.num_observables
    O = np.zeros((len(keys), K), np.uint8)
    for i, k in enumerate(keys):
        for o in errs[k]:
            O[i, o] = 1
    # features of a term: its observables and its syndrome image h_c = parity of check c's detectors (telescoping);
    # an undetectable set has h = 0, so obs(pi F) = obs(F) @ A[:K]; with pi^-1 also linear, obs(F) != 0 <=>
    # obs(pi F) != 0.  We require such a linear A to exist for every translation pi.
    nrow = 1 + max(int(c[0]) for c in coords.values())
    Hh = np.zeros((len(keys), nrow), np.uint8)
    for i, k in enumerate(keys):
        for x in k:
            Hh[i, int(coords[x][0])] ^= 1
    X = np.concatenate([O, Hh], axis=1)
    colperm = []
    for qp, cp in perms:
        dmap = {d: det_of[(cp[int(c[0])], int(c[1]))] for d, c in coords.items()}
        pm = []
        for k in keys:
            k2 = frozenset(dmap[x] for x in k)
            assert k2 in kid, "translated term missing"
            pm.append(kid[k2])
        assert sorted(pm) == list(range(len(keys)))
        M = gf2_solve_map(X, O[pm])
        assert M is not None, "observable action not linear even modulo syndrome image"
        colperm.append(pm)
    return keys, errs, dem.num_detectors, K, colperm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("basis")
    ap.add_argument("R", type=int)
    ap.add_argument("W", type=int)
    ap.add_argument("--procs", type=int, default=1)
    ap.add_argument("--mode", default="decide")
    a = ap.parse_args()
    t0 = time.time()
    keys, errs, nd, K, colperm = build(a.name, a.basis, a.R)
    orb = [-1] * len(keys)
    reps = []
    for j in range(len(keys)):
        if orb[j] < 0:
            for pm in colperm:
                orb[pm[j]] = len(reps)
            reps.append(j)
    lines = [f"{len(keys)} {nd}"]
    for k in keys:
        lines.append(f"{len(k)} {' '.join(map(str, sorted(k)))} {len(errs[k])} {' '.join(map(str, sorted(errs[k])))}")
    lines += [str(len(reps)), " ".join(map(str, orb)), " ".join(map(str, reps))]
    inp = OUT / f"dem_{a.name}_{a.basis}_R{a.R}.txt"
    inp.write_text("\n".join(lines) + "\n")
    nw = -(-nd // 64)
    exe = {1: "mitm_nw2", 2: "mitm_nw2", 3: "mitm_nw4", 4: "mitm_nw4", 5: "mitm_nw5", 6: "mitm_nw6"}[nw]
    tb = time.time()
    pending = list(range(len(reps)))
    running, outs = [], []
    found = None
    while pending or running:
        while pending and len(running) < a.procs and found is None:
            o = pending.pop(0)
            running.append((o, subprocess.Popen([str(OUT / exe), str(a.W), a.mode, "2", str(o), str(o)],
                                                stdin=open(inp), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                                text=True)))
        if not running:
            break
        o, p = running.pop(0)
        so, se = p.communicate()
        outs.append((o, [l for l in se.splitlines() if l.startswith("CASE")]))
        sols = [list(map(int, l.split()[2:])) for l in so.splitlines() if l.startswith("SOL")]
        if sols and found is None:
            found = sols[0]
            pending = []
    rec = {"spec": a.name, "basis": a.basis, "R": a.R, "W<=": a.W, "terms": len(keys), "detectors": nd,
           "orbits": len(reps), "translations_verified": len(colperm), "exe": exe,
           "cases": [c for _, cs in sorted(outs) for c in cs], "found": found,
           "nodes_total": sum(int(c.split("nodes=")[1].split()[0]) for _, cs in outs for c in cs),
           "sec_search": round(time.time() - tb, 1), "sec": round(time.time() - t0, 1)}
    if found:
        dd, oo = set(), set()
        for j in found:
            dd ^= set(keys[j])
            oo ^= set(errs[keys[j]])
        rec["found_check"] = {"weight": len(found), "distinct": len(set(found)) == len(found), "dets_zero": not dd,
                              "obs": sorted(oo)}
    jdump(rec, "direct.jsonl")


if __name__ == "__main__":
    main()
