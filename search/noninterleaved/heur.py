"""扩展码上的启发式短逻辑错误搜索（E-010，lead）。

求 min |x| s.t. He x = 0, Le x ≠ 0。复用评估器距离模块的两个矩阵级例程（只读使用）：
  _bposd_chunk  论文 2308.07915 Eq.(12) 的随机 η BP-OSD 搜索；
  _lns_chain    以解为中心、在 hops 跳邻域内用 CP-SAT 反复局部改进。
返回的是上界（每个解都经 _is_logical 核对）；找不到 ≤ cap 的解不构成证明。
"""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp

from evaluators.distance import _bposd_chunk, _is_logical, _lns_chain


def heur_min(He, Le, *, trials: int = 300, seed: int = 0, osd_order: int = 2, max_iter: int = 200,
             lns_starts: int = 8, lns_hops: int = 2, lns_det_time: float = 2.0, stop_at: int | None = None):
    D = sp.csc_matrix(He).astype(np.uint8)
    L = sp.csc_matrix(Le).astype(np.uint8)
    sols, done = _bposd_chunk(D, L, np.random.SeedSequence([seed, 1]), trials, osd_order, max_iter, None,
                              stop_at + 1 if stop_at is not None else None)
    best = None
    pool = sorted({s for _, s in sols}, key=len)
    for s in pool[:lns_starts]:
        if best is None or len(s) < len(best):
            best = list(s)
        if stop_at is not None and len(best) <= stop_at:
            break
        refined, _ = _lns_chain(D, L, list(s), lns_hops, lns_det_time, seed, max_chain=12, patience=2)
        if _is_logical(D, L, refined) and len(refined) < len(best):
            best = refined
        if stop_at is not None and len(best) <= stop_at:
            break
    return (len(best) if best is not None else None), best, {"bposd_trials": done, "bposd_solutions": len(sols)}
