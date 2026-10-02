"""evaluators/codes.py 的测试。"""
from __future__ import annotations

import numpy as np
import pytest

from evaluators.codes import CSSCode, code_dimension, compute_logicals, rank, rotated_surface_code_from_stim

STEANE = np.array([[1, 0, 1, 0, 1, 0, 1], [0, 1, 1, 0, 0, 1, 1], [0, 0, 0, 1, 1, 1, 1]], dtype=np.uint8)


@pytest.mark.parametrize("d", [3, 5, 7])
def test_rotated_surface_code_parameters(d):
    code, data, c = rotated_surface_code_from_stim(d, "Z")
    assert code.n == d * d and code.k == 1
    assert code.HX.shape[0] + code.HZ.shape[0] == d * d - 1
    assert not code.check()
    assert int(code.LZ.sum()) >= d and int(code.LX.sum()) >= d


def test_steane_and_422():
    s = CSSCode.from_checks(STEANE, STEANE)
    assert (s.n, s.k) == (7, 1)
    c = CSSCode.from_checks(np.ones((1, 4), np.uint8), np.ones((1, 4), np.uint8))
    assert (c.n, c.k) == (4, 2)
    LX, LZ = compute_logicals(c.HX, c.HZ)
    assert np.array_equal((LX.astype(int) @ LZ.T) % 2, np.eye(2, dtype=int))


def test_rejects_noncommuting_stabilizers():
    HX = np.array([[1, 1, 0]], np.uint8)
    HZ = np.array([[0, 1, 1]], np.uint8)
    with pytest.raises(ValueError, match="do not commute"):
        CSSCode(HX, HZ, np.zeros((0, 3), np.uint8), np.zeros((0, 3), np.uint8))


def test_rejects_bad_logicals():
    code = CSSCode.from_checks(STEANE, STEANE)
    # 逻辑算符等于稳定子（平凡）
    with pytest.raises(ValueError):
        CSSCode(STEANE, STEANE, STEANE[:1], code.LZ)
    # 与稳定子反对易
    bad = code.LX.copy()
    bad[0, 0] ^= 1
    with pytest.raises(ValueError, match="anticommutes"):
        CSSCode(STEANE, STEANE, bad, code.LZ)
    # 个数不对
    with pytest.raises(ValueError, match="expected k=1"):
        CSSCode(STEANE, STEANE, np.vstack([code.LX, code.LX]), np.vstack([code.LZ, code.LZ]))


def test_logical_predicates():
    code, _, _ = rotated_surface_code_from_stim(3, "Z")
    assert code.is_logical_z(code.LZ[0]) and code.is_logical_x(code.LX[0])
    assert not code.is_logical_z(code.HZ[0])  # 稳定子
    assert not code.is_logical_z((code.LZ[0] ^ code.HZ[0]) * 0)  # 零向量
    assert code.is_logical_z(code.LZ[0] ^ code.HZ[0])  # 与 LZ 等价
    assert code_dimension(code.HX, code.HZ) == 1 and rank(code.HZ) == 4


def test_rejects_non_binary_entries():
    with pytest.raises(ValueError):
        CSSCode.from_checks(np.array([[2, 0]]), np.array([[0, 0]]))
