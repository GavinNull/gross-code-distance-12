"""近最优参考：逐 shot 最可能错误（MLE）解码（H-005，2026-10-03）。

只用于小样本上报告“离近最优还有多远”，不参与打分、不进速度预算。放在一个很薄的接口后面
（`NearOptimalDecoder`：`name`、`decode(problem, syndrome) -> NearOptResult`），以后 E-006 的 `search/decoders`
或别的精确 / 近似 MLE 解码器可以按同一接口接进来（由评估器侧的适配器调用，评估器本身不 import search/）。

`CpSatMLE`：在一个 sector 的解码问题上求
    min Σ_j w_j x_j   s.t.  H x = s (mod 2),  x ∈ {0,1}^M,   w_j = log((1-p_j)/p_j)
用 OR-Tools CP-SAT（奇偶约束写成带整数松弛变量的线性等式），权重按 `scale` 取整。时间上限内证明最优时 `optimal=True`；否则只是可行解
（报告里分开计数）。这是最可能**错误**（不是最可能的逻辑类，没有对简并求和），与 Tesseract / IP 解码器同口径。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

import numpy as np

__all__ = ["NearOptResult", "NearOptimalDecoder", "CpSatMLE", "get_near_optimal"]


@dataclass
class NearOptResult:
    observables: np.ndarray | None     # 预测的 observable 翻转（k,），None = 没找到解
    optimal: bool                      # 是否证明了最优
    weight: float | None               # Σ w_j x_j（未取整的真实值）
    wall_s: float
    status: str


class NearOptimalDecoder(Protocol):
    name: str

    def decode(self, problem, syndrome: np.ndarray) -> NearOptResult: ...


class CpSatMLE:
    name = "cpsat_mle"

    def __init__(self, time_limit_s: float = 60.0, num_workers: int = 1, scale: float = 1000.0):
        self.time_limit_s = float(time_limit_s)
        self.num_workers = int(num_workers)
        self.scale = float(scale)
        self._cache: dict = {}

    def _prep(self, problem):
        # 缓存同时保存 problem 本身的强引用，并核对身份：只用 id() 做键时，临时对象被回收后 id 会被复用，
        # 会静默返回另一个问题的 H/w/L 并照样报 OPTIMAL（auditor 2026-10-04 发现）。
        key = id(problem)
        hit = self._cache.get(key)
        if hit is not None and hit[0] is problem:
            return hit[1]
        H = problem.H.tocsr()
        rows = [H.indices[H.indptr[i]:H.indptr[i + 1]].tolist() for i in range(H.shape[0])]
        p = np.clip(np.asarray(problem.priors, dtype=np.float64), 1e-15, 0.5 - 1e-12)
        w = np.log((1 - p) / p)
        data = (rows, w, problem.L.tocsr())
        self._cache[key] = (problem, data)
        return data

    def decode(self, problem, syndrome: np.ndarray) -> NearOptResult:
        import time

        from ortools.sat.python import cp_model
        rows, w, L = self._prep(problem)
        t0 = time.perf_counter()
        s = np.asarray(syndrome, dtype=np.uint8)
        if not s.any():
            return NearOptResult(np.zeros(L.shape[0], dtype=np.uint8), True, 0.0, 0.0, "TRIVIAL")
        m = cp_model.CpModel()
        x = [m.NewBoolVar(f"x{j}") for j in range(len(w))]
        for i, cols in enumerate(rows):
            # 奇偶约束写成线性等式 Σ x_j − 2 t_i = s_i（CP-SAT 对这种形式比 AddBoolXOr 快得多：BB72 上 0.2–1 s / shot，
            # AddBoolXOr 在 30 s 内一个都证明不了最优）
            t = m.NewIntVar(0, len(cols) // 2, f"t{i}")
            m.Add(sum(x[j] for j in cols) - 2 * t == int(s[i]))
        m.Minimize(sum(int(round(self.scale * w[j])) * x[j] for j in range(len(w))))
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.time_limit_s
        solver.parameters.num_workers = self.num_workers
        solver.parameters.random_seed = 0
        st = solver.Solve(m)
        wall = time.perf_counter() - t0
        name = solver.StatusName(st)
        if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return NearOptResult(None, False, None, wall, name)
        e = np.array([solver.Value(v) for v in x], dtype=np.uint8)
        obs = (L @ e) % 2
        return NearOptResult(np.asarray(obs).astype(np.uint8).ravel(), st == cp_model.OPTIMAL,
                             float(w[e.astype(bool)].sum()), wall, name)


def get_near_optimal(spec: dict) -> NearOptimalDecoder:
    method = (spec or {}).get("method", "cpsat_mle")
    if method == "cpsat_mle":
        return CpSatMLE(time_limit_s=float(spec.get("time_limit_s", 60.0)), num_workers=int(spec.get("num_workers", 1)))
    raise ValueError(f"unknown near-optimal decoder {method!r}")


def _weight(p: float) -> float:
    return math.log((1 - p) / p)
