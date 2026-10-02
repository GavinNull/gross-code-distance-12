"""Code-distance estimation.

* `distance_upper_bound_bposd`: the randomized BP-OSD method of arXiv:2308.07915 Sec. 6 (Eq. 11),
  same as baselines/bb_code.py (E-002): pick a random nontrivial logical eta of the opposite type,
  solve min |xi| s.t. H xi = 0, eta.xi = 1 heuristically with BP-OSD.  Every value found is an
  explicitly verified logical operator, hence a rigorous UPPER bound.  Trials stop on a count or on a
  wall-clock budget, whichever comes first.
* `distance_exact_milp`: integer program (Landahl–Anderson–Rice style, arXiv:1108.5738, as used by
  the IBM paper for Table 3) solved with HiGHS through scipy.optimize.milp:
      min sum(xi)  s.t.  H xi - 2 s = 0,  L xi - 2 t - y = 0,  sum(y) >= 1,
      xi, y binary, s, t >= 0 integer,
  where L is the paired logical basis of the opposite type (so y_j = <L_j, xi> mod 2 and "some
  y_j = 1" <=> xi is a nontrivial logical).  If HiGHS proves optimality within the time limit the
  value is EXACT; otherwise we return the incumbent (upper bound) and the dual bound (lower bound).
  For group codes (abelian G) the code is invariant under simultaneous translation of both blocks,
  which acts transitively on L and on R, so we may add xi_L0 + xi_R0 >= 1 (symmetry breaking).
* For abelian group codes d_X = d_Z: the inversion automorphism maps (A, B) -> (A^T, B^T), whose HX
  is HZ with blocks swapped, so the X- and Z-codes are permutation equivalent.  Then we only compute
  the Z-distance.  For non-abelian groups both are computed.
"""
from __future__ import annotations

import time

import numpy as np
import scipy.sparse as sp
from scipy.optimize import Bounds, LinearConstraint, milp


def _one_type_bposd(H, Lopp, trials, time_budget, rng, osd_order, max_iter):
    from ldpc import BpOsdDecoder
    t0 = time.time()
    vals = []
    best_vec = None
    kk = Lopp.shape[0]
    for _ in range(trials):
        if vals and time.time() - t0 > time_budget:
            break
        c = rng.integers(0, 2, size=kk)
        if not c.any():
            c[rng.integers(kk)] = 1
        eta = (c @ Lopp) % 2
        M = np.vstack([H, eta[None, :]]).astype(np.uint8)
        syn = np.zeros(M.shape[0], dtype=np.uint8)
        syn[-1] = 1
        # randomize the prior a little: changes BP/OSD ordering -> more diverse solutions
        er = float(rng.uniform(0.01, 0.1))
        dec = BpOsdDecoder(M, error_rate=er, max_iter=max_iter, bp_method="minimum_sum",
                           osd_method="osd_cs", osd_order=osd_order)
        xi = dec.decode(syn)
        if not ((M.astype(np.int64) @ xi) % 2 == syn).all():
            continue
        w = int(xi.sum())
        vals.append(w)
        if best_vec is None or w < int(best_vec.sum()):
            best_vec = xi.astype(np.uint8)
    return vals, best_vec


def distance_upper_bound_bposd(css, trials: int = 200, time_budget: float = 60.0, seed: int = 0,
                               osd_order: int = 7, max_iter: int = 1000, symmetric: bool = False) -> dict:
    """Upper bound on d(css) (evaluators.codes.CSSCode).  symmetric=True -> only Z type (d_X = d_Z)."""
    rng = np.random.default_rng(seed)
    t0 = time.time()
    out = {}
    types = [("Z", css.HX, css.LX)] if symmetric else [("Z", css.HX, css.LX), ("X", css.HZ, css.LZ)]
    per = trials if symmetric else max(1, trials // 2)
    budget = time_budget / len(types)
    best = None
    for name, H, Lopp in types:
        vals, vec = _one_type_bposd(H, Lopp, per, budget, rng, osd_order, max_iter)
        out[f"d{name}_ub"] = min(vals) if vals else None
        out[f"{name}_trials"] = len(vals)
        if vals:
            hist = {}
            for v in vals:
                hist[v] = hist.get(v, 0) + 1
            out[f"{name}_hist"] = dict(sorted(hist.items()))
            if best is None or min(vals) < best[0]:
                best = (min(vals), vec, name)
    out["d_ub"] = best[0] if best else None
    out["witness_type"] = best[2] if best else None
    out["witness"] = best[1] if best else None
    out["seconds"] = time.time() - t0
    return out


def _milp_one_type(H, Lopp, upper: int | None, time_limit: float, translation_n2: int | None):
    """min weight xi with H xi = 0 and xi anticommuting with some row of Lopp."""
    H = np.asarray(H, dtype=np.int64)
    Lopp = np.asarray(Lopp, dtype=np.int64)
    r, n = H.shape
    k = Lopp.shape[0]
    # variable order: xi (n) | s (r) | t (k) | y (k)
    nv = n + r + k + k
    c = np.zeros(nv)
    c[:n] = 1
    rows = []
    lbs, ubs = [], []
    A1 = sp.hstack([sp.csr_matrix(H), -2 * sp.identity(r), sp.csr_matrix((r, 2 * k))])
    A2 = sp.hstack([sp.csr_matrix(Lopp), sp.csr_matrix((k, r)), -2 * sp.identity(k), -sp.identity(k)])
    rows += [A1, A2]
    lbs += [np.zeros(r), np.zeros(k)]
    ubs += [np.zeros(r), np.zeros(k)]
    yrow = np.zeros((1, nv))
    yrow[0, n + r + k:] = 1
    rows.append(sp.csr_matrix(yrow))
    lbs.append([1])
    ubs.append([np.inf])
    if upper is not None:
        wr = np.zeros((1, nv))
        wr[0, :n] = 1
        rows.append(sp.csr_matrix(wr))
        lbs.append([0])
        ubs.append([upper])
    if translation_n2:
        sr = np.zeros((1, nv))
        sr[0, 0] = 1
        sr[0, translation_n2] = 1
        rows.append(sp.csr_matrix(sr))
        lbs.append([1])
        ubs.append([2])
    A = sp.vstack(rows).tocsr()
    lb = np.concatenate([np.asarray(x, float) for x in lbs])
    ub = np.concatenate([np.asarray(x, float) for x in ubs])
    hi = np.full(nv, np.inf)
    hi[:n] = 1
    hi[n + r + k:] = 1
    # parity slacks are bounded by half the row weight
    hi[n:n + r] = np.floor(H.sum(1) / 2)
    hi[n + r:n + r + k] = np.floor(Lopp.sum(1) / 2)
    res = milp(c, constraints=LinearConstraint(A, lb, ub), integrality=np.ones(nv),
               bounds=Bounds(np.zeros(nv), hi),
               options={"time_limit": time_limit, "disp": False, "mip_rel_gap": 0})
    out = {"status": int(res.status), "message": res.message}
    if res.x is not None:
        xi = np.round(res.x[:n]).astype(np.uint8)
        out["value"] = int(xi.sum())
        out["witness"] = xi
    else:
        out["value"] = None
    lbd = getattr(res, "mip_dual_bound", None)
    out["lower"] = int(np.ceil(lbd - 1e-6)) if lbd is not None and np.isfinite(lbd) else None
    out["optimal"] = res.status == 0
    return out


def distance_exact_milp(css, time_limit: float = 600.0, upper: int | None = None,
                        symmetric: bool = False, translation_n2: int | None = None) -> dict:
    """Exact distance by MILP (or bounds if time runs out).

    upper: known upper bound (e.g. from BP-OSD) added as a constraint sum(xi) <= upper; the
    constraint never cuts off the optimum, it only helps pruning.  If the MILP is infeasible under
    it, the optimum equals `upper` itself only if `upper` was achieved by a verified logical.
    translation_n2: |G| for group codes (enables the symmetry-breaking row)."""
    t0 = time.time()
    types = [("Z", css.HX, css.LX)] if symmetric else [("Z", css.HX, css.LX), ("X", css.HZ, css.LZ)]
    out = {}
    d_lo, d_hi = [], []
    for name, H, Lopp in types:
        rem = max(1.0, time_limit - (time.time() - t0))
        r = _milp_one_type(H, Lopp, upper, rem, translation_n2)
        if r["status"] == 2:
            if upper is None:
                raise RuntimeError("MILP infeasible without an upper bound: code has k = 0?")
            # proved: no logical of this type with weight <= upper
            lo, hi = upper + 1, np.inf
        elif r["optimal"]:
            lo = hi = r["value"]
        else:
            hi = r["value"] if r["value"] is not None else np.inf
            lo = r["lower"] if r["lower"] is not None else 1
        if r["value"] is not None:
            w = r["witness"]
            assert ((np.asarray(H, np.int64) @ w) % 2 == 0).all()
            assert ((np.asarray(Lopp, np.int64) @ w) % 2).any()
        out[f"d{name}"] = {"lower": int(lo), "upper": (None if not np.isfinite(hi) else int(hi)),
                           "status": r["message"]}
        d_lo.append(lo)
        d_hi.append(hi)
    # d = min(d_Z, d_X)
    out["d_lower"] = int(min(d_lo))
    out["d_upper"] = int(min(d_hi)) if np.isfinite(min(d_hi)) else None
    if out["d_upper"] is None:
        raise RuntimeError("no logical found by MILP and all types infeasible below upper bound")
    out["exact"] = out["d_lower"] == out["d_upper"]
    out["seconds"] = time.time() - t0
    return out


def code_distance(code, bposd_trials=200, bposd_budget=60.0, milp_max_n=100, milp_time=300.0,
                  seed=0) -> dict:
    """Convenience: BP-OSD upper bound; plus MILP if n <= milp_max_n.  Returns
    {"d": value, "d_kind": "exact"|"upper", "d_lower": ..., ...}."""
    css = code.to_css()
    sym = code.is_abelian
    ub = distance_upper_bound_bposd(css, trials=bposd_trials, time_budget=bposd_budget, seed=seed,
                                    symmetric=sym)
    res = {"d_ub_bposd": ub["d_ub"], "bposd_trials": ub.get("Z_trials", 0) + ub.get("X_trials", 0),
           "bposd_seconds": round(ub["seconds"], 2), "d": ub["d_ub"], "d_kind": "upper", "d_lower": None}
    if code.n <= milp_max_n:
        ex = distance_exact_milp(css, time_limit=milp_time, upper=ub["d_ub"], symmetric=sym,
                                 translation_n2=code.n2 if sym else None)
        res.update({"milp_seconds": round(ex["seconds"], 2), "d_lower": ex["d_lower"]})
        if ex["exact"]:
            res["d"], res["d_kind"] = ex["d_upper"], "exact"
        else:
            res["d"] = min(x for x in (ex["d_upper"], ub["d_ub"]) if x is not None)
    return res
