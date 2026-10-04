"""CpSatMLE 缓存回归（auditor 2026-10-04）：临时 problem 对象被回收后 id 可能被复用，
缓存里同一个 id 下的旧条目不得被当成新问题的数据。id 复用无法稳定触发，所以直接注入陈旧条目来模拟。"""
from types import SimpleNamespace

import numpy as np
import scipy.sparse as sp

from evaluators.decoder_mle import CpSatMLE


def _problem(L):
    # 两个机制都满足 syndrome [1]；先验 0.2 的机制 1 更可能，MLE 选它
    return SimpleNamespace(H=sp.csc_matrix(np.array([[1, 1]], dtype=np.uint8)),
                           L=sp.csr_matrix(np.array(L, dtype=np.uint8)),
                           priors=np.array([0.01, 0.2], dtype=np.float64))


def test_stale_cache_entry_under_reused_id_is_ignored():
    mle = CpSatMLE(time_limit_s=10)
    old = _problem([[0, 0]])                       # 旧问题：任何解都不翻转 observable
    stale = mle._prep(old)
    new = _problem([[0, 1]])                       # 新问题：机制 1 翻转 observable
    mle._cache[id(new)] = stale                    # 模拟 id 复用：新对象的 id 下挂着旧问题的数据
    r = mle.decode(new, np.array([1], dtype=np.uint8))
    assert r.optimal
    assert r.observables.tolist() == [1]           # 若误用旧数据会得到 [0]
