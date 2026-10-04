"""E-007 公共代码：任务参数、CPU 记账、退火超参（跑前固定）。只通过评估器公开入口 + 官方 relay_bp 包。"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "results" / "E-007-relay-sa-tuning"
SECRET = os.path.expanduser("~/.qec-ai-search-tmp/e007.key")   # 临时密钥：结果不能上榜

# 搜索集前缀：yaml 写“BB72 约 4 万 shot”，但评估器的 BB72 搜索集只有 20000 shot（decoder.search.shots，
# 超过会 ValueError），所以用整个搜索集；BB90 用全部 10000。
SHOTS = {"bb72-dec-p3e-3": 20000, "bb90-dec-p3e-3": 10000}
# 退火温度与分数（-P_any）同量纲，按基线 P_any 的量级与采样噪声设定（跑前固定，不再调）。
TEMPS = {"bb72-dec-p3e-3": (2.0e-3, 2.0e-4), "bb90-dec-p3e-3": (4.0e-4, 4.0e-5)}


def use_temp_secret():
    os.environ["QEC_DECODER_SECRET_FILE"] = SECRET


def cpu_of_eval(metrics: dict, shots: int) -> float:
    """候选一次评估的 CPU 秒（两个 sector 之和，不含构建）。"""
    sp = metrics.get("speed") or {}
    return float(sp.get("cpu_per_shot_ms", 0.0)) * 1e-3 * shots


def load_evals(run_dir) -> list[dict]:
    p = Path(run_dir) / "evaluations.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
