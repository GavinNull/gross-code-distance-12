"""evaluators/stats.py 的测试。"""
from __future__ import annotations

import pytest

from evaluators.stats import (
    DEFAULT_LIKELIHOOD_FACTOR,
    binomial_interval,
    likelihood_factor_to_sigma,
    sigma_to_likelihood_factor,
)


def test_sigma_conversion():
    assert likelihood_factor_to_sigma(1000) == pytest.approx(3.717, abs=1e-3)
    assert sigma_to_likelihood_factor(1.96) == pytest.approx(6.83, abs=1e-2)
    assert likelihood_factor_to_sigma(sigma_to_likelihood_factor(2.5)) == pytest.approx(2.5)


def test_interval_label_states_sigma_not_95_percent():
    iv = binomial_interval(200, 100_000)
    assert iv.low < iv.best < iv.high
    assert iv.likelihood_factor == DEFAULT_LIKELIHOOD_FACTOR
    assert "3.72σ" in iv.label() and "95" not in iv.label()
    # 95% 区间更窄
    iv95 = binomial_interval(200, 100_000, sigma_to_likelihood_factor(1.96))
    assert iv.low < iv95.low < iv95.high < iv.high


def test_rejects_bad_counts():
    with pytest.raises(ValueError):
        binomial_interval(5, 0)
