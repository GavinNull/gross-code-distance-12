"""E-018 stage b: exact decision "does circuit C (gross code, single ancilla, Fig. 12 per-check CNOT orders) have an
undetected logical of weight 11 = d_ext at R rounds?"  0 hits over both memory bases => d_circ >= 12 at that R.

Argument (generalises search/experiments/e015/ibm_lift.py; audit 2026-10-05 B7).  Memory basis Z (X symmetric):
detectors are Z-check comparisons + final data readout, so for a fault set F the product of all detectors of check i
is row i of H_Z applied to x_F = sum_f x_f, the end-of-circuit data X part ("image") of the faults.
 (T1) every single fault has image 0 or exactly one extended-code column (checked here on every circuit: assertion
      `table1`), because the per-check CNOT orders are those of Fig. 12;
 (P3) hence d_circ >= d_ext = 11 (Prop. 3), and if F is an undetected logical with |F| = 11 the images are 11 distinct
      nonzero columns forming a weight-11 extended logical S (otherwise cancelling equal pairs / dropping zeros
      leaves an extended logical of weight <= 10, which E-014 proved does not exist).
So it suffices, for every weight-11 extended logical S (stage a), to decide whether one can pick for each column
j in S a fault with image j such that the detectors cancel (the observable flip is then automatic: the observable
is L x_F = L S != 0).

Implementation (no need to treat "DEM terms with several images" separately): the evaluator's noisy circuit is
augmented with extra observables = the parities of H rows and L rows on the final data readout, i.e. exactly the
image key (H x_f, L x_f) of each fault.  stim's DEM of the augmented circuit therefore has one error per distinct
(detectors, image) pair; locations of one original DEM term with different images become different augmented
terms.  A fault set F of the kind above maps to 11 augmented terms, one per column group, automatically distinct
(groups are disjoint); conversely any choice of one augmented term per column with zero detector XOR is realised
by 11 distinct circuit faults, i.e. it is a genuine undetected logical of weight <= 11 (and of weight exactly 11 in
original DEM terms, since d_circ >= 11).  Therefore hits are genuine and the search is complete.  (T1) is checked on
the augmented DEM: every error's image key is 0 or a column key.  The evaluator's own observables are checked to
equal the L part of the image.

Exact search per S: frontier dynamic programming over the 11 groups (order chosen greedily), states = XOR of chosen
detector masks; a detector is "closed" once no later group can flip it, and states with a closed detector set are
discarded.  This enumerates the full product implicitly (exact).  Back-pointers give a witness.

    PYTHONPATH=.:tests uv run python -m search.experiments.e018.lift --schedule fig12 --R 1 2 3
    PYTHONPATH=.:tests uv run python -m search.experiments.e018.lift --schedule path/to/cand.json --R 1 2
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import stim

from evaluators.candidate import build_circuits, parse_schedule
from evaluators.noise import add_noise
from search.experiments.e018.common import OUT, css, ext, fig12, load_logicals, orders

KIND_OF_BASIS = {"Z": "X", "X": "Z"}   # Z-basis memory sees X errors = X-check hooks = ext code "X"


def spec_of(arg):
    if arg == "fig12":
        import sys
        sys.path.insert(0, "tests")
        from schedule_helpers import from_baseline
        return parse_schedule(from_baseline(fig12()[0]))
    return parse_schedule(json.loads(Path(arg).read_text()))


def check_orders(spec):
    """The candidate must keep Fig. 12's per-check CNOT orders (then its extended code is E-014's)."""
    xo, zo = orders()
    D = spec.period
    for chk, ref in ((spec.x_checks, xo), (spec.z_checks, zo)):
        for i, c in enumerate(chk):
            _, offs = c.offsets(D)
            assert [col for _, col in offs] == list(ref[i]), f"check {i}: CNOT order differs from Fig. 12"


def augmented(spec, R, basis):
    c = css()
    circ = add_noise(build_circuits(spec, c, R)[basis], "sd6", 1e-3).flattened()
    kind = KIND_OF_BASIS[basis]
    E = ext(kind)
    H, L = (np.asarray(c.HZ) % 2, np.asarray(c.LZ) % 2) if basis == "Z" else (np.asarray(c.HX) % 2, np.asarray(c.LX) % 2)
    n = c.n
    # locate the final data readout: last measurement instruction, must target data 0..n-1 in some order
    nm = circ.num_measurements
    ops = list(circ)
    idx = max(i for i, op in enumerate(ops) if op.name in ("M", "MX", "MZ", "MR", "MRX"))
    last = ops[idx]
    tq = [t.value for t in last.targets_copy()]
    assert sorted(tq) == list(range(n)) and last.name == ("M" if basis == "Z" else "MX"), (last.name, len(tq))
    after = sum(len(op.targets_copy()) for op in ops[idx + 1:] if op.name.startswith("M"))
    assert after == 0
    pos = {q: nm - n + k for k, q in enumerate(tq)}      # absolute record index of data q
    k0 = circ.num_observables
    aug = circ.copy()
    rows = [H[i] for i in range(H.shape[0])] + [L[i] for i in range(L.shape[0])]
    for r_i, row in enumerate(rows):
        tg = [stim.target_rec(pos[q] - nm) for q in np.nonzero(row)[0]]
        aug.append("OBSERVABLE_INCLUDE", tg, k0 + r_i)
    return circ, aug, E, H, L, k0


def build_groups(spec, R, basis):
    circ, aug, E, H, L, k0 = augmented(spec, R, basis)
    dem = aug.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    nH, nL = H.shape[0], L.shape[0]
    key_idx = E["key_idx"]
    groups = {}
    nterms = nzero = 0
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        dm = 0
        hb = np.zeros(nH, np.uint8); lb = np.zeros(nL, np.uint8); ob = np.zeros(k0, np.uint8)
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                dm ^= 1 << t.val
            elif t.is_logical_observable_id():
                v = t.val
                if v < k0:
                    ob[v] ^= 1
                elif v < k0 + nH:
                    hb[v - k0] ^= 1
                else:
                    lb[v - k0 - nH] ^= 1
        nterms += 1
        assert (ob == lb).all(), "evaluator observable != L part of the image (logical basis mismatch)"
        if not hb.any() and not lb.any():
            nzero += 1
            continue
        key = hb.tobytes() + lb.tobytes()
        assert key in key_idx, "Table I violated: a fault's image is not 0 and not a single extended column"
        groups.setdefault(key_idx[key], []).append(dm)
    stats = {"aug_terms": nterms, "zero_image": nzero, "columns_realised": len(groups),
             "N": len(E["keys"]), "orig_dem_errors": circ.detector_error_model(decompose_errors=False).num_errors,
             "detectors": circ.num_detectors}
    assert len(groups) == len(E["keys"]), "not every extended column is realised"
    return groups, stats, circ, aug


def solve(S, groups):
    """Exact: is there a choice of one mask per group (columns of S) with XOR 0?  Returns list of chosen masks or None."""
    G = [list(dict.fromkeys(groups[j])) for j in S]
    sup = [0] * len(G)
    for i, g in enumerate(G):
        for m in g:
            sup[i] |= m
    # greedy order: start with the smallest group, then maximise overlap with what is open
    order, rem, opened = [], set(range(len(G))), 0
    while rem:
        i = max(rem, key=lambda i: (bin(sup[i] & opened).count("1") - 0.01 * len(G[i]), -i)) if opened else \
            min(rem, key=lambda i: len(G[i]))
        order.append(i); rem.discard(i); opened |= sup[i]
    later = [0] * (len(order) + 1)
    for p in range(len(order) - 1, -1, -1):
        later[p] = later[p + 1] | sup[order[p]]
    layers = [{0: None}]
    for p, i in enumerate(order):
        closed_mask = ~later[p + 1]
        nxt = {}
        for s in layers[-1]:
            for m in G[i]:
                t = s ^ m
                if t & closed_mask:
                    continue
                if t not in nxt:
                    nxt[t] = (s, m)
        if not nxt:
            return None, max(len(x) for x in layers)
        layers.append(nxt)
    assert 0 in layers[-1]
    # back-track a witness
    chosen, s = {}, 0
    for p in range(len(order), 0, -1):
        prev, m = layers[p][s]
        chosen[S[order[p - 1]]] = m
        s = prev
    return chosen, max(len(x) for x in layers)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--schedule", default="fig12")
    ap.add_argument("--R", type=int, nargs="+", default=[1])
    ap.add_argument("--bases", default="ZX")
    ap.add_argument("--logicals", default="all", help="all | prelim")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--max_hits", type=int, default=10 ** 9)
    a = ap.parse_args()
    spec = spec_of(a.schedule).canonical()
    check_orders(spec)
    tag = a.tag or Path(a.schedule).stem
    res = {"schedule": a.schedule, "per": []}
    outp = OUT / f"lift_{tag}.json"
    for R in a.R:
        for basis in a.bases:
            t0 = time.time()
            kind = KIND_OF_BASIS[basis]
            import pickle
            sols = pickle.load(open(OUT / f"w11_{a.logicals}_{kind}.pkl", "rb"))
            groups, stats, circ, aug = build_groups(spec, R, basis)
            hits, maxfront = [], 0
            for S in sols:
                ch, mf = solve(S, groups)
                maxfront = max(maxfront, mf)
                if ch is not None:
                    hits.append({"S": list(S), "masks": {int(k): int(v) for k, v in ch.items()}})
                    if len(hits) >= a.max_hits:
                        break
            gs = [len(set(v)) for v in groups.values()]
            rec = {"R": R, "basis": basis, "kind": kind, "num_logicals": len(sols), "lifting": len(hits),
                   "group_size_min_max_mean": [min(gs), max(gs), round(float(np.mean(gs)), 2)],
                   "max_frontier": maxfront, **stats, "sec": round(time.time() - t0, 1),
                   "hits": hits}
            print(f"R={R} {basis}: lifting {len(hits)}/{len(sols)}  groups {rec['group_size_min_max_mean']} "
                  f"frontier {maxfront} {stats} {rec['sec']}s", flush=True)
            res["per"].append(rec)
            outp.write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
