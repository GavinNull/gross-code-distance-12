"""E-021 step 3: exact lift checker for ARBITRARY per-check CNOT orders (generalises e018/lift.py, whose argument
is unchanged; audit 2026-10-08 B).  Requires d_ext >= 11 for the circuit's orders on the kind being checked
(complete W=10 DFS, extgen.ext_dfs) -- then a weight-11 undetected logical maps to 11 distinct non-zero columns
forming a weight-11 extended logical, and the augmented-observable DP over the complete weight-11 list is exact.

Circuits: non-wrapping symmetric frames from nwsat (class-label ranks) -> evaluator ScheduleSpec (period = items+2,
prep 0, CNOT at rank+1, meas period-1), or any qec-schedule/v1 JSON.

    PYTHONPATH=.:tests uv run python -m search.experiments.e021.lift21 --cand results/.../nwd_<tag>.json --R 1 2 3
"""
from __future__ import annotations

import argparse
import json
import pickle
import time
from pathlib import Path

import numpy as np
import stim

from evaluators.candidate import build_circuits, parse_schedule
from evaluators.noise import add_noise
from search.experiments.e018.common import css
from search.experiments.e018.lift import solve
from search.experiments.e021.extgen import ext_dfs, ext_general, expand
from search.experiments.e021.mono import table

OUT = Path("results/E-021-gross-new-orders")
KIND_OF_BASIS = {"Z": "X", "X": "Z"}
N2 = 72


def spec_from_ranks(cls, rank, items, nitems):
    """cls: class of each row (same for X, Z); rank[item index]; items list of (ty, class, label)."""
    T = table()
    P = nitems + 2
    idx = {it: n for n, it in enumerate(items)}
    d = {"format": "qec-schedule/v1", "period": P, "x_checks": [], "z_checks": []}
    for ty, key in (("X", "x_checks"), ("Z", "z_checks")):
        for i in range(N2):
            cn = [[int(T[ty][i][lab]), int(rank[idx[(ty, cls[i], lab)]]) + 1] for lab in range(6)]
            d[key].append({"prep": 0, "meas": P - 1, "cnots": cn})
    return d


def label_orders(spec):
    """per-check label orders read from a ScheduleSpec (offsets from prep)."""
    T = table()
    D = spec.period
    out = {}
    for ty, chk in (("X", spec.x_checks), ("Z", spec.z_checks)):
        lo = []
        for i, c in enumerate(chk):
            _, offs = c.offsets(D)
            inv = {int(T[ty][i][k]): k for k in range(6)}
            lo.append(tuple(inv[col] for _, col in offs))
        out[ty] = lo
    return out


def augmented(spec, R, basis, E):
    c = css()
    circ = add_noise(build_circuits(spec, c, R)[basis], "sd6", 1e-3).flattened()
    H, L = (np.asarray(c.HZ) % 2, np.asarray(c.LZ) % 2) if basis == "Z" else (np.asarray(c.HX) % 2, np.asarray(c.LX) % 2)
    n = c.n
    nm = circ.num_measurements
    ops = list(circ)
    idx = max(i for i, op in enumerate(ops) if op.name in ("M", "MX", "MZ", "MR", "MRX"))
    last = ops[idx]
    tq = [t.value for t in last.targets_copy()]
    assert sorted(tq) == list(range(n)) and last.name == ("M" if basis == "Z" else "MX")
    pos = {q: nm - n + k for k, q in enumerate(tq)}
    k0 = circ.num_observables
    aug = circ.copy()
    rows = [H[i] for i in range(H.shape[0])] + [L[i] for i in range(L.shape[0])]
    for r_i, row in enumerate(rows):
        aug.append("OBSERVABLE_INCLUDE", [stim.target_rec(pos[q] - nm) for q in np.nonzero(row)[0]], k0 + r_i)
    return circ, aug, H, L, k0


def build_groups(spec, R, basis, E):
    circ, aug, H, L, k0 = augmented(spec, R, basis, E)
    key_idx = {E["He"][:, j].tobytes() + E["Le"][:, j].tobytes(): j for j in range(E["N"])}
    dem = aug.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    nH, nL = H.shape[0], L.shape[0]
    groups, nterms, nzero = {}, 0, 0
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
        assert (ob == lb).all()
        if not hb.any() and not lb.any():
            nzero += 1; continue
        key = hb.tobytes() + lb.tobytes()
        assert key in key_idx, "Table I violated"
        groups.setdefault(key_idx[key], []).append(dm)
    assert len(groups) == E["N"], "not every extended column is realised"
    return groups, {"aug_terms": nterms, "zero_image": nzero, "detectors": circ.num_detectors}


def w11_list(kind, lab, workers=4, tag=""):
    """complete weight-<=11 enumeration (orbit-expanded), cached; asserts d_ext >= 11 (no weight <= 10)."""
    f = OUT / f"w11_{tag}_{kind}.pkl"
    if f.exists():
        return pickle.load(open(f, "rb"))
    E = ext_general(kind, lab)
    s10, n10, c10 = ext_dfs(kind, lab, 10, stopfirst=1, workers=workers, E=E)
    assert not s10 and c10, "d_ext <= 10"
    sols, nodes, complete = ext_dfs(kind, lab, 11, stopfirst=0, workers=workers, E=E)
    assert complete
    allS = expand(E, sols)
    pickle.dump(allS, open(f, "wb"))
    return allS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", required=True, help="nwsat json with candidate_rank, or a qec-schedule json")
    ap.add_argument("--R", type=int, nargs="+", default=[2])
    ap.add_argument("--bases", default="ZX")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    d = json.loads(Path(a.cand).read_text())
    if "candidate_rank" in d:
        from search.experiments.e021.nwsat import Family, parse_sub
        gens = [(1, 0), (0, 1)] if d["sub"] == "all" else parse_sub(d["sub"])
        F = Family(gens)
        sd = spec_from_ranks(F.cls, d["candidate_rank"], F.items, len(F.items))
    else:
        sd = d
    tag = a.tag or Path(a.cand).stem
    (OUT / f"spec_{tag}.json").write_text(json.dumps(sd))
    spec = parse_schedule(sd).canonical()
    lo = label_orders(spec)
    res = {"cand": a.cand, "period": spec.period, "per": []}
    for basis in a.bases:
        kind = KIND_OF_BASIS[basis]
        t0 = time.time()
        sols = w11_list(kind, lo[kind], a.workers, tag)
        E = ext_general(kind, lo[kind])
        print(f"{kind}: {len(sols)} weight-11 extended logicals ({time.time() - t0:.0f}s)", flush=True)
        for R in a.R:
            t1 = time.time()
            groups, st = build_groups(spec, R, basis, E)
            hits = []
            for S in sols:
                ch, _ = solve(S, groups)
                if ch is not None:
                    hits.append(list(S))
            rec = {"R": R, "basis": basis, "kind": kind, "num": len(sols), "lifting": len(hits), **st,
                   "sec": round(time.time() - t1, 1), "hits": hits[:200]}
            print(f"R={R} basis {basis}: lifting {len(hits)}/{len(sols)} {st} {rec['sec']}s", flush=True)
            res["per"].append(rec)
            (OUT / f"lift_{tag}.json").write_text(json.dumps(res))


if __name__ == "__main__":
    main()
