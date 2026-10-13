"""Second and third implementations of the lift test of Lemma 2 (independent of code/gross12/ext.py and CP-SAT).

dp_lift   frontier dynamic programming: the 11 column groups are processed in a greedy order; a state is the XOR of
          the chosen mechanisms' detector bitmasks; a detector that no later group can flip is "closed" and states
          with a closed detector set are discarded.  Enumerates the full product implicitly (exact).
mitm_lift meet in the middle without any solver: enumerate all XORs of one mechanism per column for the columns at
          even and at odd positions (sorted by group size) and intersect the two sets.
Both use their own augmented detector error model (detector bitmasks; image = (H, L) parities of the final data
frame, added as extra observables) and their own extended-code construction (code/sat/common.ext_general from the
CNOT label orders); the circuit and SD6 noise are built by code/gross12 (the object under test).

    python code/lift_independent.py --circuit A --R 1-3 --method dp mitm
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import stim

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_cli import Verdict, circuit, load_code, parse_range     # noqa: E402
from gross12.noise import add_sd6                                    # noqa: E402
from gross12.schedule import build_circuits                          # noqa: E402
from sat.common import BASIS_OF_KIND, ext_general, table, w11_keys  # noqa: E402

KIND_OF_BASIS = {"Z": "X", "X": "Z"}


def label_orders(spec):
    T = table()
    out = {}
    for ty, chk in (("X", spec.x_checks), ("Z", spec.z_checks)):
        lo = []
        for i, c in enumerate(chk):
            _, offs = c.offsets(spec.period)
            inv = {int(T[ty][i][k]): k for k in range(6)}
            lo.append(tuple(inv[col] for _, col in offs))
        out[ty] = lo
    return out


def build_groups(spec, R, basis, E, code):
    circ = add_sd6(build_circuits(spec, code, R)[basis]).flattened()
    H, L = (code.HZ, code.LZ) if basis == "Z" else (code.HX, code.LX)
    n = code.n
    nm = circ.num_measurements
    ops = list(circ)
    idx = max(i for i, op in enumerate(ops) if op.name in ("M", "MX"))
    tq = [t.value for t in ops[idx].targets_copy()]
    assert sorted(tq) == list(range(n))
    pos = {q: nm - n + k for k, q in enumerate(tq)}
    k0 = circ.num_observables
    aug = circ.copy()
    for r_i, row in enumerate(list(H) + list(L)):
        aug.append("OBSERVABLE_INCLUDE", [stim.target_rec(pos[int(q)] - nm) for q in np.nonzero(row)[0]], k0 + r_i)
    key_idx = {E["He"][:, j].tobytes() + E["Le"][:, j].tobytes(): j for j in range(E["N"])}
    dem = aug.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    nH, nL = H.shape[0], L.shape[0]
    groups = {}
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
        assert (ob == lb).all()
        if not hb.any() and not lb.any():
            continue
        key = hb.tobytes() + lb.tobytes()
        assert key in key_idx, "a mechanism's image is not an extended-code column"
        groups.setdefault(key_idx[key], []).append(dm)
    assert len(groups) == E["N"]
    return groups, circ.num_detectors


def dp_lift(S, groups):
    G = [list(dict.fromkeys(groups[j])) for j in S]
    sup = [0] * len(G)
    for i, g in enumerate(G):
        for m in g:
            sup[i] |= m
    order, rem, opened = [], set(range(len(G))), 0
    while rem:
        i = max(rem, key=lambda i: (bin(sup[i] & opened).count("1") - 0.01 * len(G[i]), -i)) if opened else \
            min(rem, key=lambda i: len(G[i]))
        order.append(i); rem.discard(i); opened |= sup[i]
    later = [0] * (len(order) + 1)
    for p in range(len(order) - 1, -1, -1):
        later[p] = later[p + 1] | sup[order[p]]
    layer = {0}
    for p, i in enumerate(order):
        closed = ~later[p + 1]
        nxt = set()
        for s in layer:
            for m in G[i]:
                t = s ^ m
                if not t & closed:
                    nxt.add(t)
        if not nxt:
            return False
        layer = nxt
    return 0 in layer


def mitm_lift(S, groups):
    G = sorted((list(dict.fromkeys(groups[j])) for j in S), key=len)

    def xors(gs):
        acc = {0}
        for g in gs:
            acc = {a ^ m for a in acc for m in g}
        return acc
    a, b = xors(G[0::2]), xors(G[1::2])
    if len(a) > len(b):
        a, b = b, a
    return any(x in b for x in a)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--circuit", default="A")
    ap.add_argument("--basis", nargs="+", default=["Z", "X"])
    ap.add_argument("--R", default="1-3")
    ap.add_argument("--method", nargs="+", default=["dp"], choices=["dp", "mitm"])
    ap.add_argument("--expect", choices=["none", "all"], default=None)
    a = ap.parse_args()
    expect = a.expect or ("all" if a.circuit.startswith("fig12") else "none")
    code = load_code()
    spec = circuit(a.circuit).canonical()
    lo = label_orders(spec)
    V = Verdict()
    for basis in a.basis:
        kind = KIND_OF_BASIS[basis]
        E = ext_general(kind, lo[kind])
        k2j = {E["He"][:, j].tobytes() + E["Le"][:, j].tobytes(): j for j in range(E["N"])}
        lists = [[k2j[k] for k in S] for S in w11_keys(kind)]
        for R in parse_range(a.R):
            groups, nd = build_groups(spec, R, basis, E, code)
            for meth in a.method:
                t0 = time.time()
                f = dp_lift if meth == "dp" else mitm_lift
                hits = [i for i, S in enumerate(lists) if f(S, groups)]
                want = 0 if expect == "none" else len(lists)
                print(json.dumps({"circuit": a.circuit, "basis": basis, "R": R, "method": meth, "lifting": len(hits),
                                  "of": len(lists), "detectors": nd, "sec": round(time.time() - t0, 1)}), flush=True)
                V(len(hits) == want, f"[{meth}] lift circuit {a.circuit} basis {basis} R={R}: {len(hits)}/{len(lists)} "
                                     f"lift (expected {want})")
    V.exit()
