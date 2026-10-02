"""Circuit-level distance via integer programming on the stim detector error model.

d_circ = min |xi| over xi in {0,1}^E with D xi = 0 (mod 2) and L xi != 0 (mod 2).
Since any logical error flips at least one observable,
  d_circ = min_i  min { |xi| : D xi = 0, (L xi)_i = 1 }.
Each inner problem is a MILP (parity via integer slacks), solved with HiGHS (scipy.optimize.milp).
With a time limit the solver returns the incumbent (an upper bound) and its dual bound
(a lower bound); both are reported. Weights are unit (count of DEM error mechanisms, i.e. faults;
identical single-fault columns are merged by stim, so one column = at least one fault).

Usage: uv run python -m baselines.circuit_distance --config experiments/E-002-gross-baseline.yaml \
           --rounds 1 --basis Z --time-limit 300 [--observables 0,1,...]
"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np
import scipy.sparse as sp
from scipy.optimize import Bounds, LinearConstraint, milp


def dem_matrices(dem):
    from stimbposd.dem_to_matrices import detector_error_model_to_check_matrices
    m = detector_error_model_to_check_matrices(dem, allow_undecomposed_hyperedges=True)
    return m.check_matrix.tocsr().astype(np.int64), m.observables_matrix.tocsr().astype(np.int64)


def min_weight_flipping(D, L, obs, time_limit):
    nd, ne = D.shape
    row_w = np.asarray(D.sum(axis=1)).ravel()
    lw = int(L[obs].sum())
    # variables: xi (ne binaries), s (nd ints, 0..row_w/2), t (1 int, 0..lw/2)
    n_s = nd
    c = np.concatenate([np.ones(ne), np.zeros(n_s + 1)])
    A1 = sp.hstack([D, -2 * sp.identity(nd, format="csr"), sp.csr_matrix((nd, 1))])
    A2 = sp.hstack([L[obs], sp.csr_matrix((1, nd)), sp.csr_matrix([[-2]])])
    A = sp.vstack([A1, A2]).tocsr()
    lb = np.concatenate([np.zeros(nd), [1]])
    ub = lb.copy()
    integrality = np.ones(ne + n_s + 1)
    bounds = Bounds(np.zeros(ne + n_s + 1),
                    np.concatenate([np.ones(ne), np.floor(row_w / 2), [np.floor(lw / 2)]]))
    t0 = time.time()
    r = milp(c, constraints=LinearConstraint(A, lb, ub), integrality=integrality, bounds=bounds,
             options={"time_limit": time_limit, "disp": False})
    out = {"observable": obs, "status": int(r.status), "message": r.message, "wall_s": round(time.time() - t0, 1)}
    if r.x is not None:
        xi = np.round(r.x[:ne]).astype(np.int64)
        assert not (D @ xi % 2).any() and (L[obs] @ xi) % 2 == 1
        out["upper_bound"] = int(xi.sum())
        out["support"] = np.nonzero(xi)[0].tolist()
    dual = getattr(r, "mip_dual_bound", None)
    if dual is not None:
        out["lower_bound"] = int(np.ceil(dual - 1e-6))
    return out


def main():
    from baselines.gross import load, circuits
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--basis", default="Z")
    ap.add_argument("--time-limit", type=float, default=300)
    ap.add_argument("--observables", default=None)
    ap.add_argument("--witness-weight", type=int, default=None,
                    help="instead of ILP: BP-OSD random search for an undetectable logical error of this weight or less")
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--max-trials", type=int, default=6000)
    a = ap.parse_args()
    cfg, code, sched, out = load(a.config)
    c = circuits(code, sched, a.rounds, a.basis, 0.001)
    if a.witness_weight is not None:
        w = bposd_witness(c, a.witness_weight, a.max_trials, a.seed)
        p = out / f"circuit_distance_witness_{a.basis}_r{a.rounds}.json"
        p.write_text(json.dumps({"basis": a.basis, "rounds": a.rounds, "seed": a.seed, "result": w}, indent=1))
        print(json.dumps({k: v for k, v in (w or {"found": None}).items() if k != "faults"}))
        for f in (w or {}).get("faults", []):
            print(f[:300])
        return
    dem = c.detector_error_model()
    D, L = dem_matrices(dem)
    obs = range(L.shape[0]) if a.observables is None else [int(x) for x in a.observables.split(",")]
    res = []
    path = out / f"circuit_distance_ilp_{a.basis}_r{a.rounds}.json"
    for o in obs:
        r = min_weight_flipping(D, L, o, a.time_limit)
        r.update({"basis": a.basis, "rounds": a.rounds, "num_errors": D.shape[1], "num_detectors": D.shape[0]})
        res.append(r)
        print({k: v for k, v in r.items() if k != "support"}, flush=True)
        path.write_text(json.dumps(res, indent=1))



def bposd_witness(circuit, target_weight, max_trials, seed, osd_order=10):
    """Random-eta BP-OSD search (paper Eq. 12) until an undetectable logical error of weight
    <= target_weight is found; returns (weight, DEM column indices, stim explanation)."""
    import stim
    from ldpc import BpOsdDecoder
    dem = circuit.detector_error_model()
    D, L = dem_matrices(dem)
    rng = np.random.default_rng(seed)
    for trial in range(max_trials):
        a = rng.integers(0, 2, L.shape[0])
        if not a.any():
            a[rng.integers(L.shape[0])] = 1
        b = rng.integers(0, 2, D.shape[0])
        eta = (a @ L + b @ D) % 2
        H = sp.vstack([D, sp.csr_matrix(eta)]).tocsr().astype(np.uint8)
        syn = np.zeros(H.shape[0], dtype=np.uint8)
        syn[-1] = 1
        xi = BpOsdDecoder(H, error_rate=0.01, max_iter=100, bp_method="minimum_sum",
                          osd_method="osd_cs", osd_order=osd_order).decode(syn)
        if xi.sum() <= target_weight:
            cols = np.nonzero(xi)[0].tolist()
            assert not (D @ xi % 2).any() and (L @ xi % 2).any()
            # rebuild a DEM containing only the chosen mechanisms and let stim locate them in the circuit
            flat = [inst for inst in dem.flattened() if inst.type == "error"]
            sub = stim.DetectorErrorModel()
            for i in cols:
                sub.append(flat[i])
            expl = circuit.explain_detector_error_model_errors(dem_filter=sub, reduce_to_one_representative_error=True)
            return {"trial": trial, "weight": int(xi.sum()), "columns": cols,
                    "flipped_observables": np.nonzero(L @ xi % 2)[0].tolist(),
                    "faults": [str(e.circuit_error_locations[0]) for e in expl]}
    return None


if __name__ == "__main__":
    main()
