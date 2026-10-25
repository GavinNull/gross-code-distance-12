"""E-036 step 5a: exhaustive enumeration of the uniform (translation-invariant timing) single-ancilla family.

Family U(S, mode): every X check uses the same term->slot map, every Z check the same term->slot map, CNOT slots
1..S.  mode nowrap: all checks prep at layer 0 and measure at layer S+1 (period S+2; the Kunlun circuit is
U(7, nowrap) with the IBM slot maps).  Filters (exact, all algebraic): (i) no data qubit used twice in a slot
(over the measured checks of the variant); (ii) determinism: for every (X check, Z check) pair, the number of
shared data qubits on which the X CNOT precedes the Z CNOT is even.  Survivors are evaluated exactly on the full
SD6 DEM (meet-in-the-middle, all weights <= d-1) at R = 1, then R = 1..Rchk for those that pass.
Equivalences are NOT quotiented (every map is enumerated).
"""
import argparse
import itertools
import json
import time

import numpy as np

from search.experiments.e036.common import (OUT, TERMS, checks, code, dem_mechs, min_weight, sd6, spec_from_terms,
                                            term_col)


def setup(variant):
    xs, zs = checks(variant)
    # collision table: X term t and Z term u in the same slot
    coll = np.zeros((6, 6), bool)
    for t in range(6):
        dx = {term_col("X", c, t) for c in xs}
        for u in range(6):
            dz = {term_col("Z", c, u) for c in zs}
            coll[t, u] = bool(dx & dz)
    # determinism pairs: list of (t,u) per (X check, Z check) with shared qubit q = X term t = Z term u
    pairs = []
    for i in xs:
        sx = {term_col("X", i, t): t for t in range(6)}
        for j in zs:
            sz = {term_col("Z", j, u): u for u in range(6)}
            sh = [(sx[q], sz[q]) for q in sx if q in sz]
            if sh:
                pairs.append(sh)
    return coll, pairs


def assignments(S):
    """all injective maps term -> slot in 1..S, as arrays of times (len 6)."""
    return np.array([p for p in itertools.permutations(range(1, S + 1), 6)], np.int16)


def survivors(variant, S):
    coll, pairs = setup(variant)
    A = assignments(S)  # (NA, 6)
    NA = len(A)
    # slot occupancy matrix: occ[a, s] = term index at slot s or -1
    occ = -np.ones((NA, S + 1), np.int16)
    for t in range(6):
        occ[np.arange(NA), A[:, t]] = t
    out = []
    for ia in range(NA):
        xt = A[ia]
        ok = np.ones(NA, bool)
        for s in range(1, S + 1):
            t = occ[ia, s]
            if t < 0:
                continue
            zu = occ[:, s]
            m = zu >= 0
            bad = np.zeros(NA, bool)
            bad[m] = coll[t, zu[m]]
            ok &= ~bad
        if not ok.any():
            continue
        idx = np.nonzero(ok)[0]
        Z = A[idx]
        par_ok = np.ones(len(idx), bool)
        for sh in pairs:
            par = np.zeros(len(idx), np.int8)
            for (t, u) in sh:
                par ^= (xt[t] < Z[:, u]).astype(np.int8)
            par_ok &= par == 0
        for j in idx[par_ok]:
            out.append((ia, int(j)))
    return A, out


def evaluate(variant, S, xt, zt, Rs, dtarget, bases=("Z", "X")):
    spec = spec_from_terms(variant, list(map(int, xt)), list(map(int, zt)), S + 2, 0, S + 1, 0, S + 1)
    best = 99
    for R in Rs:
        for b in bases:
            mechs, _ = dem_mechs(sd6(spec, variant, b, R))
            w, _ = min_weight(mechs, dtarget - 1)
            if w is not None:
                return w, spec
    return None, spec


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("variant")
    ap.add_argument("S", type=int)
    ap.add_argument("--d", type=int, default=4)
    ap.add_argument("--rchk", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--shard", default="0/1")
    a = ap.parse_args()
    t0 = time.time()
    A, surv = survivors(a.variant, a.S)
    k, K = map(int, a.shard.split("/"))
    surv_k = surv[k::K]
    print(json.dumps({"variant": a.variant, "S": a.S, "n_maps": len(A), "n_legal_det": len(surv), "shard": a.shard,
                      "sec": round(time.time() - t0, 1)}), flush=True)
    hist = {}
    good = []
    for n, (ia, iz) in enumerate(surv_k):
        if a.limit and n >= a.limit:
            break
        w, spec = evaluate(a.variant, a.S, A[ia], A[iz], [1], a.d)
        if w is None:
            w2, _ = evaluate(a.variant, a.S, A[ia], A[iz], list(range(2, a.rchk + 1)), a.d)
            w = w2
        key = str(w if w is not None else f">={a.d}")
        hist[key] = hist.get(key, 0) + 1
        if w is None:
            rec = {"X": "".join(f"{TERMS[t]}@{A[ia][t]}" for t in np.argsort(A[ia])),
                   "Z": "".join(f"{TERMS[t]}@{A[iz][t]}" for t in np.argsort(A[iz])),
                   "xt": A[ia].tolist(), "zt": A[iz].tolist()}
            good.append(rec)
            print(json.dumps(rec), flush=True)
    res = {"variant": a.variant, "S": a.S, "period": a.S + 2, "n_legal_det": len(surv), "shard": a.shard,
           "evaluated": sum(hist.values()), "hist_min_w": hist, "n_good": len(good), "sec": round(time.time() - t0, 1)}
    print(json.dumps(res), flush=True)
    (OUT / f"uniform_{a.variant}_S{a.S}_{k}of{K}.json").write_text(json.dumps({"summary": res, "good": good}, indent=1))
