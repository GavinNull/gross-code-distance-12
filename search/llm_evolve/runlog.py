"""运行目录、JSONL 日志、断点文件、带缓存的评估器（LLM 搜索与经典基线共用）。

目录布局 ``results/<run-id>/``：
    config.json        运行配置 + 问题指纹 + 客户端描述
    evaluations.jsonl  每次**唯一**评估一行（缓存命中不重复记录）
    llm_calls.jsonl    （仅 LLM 搜索）每次 LLM 调用一行：prompt、回复、提取的程序、评估结果、token
    state.json         断点（原子写入）；记录各 JSONL 的字节偏移，续跑时截断到该偏移
    summary.json       结束时的摘要（最优程序、预算使用、停止原因）
    best_program.py    最优程序源码
"""

from __future__ import annotations

import json
import math
import os
import threading
import time
from pathlib import Path
from typing import Any

from .database import program_hash
from .problem import EvalResult, Problem

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "results"


def _json_default(o: Any) -> Any:
    if isinstance(o, float) and not math.isfinite(o):
        return None
    if hasattr(o, "tolist"):
        return o.tolist()
    if isinstance(o, (set, frozenset, tuple)):
        return list(o)
    return str(o)


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=_json_default)


def atomic_write_json(path: Path, obj: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=1, default=_json_default))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


class JsonlLog:
    """追加写 JSONL；``offset`` 是已提交（已进入断点）的字节数。"""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        path.touch(exist_ok=True)

    def append(self, record: dict[str, Any]) -> None:
        line = dumps(record) + "\n"
        with self._lock, open(self.path, "a") as f:
            f.write(line)

    def offset(self) -> int:
        return self.path.stat().st_size

    def truncate(self, offset: int) -> None:
        """续跑时丢弃断点之后（崩溃前未提交）的记录，避免重复。"""
        with open(self.path, "r+b") as f:
            f.truncate(offset)

    def read(self) -> list[dict[str, Any]]:
        with open(self.path) as f:
            return [json.loads(ln) for ln in f if ln.strip()]


class CachedEvaluator:
    """按规范化源码哈希去重的评估器包装。只有缓存未命中才调用 ``problem.evaluate`` 并计数。"""

    def __init__(self, problem: Problem, log: JsonlLog | None = None,
                 cache: dict[str, dict[str, Any]] | None = None, n_evals: int = 0,
                 n_cache_hits: int = 0):
        self.problem = problem
        self.log = log
        self.cache: dict[str, dict[str, Any]] = dict(cache or {})
        self.n_evals = n_evals
        self.n_cache_hits = n_cache_hits

    def lookup(self, src: str) -> tuple[str, EvalResult | None]:
        h = program_hash(src)
        hit = self.cache.get(h)
        return h, (EvalResult.from_dict(hit) if hit is not None else None)

    def raw_evaluate(self, src: str) -> tuple[EvalResult, float]:
        """直接调用问题的评估入口（线程安全，不改内部状态）。评估器自身抛异常记为 invalid。"""
        t0 = time.perf_counter()
        try:
            res = self.problem.evaluate(src)
            if not isinstance(res, EvalResult):
                raise TypeError(f"Problem.evaluate returned {type(res).__name__}, expected EvalResult")
        except Exception as e:  # noqa: BLE001
            res = EvalResult.invalid(f"evaluator error: {type(e).__name__}: {e}", evaluator_error=True)
        return res, time.perf_counter() - t0

    def record(self, h: str, src: str, res: EvalResult, elapsed: float, context: dict[str, Any]) -> int:
        """登记一次新评估（写缓存 + 日志），返回评估序号（从 1 开始）。"""
        self.n_evals += 1
        self.cache[h] = res.to_dict()
        if self.log is not None:
            self.log.append({"eval_index": self.n_evals, "hash": h, **res.to_dict(),
                             "context": context, "src": src, "timing": {"eval_s": round(elapsed, 4)}})
        return self.n_evals

    def evaluate(self, src: str, context: dict[str, Any] | None = None) -> tuple[str, EvalResult, bool, int | None]:
        """返回 (hash, result, cache_hit, eval_index)。"""
        h, cached = self.lookup(src)
        if cached is not None:
            self.n_cache_hits += 1
            return h, cached, True, None
        res, elapsed = self.raw_evaluate(src)
        idx = self.record(h, src, res, elapsed, context or {})
        return h, res, False, idx

    def state_dict(self) -> dict[str, Any]:
        return {"cache": self.cache, "n_evals": self.n_evals, "n_cache_hits": self.n_cache_hits}


def make_run_dir(run_id: str, results_dir: str | Path | None = None, *, must_exist: bool = False) -> Path:
    base = Path(results_dir) if results_dir is not None else DEFAULT_RESULTS_DIR
    d = base / run_id
    if must_exist and not (d / "state.json").exists():
        raise FileNotFoundError(f"no checkpoint at {d / 'state.json'}")
    d.mkdir(parents=True, exist_ok=True)
    return d


def best_so_far_curve(run_dir: str | Path) -> list[tuple[int, float]]:
    """从 evaluations.jsonl 计算“第 i 次评估时的最优合法分数”，用于在相同评估次数下比较不同搜索器。"""
    log = JsonlLog(Path(run_dir) / "evaluations.jsonl")
    best = -math.inf
    out = []
    for r in log.read():
        if r["valid"] and r["score"] > best:
            best = r["score"]
        out.append((r["eval_index"], best))
    return out


def best_at(curve: list[tuple[int, float]], n_evals: int) -> float:
    """曲线在第 n_evals 次评估时的最优分数（没有合法程序时返回 -inf）。"""
    best = -math.inf
    for i, s in curve:
        if i > n_evals:
            break
        best = s
    return best
