"""E-028: exact lift for [[90,8,10]] circuits (port of e021/lift21.build_groups + label_orders; DP = e018/lift.solve,
audited 2026-10-08 B; argument = template identity + Table I, audit 2026-10-10).

If a side's extended code has d_ext = 9 (no weight <= 8, complete DFS) then any undetected circuit logical of weight 9
has 9 distinct non-zero images forming a weight-9 extended logical; so with the complete weight-9 list, "0 of the list
lifts at R" <=> "no undetected logical of weight <= 9 at R" for that memory basis.

The augmented DEM adds observables = (H rows, L rows) on the final data readout; each DEM term's image key must be 0 or
an extended column key (Table I, asserted), and every extended column must be realised.
"""
from __future__ import annotations

import json

import numpy as np
import stim

from evaluators.candidate import build_circuits, parse_schedule
from evaluators.noise import add_noise
from search.experiments.e018.lift import solve
from search.experiments.e028 import common as C

KIND_OF_BASIS = {"Z": "X", "X": "Z"}


def label_orders(spec):
    T = C.table()
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


def augmented(spec, R, basis):
    c = C.css()
    circ = add_noise(build_circuits(spec, c, R)[basis], "sd6", 1e-3).flattened()
    H, L = C.HLk(KIND_OF_BASIS[basis])
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


def build_groups(spec, R, basis, E, zeros=None):
    circ, aug, H, L, k0 = augmented(spec, R, basis)
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
            nzero += 1
            if zeros is not None and dm:
                zeros.add(dm)
            continue
        key = hb.tobytes() + lb.tobytes()
        assert key in key_idx, "Table I violated"
        groups.setdefault(key_idx[key], []).append(dm)
    assert len(groups) == E["N"], "not every extended column is realised"
    return groups, {"aug_terms": nterms, "zero_image": nzero, "detectors": circ.num_detectors}


def reindex(E, keylist):
    k2j = {E["He"][:, j].tobytes() + E["Le"][:, j].tobytes(): j for j in range(E["N"])}
    allk = {k for S in keylist for k in S}
    assert allk <= set(k2j), "list column not in this circuit's extended code"
    return [tuple(sorted(k2j[k] for k in S)) for S in keylist], frozenset(k2j)


def lift_screen(spec_d, lists, colsets, rmax=6, rlist=None, stop_first=True, bases="ZX"):
    """lists[kind] = list of key tuples (complete weight-9 list), colsets[kind] = the class's column key set."""
    spec = parse_schedule(spec_d).canonical()
    lo = label_orders(spec)
    Es, sols = {}, {}
    for b in bases:
        k = KIND_OF_BASIS[b]
        Es[b] = C.ext_general(k, lo[k], group=[(0, 0)])
        sols[b], cs = reindex(Es[b], lists[k])
        assert cs == colsets[k], "circuit's extended code differs from the class"
    per = []
    for R in (rlist or range(1, rmax + 1)):
        for b in bases:
            try:
                groups, st = build_groups(spec, R, b, Es[b])
            except Exception as e:  # noqa: BLE001
                return {"status": "error", "err": str(e)[:300]}
            n = 0
            for S in sols[b]:
                if solve(S, groups)[0] is not None:
                    n += 1
                    if stop_first:
                        break
            per.append({"R": R, "basis": b, "lifting": n, "num": len(sols[b])})
            if n and stop_first:
                return {"status": "lifts", "R": R, "basis": b, "per": per}
    st = "CERTIFIED" if all(p["lifting"] == 0 for p in per) else "lifts"
    return {"status": st, "per": per}
