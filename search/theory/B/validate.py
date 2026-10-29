"""Validate the step model against the evaluator's SD6 detector error model (finite R).

Model: every item (reader z, step index s) flips exactly detector (z, s) (s = R is the final detector).  Single faults:
data error on q at half-integer time u; hook of writer instance (c, j) after its (k-1)-th CNOT (k = 2..6); flip of
reader instance (z, t).  The evaluator memory circuit has detectors of the memory basis only, so the DEM signature of
an SD6 fault is exactly the signature of its error part of the memory-relevant type.  We compare the SET of non-empty
(detectors, observables) signatures of the model with that of the stim DEM.

  uv run python -m search.theory.B.validate --code gross --spec search/experiments/e032/u11_spec.json --R 2
"""
from __future__ import annotations

import argparse
import json
import math

import numpy as np

from search.theory.B.window import get_code
from search.theory.B.bulk import load_spec


def model_sigs(code, spec, basis, R):
    from evaluators import candidate as cand
    U = cand.unroll(spec, code, R)
    lay = cand.layout_for(code)
    D = spec.period
    last = U.num_layers - 1
    W, Rd = ((spec.x_checks, lay.x_anc), (spec.z_checks, lay.z_anc)) if basis == "Z" else \
        ((spec.z_checks, lay.z_anc), (spec.x_checks, lay.x_anc))
    L = np.asarray(code.LZ if basis == "Z" else code.LX) % 2
    reads = {}
    for z, (c, a) in enumerate(zip(*Rd)):
        dm, offs = c.offsets(D)
        for o, col in offs:
            reads.setdefault(col, []).append((z, U.start[a] + o))

    def sig_fin(r, u):
        for t in range(R):
            if r + D * t > u:
                return t
        return R

    def obs(qs):
        v = L[:, list(qs)].sum(1) % 2 if qs else np.zeros(L.shape[0], int)
        return frozenset(np.flatnonzero(v).tolist())

    def items_to_sig(items):
        s = set()
        for it in items:
            s ^= {it}
        return frozenset(s)
    out = set()
    for q, lst in reads.items():
        for u2 in range(1, 2 * (last + 1), 2):
            u = u2 / 2
            out.add((items_to_sig([(z, sig_fin(r, u)) for z, r in lst]), obs([q])))
    for c, a in zip(*W):
        dm, offs = c.offsets(D)
        for j in range(R):
            for k in range(1, 7):
                suf = offs[k - 1:]
                items = []
                for o, col in suf:
                    u = U.start[a] + o + D * j
                    items += [(z, sig_fin(r, u)) for z, r in reads[col]]
                out.add((items_to_sig(items), obs([col for _, col in suf])))
    for z in range(len(Rd[0])):
        for t in range(R):
            out.add((frozenset({(z, t), (z, t + 1)}), frozenset()))
    out.discard((frozenset(), frozenset()))
    return out


def dem_sigs(code, spec, basis, R):
    from evaluators import candidate as cand
    from evaluators.noise import add_noise
    circ = add_noise(cand.memory_circuit(spec, code, basis, R), "sd6", 1e-3)
    coords = circ.get_detector_coordinates()
    dem = circ.detector_error_model(approximate_disjoint_errors=True, flatten_loops=True)
    out = set()
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        dets, obs = set(), set()
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                c = coords[t.val]
                dets ^= {(int(c[0]), int(c[1]))}
            elif t.is_logical_observable_id():
                obs ^= {t.val}
        if dets or obs:
            out.add((frozenset(dets), frozenset(obs)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--R", type=int, default=2)
    a = ap.parse_args()
    from evaluators import candidate as cand
    code = get_code(a.code)
    spec = cand.parse_schedule(load_spec(a.spec))
    res = {"spec": a.spec, "R": a.R}
    for b in ("Z", "X"):
        M, Dm = model_sigs(code, spec, b, a.R), dem_sigs(code, spec, b, a.R)
        res[b] = {"model": len(M), "dem": len(Dm), "equal": M == Dm, "model_only": len(M - Dm), "dem_only": len(Dm - M)}
    print(json.dumps(res))


if __name__ == "__main__":
    main()
