"""E-026 stage B: minimum-weight undetectable logicals of each circuit (per basis), randomized BP-OSD search
(E-016 / arXiv:2603.05481 Eq. 12 style: random eta = aL + bH, solve [H; eta] e = (0, 1)), then closure under the
circuit's spatial translations and time shifts.  Only weights <= wmax are kept.

  uv run python -m search.experiments.e026.enum search --circ p18 --basis Z --trials 400 --seed 26101 --workers 6
  uv run python -m search.experiments.e026.enum close --circ p18 --basis Z

Search runs write results/E-026-gross-ler/enum/<circ>_<basis>_s<seed>.json (raw hits, with per-trial weight list).
"""
from __future__ import annotations

import argparse
import glob
import json
import time
from multiprocessing import get_context

import numpy as np
import scipy.sparse as sp

from search.experiments.e026.common import OUT, DCIRC
from search.experiments.e026.dem import get

RE = 6          # rounds of the enumeration DEM
PE = 1e-3       # priors (only used for the leading-order weights, not for the search)
ENUM = OUT / "enum"


def _search(args):
    circ, basis, seed, trials, wmax, osd_order = args
    from ldpc import BpOsdDecoder
    D = get(circ, basis, RE, PE)
    rng = np.random.default_rng(seed)
    hits, weights = {}, []
    t0 = time.process_time()
    for _ in range(trials):
        a = rng.integers(0, 2, D.Lr.shape[0])
        if not a.any():
            a[rng.integers(D.Lr.shape[0])] = 1
        b = rng.integers(0, 2, D.ndet)
        eta = (np.asarray(a @ D.Lr.toarray()) + np.asarray(b @ D.Hr.toarray())) % 2
        H = sp.vstack([D.Hr, sp.csr_matrix(eta.astype(np.uint8))]).tocsr()
        syn = np.zeros(H.shape[0], np.uint8); syn[-1] = 1
        ch = list(0.01 * np.exp(rng.normal(0, 0.1, D.ncol)))   # near-uniform weights, jitter for diversity
        dec = BpOsdDecoder(H, error_channel=ch, max_iter=100, bp_method="minimum_sum", osd_method="osd_cs",
                           osd_order=osd_order)
        xi = dec.decode(syn)
        cols = tuple(np.nonzero(xi)[0].tolist())
        weights.append(len(cols))
        if len(cols) <= wmax:
            assert D.is_logical(cols)
            hits[cols] = hits.get(cols, 0) + 1
    return {"sols": [list(k) for k in hits], "hits": list(hits.values()), "weights": weights,
            "cpu": time.process_time() - t0}


def cmd_search(a):
    ENUM.mkdir(parents=True, exist_ok=True)
    wmax = DCIRC[a.circ] + 1
    per = max(1, a.trials // a.workers)
    jobs = [(a.circ, a.basis, [a.seed, k], per, wmax, a.osd) for k in range(a.workers)]
    with get_context("spawn").Pool(a.workers) as pool:
        res = pool.map(_search, jobs)
    sols, hits, weights, cpu = {}, {}, [], 0.0
    for r in res:
        for s, h in zip(r["sols"], r["hits"]):
            hits[tuple(s)] = hits.get(tuple(s), 0) + h
        weights += r["weights"]; cpu += r["cpu"]
    out = {"circ": a.circ, "basis": a.basis, "seed": a.seed, "trials": per * a.workers, "osd_order": a.osd,
           "RE": RE, "sols": [list(k) for k in hits], "hits": list(hits.values()),
           "weight_hist": {int(w): int(c) for w, c in zip(*np.unique(weights, return_counts=True))}, "cpu": cpu}
    (ENUM / f"{a.circ}_{a.basis}_s{a.seed}.json").write_text(json.dumps(out))
    print(a.circ, a.basis, "trials", out["trials"], "cpu", round(cpu), "hist", out["weight_hist"],
          "distinct<=wmax", len(hits), flush=True)


def orbit(D, cols, good):
    """all images of a logical under spatial translations `good` and time shifts that keep it inside the DEM."""
    out = set()
    for (a, b) in good:
        for dt in range(-D.R, D.R + 1):
            T = D.translate(cols, a, b, dt)
            if T is not None and D.is_logical(T):
                out.add(T)
    return out


def cmd_close(a):
    D = get(a.circ, a.basis, RE, PE)
    good = D.symmetry()
    files = sorted(glob.glob(str(ENUM / f"{a.circ}_{a.basis}_s*.json")))
    per_seed = {}
    for f in files:
        d = json.loads(open(f).read())
        per_seed[d["seed"]] = [tuple(c) for c in d["sols"]]
    # orbit keys
    okey = {}
    orbits = {}
    for seed, sols in per_seed.items():
        for c in sols:
            if c in okey:
                continue
            O = orbit(D, c, good)
            k = min(O)
            for o in O:
                okey[o] = k
            orbits[k] = O
    # bulk per-round counting: logicals whose min detector round == J0 (and fully inside rounds 1..RE-1)
    J0 = 2
    res = {"circ": a.circ, "basis": a.basis, "symmetry": len(good), "files": [f.split("/")[-1] for f in files]}
    by_w = {}
    for k, O in orbits.items():
        w = len(k)
        bulk = [o for o in O if D.colround[list(o)].min() == J0 and D.colround_max[list(o)].max() <= RE - 1]
        bw = by_w.setdefault(w, {"orbits": 0, "bulk_orbits": 0, "per_round": 0, "lead": []})
        bw["orbits"] += 1
        if bulk:
            bw["bulk_orbits"] += 1
            bw["per_round"] += len(bulk)
    # capture-recapture on bulk orbits between seed groups (first half vs second half of seeds)
    seeds = sorted(per_seed)
    half = len(seeds) // 2
    if half >= 1:
        for w in by_w:
            A = {okey[c] for s in seeds[:half] for c in per_seed[s] if len(c) == w}
            B = {okey[c] for s in seeds[half:] for c in per_seed[s] if len(c) == w}
            by_w[w]["LP"] = {"nA": len(A), "nB": len(B), "both": len(A & B),
                             "N_LP": (len(A) * len(B) / len(A & B)) if A & B else None}
    res["by_w"] = {int(w): {k: v for k, v in d.items() if k != "lead"} for w, d in sorted(by_w.items())}
    (ENUM / f"close_{a.circ}_{a.basis}.json").write_text(json.dumps(res, indent=1))
    # save bulk logicals (for leading-order and kernels)
    bl = [list(o) for O in orbits.values() for o in O
          if D.colround[list(o)].min() == J0 and D.colround_max[list(o)].max() <= RE - 1]
    (ENUM / f"bulk_{a.circ}_{a.basis}.json").write_text(json.dumps(bl))
    print(json.dumps(res["by_w"]), "symmetry", len(good), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("--circ", required=True)
    ap.add_argument("--basis", default="Z")
    ap.add_argument("--trials", type=int, default=600)
    ap.add_argument("--seed", type=int, default=26101)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--osd", type=int, default=10)
    a = ap.parse_args()
    assert a.workers <= 6
    {"search": cmd_search, "close": cmd_close}[a.cmd](a)


if __name__ == "__main__":
    main()
