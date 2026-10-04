"""Reference decoder for E-006: per-shot exact most-likely-error (MLE) decoding of one sector.

    minimise  sum_j w_j e_j,   w_j = log((1-p_j)/p_j)   subject to  H e = s (mod 2),  e in {0,1}^N

This is the "most likely single error" (minimum likelihood-weight) decoder, NOT the degenerate-ML decoder
(which would maximise the total probability of a logical class, summing over all errors in it).  With
mode="count" all w_j = 1 (minimum-cardinality decoder).

Solvers:
  * CP-SAT (default): native XOR constraints; weights scaled to integers (`scale`, default 1e4, rounding error per
    column <= 0.5/scale, i.e. < 1e-3 in total for any solution with < 20 faults). Hints: any feasible solutions
    supplied by the caller (BP-OSD output, truth). OPTIMAL means proven optimal for the rounded weights.
  * HiGHS MILP (scipy.optimize.milp): H e - 2 z = s with integer z; exact real weights; used as a cross-check.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp


@dataclass
class ExactResult:
    e: np.ndarray | None
    status: str           # "OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN"
    objective: float      # real-valued weight of e (nan if None)
    bound: float          # proven lower bound on the (scaled-back) objective
    seconds: float
    solver: str


class CpSatMLE:
    def __init__(self, H: sp.csc_matrix, weights: np.ndarray, scale: float = 1e4, mode: str = "mle"):
        self.H = sp.csc_matrix(H)
        self.Hr = self.H.tocsr()
        self.w = np.asarray(weights, dtype=float) if mode == "mle" else np.ones(self.H.shape[1])
        self.wi = np.maximum(1, np.rint(self.w * (scale if mode == "mle" else 1))).astype(np.int64)
        self.scale = scale if mode == "mle" else 1.0
        self.rows = [self.Hr.indices[self.Hr.indptr[i]:self.Hr.indptr[i + 1]] for i in range(self.H.shape[0])]

    def decode(self, syndrome: np.ndarray, hints=(), time_limit: float = 60.0, seed: int = 0,
               workers: int = 1, upper: float | None = None) -> ExactResult:
        from ortools.sat.python import cp_model
        t0 = time.time()
        N = self.H.shape[1]
        m = cp_model.CpModel()
        x = [m.NewBoolVar("") for _ in range(N)]
        for i, cols in enumerate(self.rows):
            lits = [x[j] for j in cols]
            if not lits:
                if syndrome[i]:
                    return ExactResult(None, "INFEASIBLE", np.nan, np.inf, time.time() - t0, "cpsat")
                continue
            if not syndrome[i]:
                lits[0] = lits[0].Not()
            m.AddBoolXOr(lits)
        obj = sum(int(self.wi[j]) * x[j] for j in range(N))
        m.Minimize(obj)
        best_hint = None
        for h in hints:
            if h is None:
                continue
            h = np.asarray(h).astype(bool)
            if ((self.Hr @ h.astype(np.uint8)) % 2 != syndrome).any():
                continue
            v = int(self.wi[h].sum())
            if best_hint is None or v < best_hint[0]:
                best_hint = (v, h)
        if best_hint is not None:
            for j in range(N):
                m.AddHint(x[j], bool(best_hint[1][j]))
        s = cp_model.CpSolver()
        s.parameters.max_time_in_seconds = time_limit
        s.parameters.num_search_workers = workers
        s.parameters.random_seed = seed
        st = s.Solve(m)
        name = s.StatusName(st)
        if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            e = np.array([s.BooleanValue(v) for v in x], dtype=bool)
            return ExactResult(e.astype(np.uint8), name, float(self.w[e].sum()),
                               s.BestObjectiveBound() / self.scale, time.time() - t0, "cpsat")
        return ExactResult(None, name, np.nan, s.BestObjectiveBound() / self.scale if st != cp_model.INFEASIBLE
                           else np.inf, time.time() - t0, "cpsat")


class MilpMLE:
    def __init__(self, H: sp.csc_matrix, weights: np.ndarray, mode: str = "mle"):
        self.H = sp.csc_matrix(H).astype(float)
        self.w = np.asarray(weights, dtype=float) if mode == "mle" else np.ones(self.H.shape[1])
        deg = np.asarray(self.H.sum(1)).ravel()
        self.zmax = np.floor(deg / 2)

    def decode(self, syndrome: np.ndarray, time_limit: float = 60.0) -> ExactResult:
        from scipy.optimize import Bounds, LinearConstraint, milp
        t0 = time.time()
        m, N = self.H.shape
        A = sp.hstack([self.H, -2 * sp.identity(m)]).tocsr()
        c = np.concatenate([self.w, np.zeros(m)])
        cons = LinearConstraint(A, syndrome.astype(float), syndrome.astype(float))
        res = milp(c, constraints=cons, integrality=np.ones(N + m),
                   bounds=Bounds(np.zeros(N + m), np.concatenate([np.ones(N), self.zmax])),
                   options={"time_limit": time_limit, "disp": False, "mip_rel_gap": 0.0})
        dt = time.time() - t0
        if res.x is None:
            return ExactResult(None, "UNKNOWN", np.nan, np.nan, dt, "milp")
        e = (res.x[:N] > 0.5).astype(np.uint8)
        st = "OPTIMAL" if res.status == 0 else "FEASIBLE"
        if ((self.H.tocsr() @ e.astype(float)) % 2 != syndrome).any():
            st = "INVALID"
        bound = getattr(res, "mip_dual_bound", np.nan)
        return ExactResult(e, st, float(self.w[e.astype(bool)].sum()), bound if bound is not None else np.nan, dt,
                           "milp")
