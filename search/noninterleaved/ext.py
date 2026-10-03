"""Extended code E and its distance d_ext (Strikis, Browne, Beverland, arXiv:2603.05481 v2).

Definitions used (section numbers of v2):
  * Residual errors (Sec. IV.A, display before Def. 1): for a Z check whose CNOTs touch data qubits
    i_1, ..., i_w in circuit order,  E_{Z,j} = { E_l = sum_{s=l..w} e_{i_s} : l = 2..w }  (suffixes of the
    order of length w-1 .. 1). Physically: a Z fault on the Z ancilla after the (l-1)-th CNOT propagates to
    every data qubit of a later CNOT. X checks analogous with X <-> Z (X fault on the X ancilla).
  * Extended code (Def. 2): append to H_X and L_X one column per Z-type residual error; the column is the
    mod-2 sum of the H_X / L_X columns of the qubits in the residual.  (X-type: append to H_Z, L_Z.)
  * Extended-code distance (Def. 3, Eq. (7)): d^Z_ext(R) = min |x| s.t. H_X^ext x = 0 and L_X^ext x != 0;
    d_ext = min(d^X_ext, d^Z_ext)  (Eq. (8)).
  * Theorem 1 / Corollary 1 (Sec. IV.B): any non-interleaved single-ancilla SEC has d'_circ = d_ext(E) with E
    its full residual set; any SEC (interleaved too) has d_circ >= d_ext(E) (Prop. 3); and
    d'_circ <= d_ext(R) for any subset R of E.

Here L_X is a full basis of X-type logicals (rows), so "L_X x != 0" <=> x in ker(H_X) \\ rowspace(H_Z)
on the data part.  Duplicate columns (identical (H, L) column) are merged: this never changes the minimum.

Exact solver: OR-tools CP-SAT with native XOR constraints (own model; nothing imported from evaluators).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np


# ----------------------------------------------------------------------------- residuals

def residual_supports(order: list[int], include_trivial: bool = False) -> list[tuple[int, ...]]:
    """Suffixes {i_l..i_w}, l = 2..w, of a check's CNOT order (data-column indices)."""
    w = len(order)
    out = [tuple(sorted(order[l - 1:])) for l in range(2, w + 1)]
    return out


def extended_matrices(H: np.ndarray, L: np.ndarray, supports) -> tuple[np.ndarray, np.ndarray, list]:
    """(H_ext, L_ext, labels).  Column labels: ('q', j) for data qubit j, ('r', support) for a residual.
    Identical (H,L)-columns are merged (first label kept); all-zero columns are dropped."""
    H = np.asarray(H, dtype=np.uint8) % 2
    L = np.asarray(L, dtype=np.uint8) % 2
    cols_H = [H[:, j] for j in range(H.shape[1])]
    cols_L = [L[:, j] for j in range(H.shape[1])]
    labels = [("q", j) for j in range(H.shape[1])]
    for S in supports:
        S = list(S)
        cols_H.append((H[:, S].sum(1) % 2).astype(np.uint8))
        cols_L.append((L[:, S].sum(1) % 2).astype(np.uint8))
        labels.append(("r", tuple(S)))
    seen = {}
    keepH, keepL, keepLab = [], [], []
    for h, l, lab in zip(cols_H, cols_L, labels):
        if not h.any() and not l.any():
            continue
        key = h.tobytes() + b"|" + l.tobytes()
        if key in seen:
            continue
        seen[key] = len(keepH)
        keepH.append(h); keepL.append(l); keepLab.append(lab)
    return (np.array(keepH, dtype=np.uint8).T, np.array(keepL, dtype=np.uint8).T, keepLab)


# ----------------------------------------------------------------------------- exact min-weight logical

@dataclass
class MinWeight:
    lower: int | None
    upper: int | None
    status: str
    seconds: float
    witness: list = field(default_factory=list)   # column indices of an optimal / best x

    @property
    def exact(self) -> bool:
        return self.lower is not None and self.lower == self.upper


def min_weight_logical(H: np.ndarray, L: np.ndarray, *, max_weight: int | None = None, time_limit: float = 600.0,
                       workers: int = 1, seed: int = 0, hint: list[int] | None = None) -> MinWeight:
    """min |x| s.t. H x = 0, L x != 0 (CP-SAT).  max_weight: optional valid cap (e.g. a known upper bound);
    if the model is infeasible under the cap, lower = max_weight + 1 and upper = None."""
    from ortools.sat.python import cp_model
    t0 = time.time()
    H = np.asarray(H, dtype=np.uint8)
    L = np.asarray(L, dtype=np.uint8)
    n = H.shape[1]
    M = cp_model.CpModel()
    one = M.NewConstant(1)
    x = [M.NewBoolVar(f"x{j}") for j in range(n)]
    for row in H:
        idx = np.nonzero(row)[0]
        if len(idx):
            M.AddBoolXOr([x[k] for k in idx] + [one])
    ys = []
    for i, row in enumerate(L):
        idx = np.nonzero(row)[0]
        if not len(idx):
            continue
        y = M.NewBoolVar(f"y{i}")
        ys.append(y)
        M.AddBoolXOr([x[k] for k in idx] + [y, one])
    M.AddBoolOr(ys)
    if max_weight is not None:
        M.Add(sum(x) <= max_weight)
    if hint:
        hs = set(hint)
        for j in range(n):
            M.AddHint(x[j], 1 if j in hs else 0)
    M.Minimize(sum(x))
    s = cp_model.CpSolver()
    s.parameters.num_workers = workers
    s.parameters.random_seed = seed
    s.parameters.max_time_in_seconds = float(time_limit)
    st = s.Solve(M)
    sec = round(time.time() - t0, 2)
    name = s.StatusName(st)
    if st == cp_model.INFEASIBLE:
        return MinWeight(None if max_weight is None else max_weight + 1, None, "infeasible_under_cap", sec)
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        w = [j for j in range(n) if s.Value(x[j])]
        xv = np.zeros(n, dtype=np.uint8); xv[w] = 1
        assert not ((H.astype(np.int64) @ xv) % 2).any() and ((L.astype(np.int64) @ xv) % 2).any()
        ub = len(w)
        lb = ub if st == cp_model.OPTIMAL else int(np.ceil(s.BestObjectiveBound() - 1e-6))
        return MinWeight(lb, ub, name.lower(), sec, w)
    return MinWeight(int(np.ceil(s.BestObjectiveBound() - 1e-6)) if st != cp_model.MODEL_INVALID else None,
                     None, name.lower(), sec)


def min_weight_milp(H: np.ndarray, L: np.ndarray, *, max_weight: int | None = None, time_limit: float = 600.0,
                    **_ignored) -> MinWeight:
    """Same problem with HiGHS (search/codes/distance.py `_milp_one_type`, used read-only, no symmetry
    breaking).  max_weight: valid cap; infeasible => lower = max_weight + 1."""
    from search.codes.distance import _milp_one_type
    t0 = time.time()
    r = _milp_one_type(H, L, max_weight, time_limit, None)
    sec = round(time.time() - t0, 2)
    if r["status"] == 2:
        if max_weight is None:
            raise RuntimeError("no logical at all (k=0?)")
        return MinWeight(max_weight + 1, None, "infeasible_under_cap", sec)
    if r["value"] is not None:
        w = np.nonzero(r["witness"])[0].tolist()
        xv = r["witness"].astype(np.int64)
        assert not ((H.astype(np.int64) @ xv) % 2).any() and ((L.astype(np.int64) @ xv) % 2).any()
        if r["optimal"]:
            return MinWeight(r["value"], r["value"], "optimal", sec, w)
        return MinWeight(r["lower"], r["value"], "time_limit", sec, w)
    return MinWeight(r["lower"], None, "time_limit_no_incumbent", sec)


def feasible_milp(H: np.ndarray, L: np.ndarray, *, max_weight: int, time_limit: float = 600.0,
                  **_ignored) -> MinWeight:
    """Decision version: is there a logical x with |x| <= max_weight?  Zero objective (HiGHS stops at the
    first feasible point).  Feasible => upper = |x| (verified witness), lower unknown (reported as None);
    infeasible => lower = max_weight + 1 (proof)."""
    import scipy.sparse as sp
    from scipy.optimize import Bounds, LinearConstraint, milp
    t0 = time.time()
    H = np.asarray(H, dtype=np.int64)
    L = np.asarray(L, dtype=np.int64)
    r, n = H.shape
    k = L.shape[0]
    nv = n + r + 2 * k
    A1 = sp.hstack([sp.csr_matrix(H), -2 * sp.identity(r), sp.csr_matrix((r, 2 * k))])
    A2 = sp.hstack([sp.csr_matrix(L), sp.csr_matrix((k, r)), -2 * sp.identity(k), -sp.identity(k)])
    yrow = np.zeros((1, nv)); yrow[0, n + r + k:] = 1
    wrow = np.zeros((1, nv)); wrow[0, :n] = 1
    A = sp.vstack([A1, A2, sp.csr_matrix(yrow), sp.csr_matrix(wrow)]).tocsr()
    lb = np.concatenate([np.zeros(r), np.zeros(k), [1], [0]])
    ub = np.concatenate([np.zeros(r), np.zeros(k), [np.inf], [max_weight]])
    hi = np.full(nv, np.inf); hi[:n] = 1; hi[n + r + k:] = 1
    hi[n:n + r] = np.floor(H.sum(1) / 2); hi[n + r:n + r + k] = np.floor(L.sum(1) / 2)
    res = milp(np.zeros(nv), constraints=LinearConstraint(A, lb, ub), integrality=np.ones(nv),
               bounds=Bounds(np.zeros(nv), hi), options={"time_limit": time_limit, "disp": False})
    sec = round(time.time() - t0, 2)
    if res.status == 2:
        return MinWeight(max_weight + 1, None, "infeasible_under_cap", sec)
    if res.x is not None:
        xv = np.round(res.x[:n]).astype(np.int64)
        assert not ((H @ xv) % 2).any() and ((L @ xv) % 2).any() and xv.sum() <= max_weight
        return MinWeight(None, int(xv.sum()), "feasible_under_cap", sec, np.nonzero(xv)[0].tolist())
    return MinWeight(None, None, "time_limit_undecided", sec)


SOLVERS = {"milp": min_weight_milp, "cpsat": min_weight_logical, "feas": feasible_milp}

# ----------------------------------------------------------------------------- d_ext of a circuit

def d_ext_type(H, L, orders, solver: str = "milp", **kw) -> dict:
    """One type.  orders: list of per-check CNOT orders (data column indices) of the checks whose
    hooks are detected by H (Z-check orders with H=H_X, L=L_X; X-check orders with H=H_Z, L=L_Z)."""
    sup = [s for o in orders for s in residual_supports(o)]
    He, Le, lab = extended_matrices(H, L, sup)
    r = SOLVERS[solver](He, Le, **kw)
    return {"lower": r.lower, "upper": r.upper, "exact": r.exact, "status": r.status, "seconds": r.seconds,
            "num_columns": He.shape[1], "num_residuals_raw": len(sup),
            "witness": [lab[j] for j in r.witness]}


def d_ext(HX, HZ, LX, LZ, x_orders, z_orders, **kw) -> dict:
    """Full extended-code distance d_ext(E) = min(d^X_ext(E_X), d^Z_ext(E_Z)).
    LX: X-type logical operators (rows), LZ: Z-type logicals."""
    dz = d_ext_type(HX, LX, z_orders, **kw)
    dx = d_ext_type(HZ, LZ, x_orders, **kw)
    # d = min(dX, dZ): lower = min of lowers; upper = min of uppers
    lo = min(dz["lower"] or 0, dx["lower"] or 0)
    ups = [v for v in (dz["upper"], dx["upper"]) if v is not None]
    up = min(ups) if ups else None
    return {"Z": dz, "X": dx, "lower": lo, "upper": up, "exact": lo is not None and lo == up}


# ----------------------------------------------------------------------------- orders from a Schedule

def orders_from_schedule(sched) -> tuple[list[list[int]], list[list[int]]]:
    """Per-check CNOT orders (data-column indices, rows in HX / HZ order) read off a cyclic Schedule:
    CNOTs of a check sorted by (layer - prep_layer) mod depth."""
    D = sched.depth
    col = {q: j for j, q in enumerate(sched.data)}
    prep, ev = {}, {}
    for t, Ly in enumerate(sched.layers):
        for q in Ly.prep_x + Ly.prep_z:
            prep[q] = t
        for c, tg in Ly.cnots:
            if c in col:      # data -> Z check
                ev.setdefault(tg, []).append((t, col[c]))
            else:             # X check -> data
                ev.setdefault(c, []).append((t, col[tg]))
    def order(q):
        return [j for _, j in sorted(ev[q], key=lambda e: (e[0] - prep[q]) % D)]
    return [order(q) for q in sched.x_checks], [order(q) for q in sched.z_checks]
