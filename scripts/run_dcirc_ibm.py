"""评估器 v2.1：在 IBM 项顺序调度（E-004 的构造）上跑一遍所有 *-dcirc 任务（pipeline.screen，不写榜）。

用法：uv run python scripts/run_dcirc_ibm.py [task_id ...]
输出：results/evaluator-v2.1-dcirc/<task>.json 与 <task>.txt（Report.to_text()），并在 stdout 打印汇总行。
只读调用 search / baselines 来构造 IBM 调度（脚本，不是评估器）。3 个进程（任务的 num_workers）。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

from evaluators import pipeline  # noqa: E402
import v21_helpers as H  # noqa: E402

TASKS = ["bb72-dcirc", "bb90-dcirc", "bb108-dcirc", "bb120-dcirc", "cp126-dcirc", "gross-dcirc"]


def main(tids):
    out = ROOT / "results" / "evaluator-v2.1-dcirc"
    out.mkdir(parents=True, exist_ok=True)
    for tid in tids:
        code, spec = H.dcirc_ibm_spec(tid)
        t0 = time.time()
        rep = pipeline.screen(tid, None, spec.to_dict())
        wall = time.time() - t0
        (out / f"{tid}.txt").write_text(rep.to_text())
        (out / f"{tid}.json").write_text(json.dumps(rep.to_dict(), default=str, indent=1))
        dd = rep.distance or {}
        per = {b: v.get("weight") for b, v in (dd.get("per_basis") or {}).items()}
        ex = next((v["coords"][:3] for v in (dd.get("per_basis") or {}).values() if v.get("coords")), [])
        print(json.dumps({"task": tid, "status": rep.status, "score": rep.score and {k: rep.score[k] for k in (
            "d_circ_upper_bound", "low_weight_witnesses", "period")}, "per_basis": per, "seed": rep.seed,
            "wall_s": round(wall, 1), "witness_example": [c["text"] for c in ex]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:] or TASKS)
