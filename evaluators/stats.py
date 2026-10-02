"""统计约定（评估器统一口径）。

1. 置信区间一律用**似然比区间**（sinter.fit_binomial 的 max_likelihood_factor），并且每次报告都要
   写出对应的 σ 数。按 Wilks 近似，似然比因子 F 对应 z = sqrt(2 ln F) 个标准差：
     F = 1000  ->  z ≈ 3.72σ（双侧约 99.98%）。E-001 用的就是它，曾被误标为 “95%”（auditor M1）。
     F ≈ 6.83  ->  z = 1.96σ（95%）。
   默认 DEFAULT_LIKELIHOOD_FACTOR = 1000，标签写作 “LR=1000 (≈3.72σ)”，不写 “95%”。
2. 对比实验（候选 vs baseline）每个数据点至少 MIN_LOGICAL_ERRORS_FOR_COMPARISON = 1000 次逻辑错误，
   X、Z 两个基底都要达到（auditor M4、H2）。
3. 本模块与 L0 / 噪声模块都没有随机性；L2 采样的种子必须由显式参数给出并写进结果（auditor M3）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

DEFAULT_LIKELIHOOD_FACTOR = 1000.0
MIN_LOGICAL_ERRORS_FOR_COMPARISON = 1000


def likelihood_factor_to_sigma(factor: float) -> float:
    """似然比因子 -> 等价的标准差数（Wilks 近似，单参数）。"""
    if factor < 1:
        raise ValueError("likelihood factor must be >= 1")
    return math.sqrt(2 * math.log(factor))


def sigma_to_likelihood_factor(sigma: float) -> float:
    return math.exp(sigma * sigma / 2)


@dataclass(frozen=True)
class BinomialInterval:
    errors: int
    shots: int
    best: float
    low: float
    high: float
    likelihood_factor: float

    @property
    def sigma(self) -> float:
        return likelihood_factor_to_sigma(self.likelihood_factor)

    def label(self) -> str:
        return (f"{self.best:.3e} [{self.low:.3e}, {self.high:.3e}] "
                f"(LR={self.likelihood_factor:g} interval, ≈{self.sigma:.2f}σ; {self.errors}/{self.shots})")


def binomial_interval(errors: int, shots: int,
                      likelihood_factor: float = DEFAULT_LIKELIHOOD_FACTOR) -> BinomialInterval:
    """二项比例的似然比区间（用 sinter.fit_binomial）。"""
    import sinter

    if shots <= 0 or not (0 <= errors <= shots):
        raise ValueError(f"invalid counts errors={errors}, shots={shots}")
    fit = sinter.fit_binomial(num_shots=shots, num_hits=errors, max_likelihood_factor=likelihood_factor)
    return BinomialInterval(errors, shots, fit.best, fit.low, fit.high, likelihood_factor)
