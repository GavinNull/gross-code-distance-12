"""E-023 stage S: low-weight undetectable logical errors of a sector (random BP-OSD search, arXiv:2603.05481 Eq. 12,
as E-016 lowweight.py: random eta = aL + bH, solve [H; eta] e = (0..0, 1) with BP-OSD-CS, keep weight <= wmax).
Half the trials use uniform channel (error_rate 0.01), half the prior-weighted channel (priors scaled to mean 0.01),
as E-016 found the unweighted search under-samples high-prior logicals.  The DEM column set is the same for SD6 and
SI1000 (same fault locations), so the search runs on the SD6 sector and logicals are reused for SI1000 via keys.

Saturation is monitored by splitting trials into chunks and recording how many new logicals each chunk adds.

    PYTHONPATH=. uv run python -m search.experiments.e023.lowweight --prob m54_paper --trials 20000 --wmax 8
"""
from __future__ import annotations

import argparse
import json
import time
from multiprocessing import get_context

import numpy as np
import scipy.sparse as sp

from search.experiments.e023.common import OUT, P_DEC, sectors


def search(args):
    prob, si, trials, seed, wmax = args
    from ldpc import BpOsdDecoder
    sec = sectors(prob, "sd6", P_DEC)[si]
    D = sec.H.tocsr().astype(np.uint8)
    Lm = sec.L.tocsr().astype(np.uint8)
    rng = np.random.default_rng(seed)
    sols = {}
    t0 = time.process_time()
    ch = list(np.minimum(sec.q * (0.01 / sec.q.mean()), 0.4))
    for it in range(trials):
        a = rng.integers(0, 2, Lm.shape[0])
        if not a.any():
            a[rng.integers(Lm.shape[0])] = 1
        b = rng.integers(0, 2, D.shape[0])
        eta = ((a @ Lm) + (b @ D)) % 2
        H = sp.vstack([D, sp.csr_matrix(eta.astype(np.uint8))]).tocsr()
        syn = np.zeros(H.shape[0], dtype=np.uint8)
        syn[-1] = 1
        if it % 2:
            dec = BpOsdDecoder(H, error_channel=ch, max_iter=100, bp_method="minimum_sum", osd_method="osd_cs",
                               osd_order=10)
        else:
            dec = BpOsdDecoder(H, error_rate=0.01, max_iter=100, bp_method="minimum_sum", osd_method="osd_cs",
                               osd_order=10)
        xi = dec.decode(syn)
        cols = tuple(np.nonzero(xi)[0].tolist())
        assert not ((D @ xi) % 2).any() and ((Lm @ xi) % 2).any()
        if len(cols) <= wmax:
            sols[cols] = sols.get(cols, 0) + 1
    return prob, si, seed, {"sols": [list(k) for k in sols], "cpu": time.process_time() - t0}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--prob", required=True)
    ap.add_argument("--trials", type=int, default=20000)
    ap.add_argument("--chunks", type=int, default=12)
    ap.add_argument("--wmax", type=int, default=8)
    ap.add_argument("--seed", type=int, default=23001)
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args(argv)
    assert a.workers <= 3
    secs = sectors(a.prob, "sd6", P_DEC)
    path = OUT / "lowweight" / f"{a.prob}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    old = json.loads(path.read_text()) if path.exists() else {"sectors": {}, "runs": []}
    jobs = [(a.prob, si, a.trials // a.chunks, a.seed * 1000 + 100 * si + c, a.wmax)
            for si in range(len(secs)) for c in range(a.chunks)]
    t0 = time.time()
    cpu = 0.0
    with get_context("spawn").Pool(a.workers) as pool:
        res = pool.map(search, jobs)
    for prob, si, seed, r in res:
        lab = secs[si].label
        cur = old["sectors"].setdefault(lab, {"logicals": [], "keys": None, "new_per_chunk": []})
        have = set(map(tuple, cur["logicals"]))
        new = [tuple(s) for s in r["sols"] if tuple(s) not in have]
        cur["new_per_chunk"].append(len(set(new)))
        have |= set(new)
        cur["logicals"] = sorted(map(list, have), key=lambda s: (len(s), s))
        cpu += r["cpu"]
    for si, s in enumerate(secs):
        cur = old["sectors"][s.label]
        cur["keys"] = [[list(k[0]), list(k[1])] for k in s.keys]
        ws = {}
        for L in cur["logicals"]:
            ws[len(L)] = ws.get(len(L), 0) + 1
        cur["count_by_weight"] = {str(k): v for k, v in sorted(ws.items())}
        print(a.prob, s.label, "by weight", cur["count_by_weight"], "new per chunk", cur["new_per_chunk"][-a.chunks:])
    old["runs"].append(dict(trials=a.trials, chunks=a.chunks, wmax=a.wmax, seed=a.seed, cpu=cpu,
                            wall=time.time() - t0))
    path.write_text(json.dumps(old))
    print(f"cpu {cpu:.0f}s wall {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()


# ------------------------------------------------------------------ symmetry closure
def loc_maps(prob, model="sd6", p=P_DEC):
    """For each sector: dict circuit-error-location key -> sector column (via stim explain, all locations)."""
    from search.experiments.e023.common import noisy_circuits
    out = []
    secs = sectors(prob, model, p)
    for (label, c, dr, orr), sec in zip(noisy_circuits(prob, model, p), secs):
        d0, d1 = dr if dr else (0, c.num_detectors)
        o0, o1 = orr if orr else (0, c.num_observables)
        kidx = {k: j for j, k in enumerate(sec.keys)}
        ex = c.explain_detector_error_model_errors(reduce_to_one_representative_error=False)
        m = {}
        for e in ex:
            ds, os_ = set(), set()
            for t in e.dem_error_terms:
                dt = t.dem_target
                if dt.is_relative_detector_id() and d0 <= dt.val < d1:
                    ds ^= {dt.val - d0}
                elif dt.is_logical_observable_id() and o0 <= dt.val < o1:
                    os_ ^= {dt.val - o0}
            j = kidx.get((tuple(sorted(ds)), tuple(sorted(os_))), -1)
            for loc in e.circuit_error_locations:
                key = (loc.tick_offset, loc.instruction_targets.gate,
                       tuple(sorted((g.gate_target.value, "X" if g.gate_target.is_x_target else
                                     "Y" if g.gate_target.is_y_target else "Z" if g.gate_target.is_z_target else "M")
                                    for g in loc.flipped_pauli_product)),
                       tuple(sorted(t.gate_target.value for t in loc.instruction_targets.targets_in_range)),
                       None if loc.flipped_measurement is None else loc.flipped_measurement.measurement_record_index)
                m[key] = j
        out.append(m)
    return secs, out


def morph_perms(prob, model="sd6"):
    """Column permutations of each sector induced by circuit translations (s, dr): qubits translated by s in Z_l x Z_m,
    ticks shifted by 8*dr (8 layers per morphing round), measurement record index shifted by N*dr.  Only maps under
    which >= 90% of columns map are kept (interior symmetries; boundary columns map to -1)."""
    from search.experiments.e019.common import get_code
    from search.experiments.e023.common import PROBLEMS
    P = PROBLEMS[prob]
    code = get_code(P["key"].split("_")[0])
    N = code.N
    secs, maps = loc_maps(prob, model)
    res = []
    for sec, m in zip(secs, maps):
        perms = []
        for i in range(code.l):
            for j in range(code.m):
                for dr in range(-P["T"] + 1, P["T"]):
                    s = (i, j)
                    perm = np.full(sec.ncol, -1, np.int64)
                    for key, col in m.items():
                        if col < 0 or perm[col] >= 0:
                            continue
                        tick, gate, paul, targs, mrec = key
                        k2 = (tick + 8 * dr, gate,
                              tuple(sorted((code.translate_q(q, s), pp) for q, pp in paul)),
                              tuple(sorted(code.translate_q(q, s) for q in targs)),
                              None if mrec is None else mrec + N * dr)
                        c2 = m.get(k2)
                        if c2 is not None and c2 >= 0:
                            perm[col] = c2
                    frac = float((perm >= 0).mean())
                    if frac > 0.6 and (i, j, dr) != (0, 0, 0):
                        perms.append(((i, j, dr), frac, perm))
        res.append(perms)
    return secs, res


def close(sec, logicals, perms, rounds=6):
    H = sec.H.tocsc()
    L = sec.L.tocsc()
    have = set(tuple(sorted(x)) for x in logicals)
    frontier = list(have)
    for _ in range(rounds):
        new = []
        for S in frontier:
            for (_, _, perm) in perms:
                T = perm[list(S)]
                if (T < 0).any():
                    continue
                T = tuple(sorted(T.tolist()))
                if T in have or len(set(T)) != len(S):
                    continue
                e = np.zeros(sec.ncol, np.uint8)
                e[list(T)] = 1
                if ((H @ e) % 2).any() or not ((L @ e) % 2).any():
                    continue
                have.add(T)
                new.append(T)
        if not new:
            break
        frontier = new
    return have


def closure_main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--prob", required=True)
    ap.add_argument("--wmax", type=int, default=8)
    a = ap.parse_args(argv)
    path = OUT / "lowweight" / f"{a.prob}.json"
    D = json.loads(path.read_text())
    t0 = time.process_time()
    secs, permsets = morph_perms(a.prob)
    for sec, perms in zip(secs, permsets):
        cur = D["sectors"][sec.label]
        good = perms   # all maps with >60% columns mapped; each image is re-verified as a logical
        base = [L for L in cur["logicals"] if len(L) <= a.wmax]
        cl = close(sec, base, good)
        cur["closed"] = sorted(map(list, cl), key=lambda s: (len(s), s))
        ws = {}
        for L in cl:
            ws[len(L)] = ws.get(len(L), 0) + 1
        cur["closed_count_by_weight"] = {str(k): v for k, v in sorted(ws.items())}
        cur["symmetries_used"] = [[list(x[0]), x[1]] for x in good]
        print(a.prob, sec.label, "symmetries", len(good), "of", len(perms), "found", cur["count_by_weight"],
              "closed", cur["closed_count_by_weight"])
    D.setdefault("closure_cpu", []).append(time.process_time() - t0)
    path.write_text(json.dumps(D))
