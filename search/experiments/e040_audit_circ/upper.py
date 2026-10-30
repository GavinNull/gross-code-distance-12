"""Item (4): upper bounds.

 data W: find a weight-W pure data logical of the gross code for the basis (mitmsearch decide on the 144 data
   columns), then stim-inject it (X_ERROR(1) / Z_ERROR(1)) right after the initial data reset of the evaluator's
   noiseless memory circuit for several R: all detectors 0 and an observable flipped => d_circ <= W for that R
   (each injected Pauli is one SD6 fault: a flip after the reset layer).
 finite: for a given R, find a concrete undetectable logical of the evaluator's R-round circuit of weight w + flips
   by the B_audit finite lift (solve_finite) of listed extended logicals, then verify it against the evaluator's SD6
   DEM itself: every realisation's detector set (and the flip's) must be a DEM term, the terms are distinct, their
   detector sets XOR to zero and their observable sets XOR to non-zero.

  uv run python -m search.experiments.e040_audit_circ.upper data g10 Z 12 1,2,3,6,10,20
  uv run python -m search.experiments.e040_audit_circ.upper finite g8 Z 10 1 2,3,4,...
"""
from __future__ import annotations

import pickle
import subprocess
import sys
from collections import defaultdict

import numpy as np

from search.experiments.e040_audit_circ.common import OUT, gross, jdump, load


def data_logical(basis, W):
    code = gross()
    H = (np.asarray(code.HZ if basis == "Z" else code.HX) % 2).astype(np.uint8)
    L = (np.asarray(code.LZ if basis == "Z" else code.LX) % 2).astype(np.uint8)
    n = H.shape[1]
    lines = [f"{n} {H.shape[0]}"]
    for q in range(n):
        hs = np.flatnonzero(H[:, q]).tolist()
        ls = np.flatnonzero(L[:, q]).tolist()
        lines.append(f"{len(hs)} {' '.join(map(str, hs))} {len(ls)} {' '.join(map(str, ls))}")
    lines += ["1", " ".join(["0"] * n), "0"]
    inp = OUT / f"data_{basis}.txt"
    inp.write_text("\n".join(lines) + "\n")
    so = subprocess.run([str(OUT / "mitm_nw2"), str(W), "decide", "2"], stdin=open(inp), capture_output=True,
                        text=True, check=True).stdout
    sol = [list(map(int, l.split()[2:])) for l in so.splitlines() if l.startswith("SOL")]
    return sol[0] if sol else None


def inject_data(name, basis, qs, R):
    import stim
    from evaluators import candidate as cand
    code = gross()
    circ = cand.memory_circuit(cand.parse_schedule(load(name)), code, basis, R)
    c = stim.Circuit()
    done = False
    for op in circ:
        c.append(op)
        if not done and op.name in ("R", "RX") and set(range(code.n)) <= {t.value for t in op.targets_copy()}:
            c.append("X_ERROR" if basis == "Z" else "Z_ERROR", qs, 1.0)
            done = True
    assert done
    s = c.compile_detector_sampler().sample(1, append_observables=True)[0]
    nd = c.num_detectors
    return {"R": R, "detectors_fired": int(s[:nd].sum()), "obs_flipped": np.flatnonzero(s[nd:]).tolist()}


def finite(name, basis, w, flips, R, maxtry=400):
    from evaluators import candidate as cand
    from evaluators.noise import add_noise
    from search.theory.B_audit.lift import finite_columns, solve_finite
    code = gross()
    sd = load(name)
    cols, B, nz = finite_columns(sd, code, basis, R)
    d = pickle.load(open(OUT / f"list_{name}_{basis}_w{w}.pkl", "rb"))
    circ = add_noise(cand.memory_circuit(cand.parse_schedule(sd), code, basis, R), "sd6", 1e-3)
    coords = circ.get_detector_coordinates()
    det_of = {(int(c[0]), int(c[1])): dd for dd, c in coords.items()}
    terms = {}
    for e in circ.detector_error_model(approximate_disjoint_errors=True, flatten_loops=True).flattened():
        if e.type != "error":
            continue
        ds, os_ = set(), set()
        for t in e.targets_copy():
            if t.is_relative_detector_id():
                ds ^= {t.val}
            elif t.is_logical_observable_id():
                os_ ^= {t.val}
        terms[frozenset(ds)] = frozenset(os_)
    for i, S in enumerate(d["keys"][:maxtry]):
        r = solve_finite(S, cols, nz, R, flips)
        if r is None:
            continue
        used, acc = [], set()
        for kind, ident, items in r:
            ds = frozenset(det_of[it] for it in items)
            used.append(ds)
            acc ^= set(items)
        # residual = flips
        res = defaultdict(list)
        for z, t in acc:
            res[z].append(t)
        ok = True
        for z, ts in res.items():
            ts.sort()
            if len(ts) != 2 or ts[1] != ts[0] + 1:
                ok = False
            used.append(frozenset({det_of[(z, ts[0])], det_of[(z, ts[1])]}))
        all_terms = all(u in terms for u in used)
        distinct = len(set(used)) == len(used)
        dx, ox = set(), set()
        for u in used:
            dx ^= set(u)
            ox ^= set(terms.get(u, frozenset()))
        return {"spec": name, "basis": basis, "R": R, "list_w": w, "list_index": i, "weight": len(used),
                "flips_used": len(res), "flip_pattern_ok": ok, "all_DEM_terms": all_terms, "distinct": distinct,
                "dets_cancel": not dx, "obs": sorted(ox),
                "verified": ok and all_terms and distinct and not dx and bool(ox)}
    return {"spec": name, "basis": basis, "R": R, "list_w": w, "found": False, "tried": min(maxtry, len(d["keys"]))}


def main():
    mode = sys.argv[1]
    if mode == "data":
        name, basis, W = sys.argv[2], sys.argv[3], int(sys.argv[4])
        Rs = [int(x) for x in sys.argv[5].split(",")]
        qs = data_logical(basis, W)
        rec = {"mode": "data", "spec": name, "basis": basis, "W": W, "qubits": qs,
               "runs": [inject_data(name, basis, qs, R) for R in Rs] if qs else None}
        jdump(rec, "upper.jsonl")
    else:
        name, basis, w, flips = sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
        for R in [int(x) for x in sys.argv[6].split(",")]:
            jdump(finite(name, basis, w, flips, R), "upper.jsonl")


if __name__ == "__main__":
    main()
