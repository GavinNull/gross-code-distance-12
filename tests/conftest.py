import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session")
def selftest_runs(tmp_path_factory):
    """评估入口在自检任务上各跑一次（paper 与 diff），写进一个临时成绩单。多个测试共用，避免重复采样。

    返回 {"paper": Report, "diff": Report, "path": 成绩单路径, "schedule": 调度 dict}。"""
    from evaluators.pipeline import evaluate
    from schedule_helpers import surface_schedule

    _, spec = surface_schedule(3)
    path = tmp_path_factory.mktemp("board") / "board.jsonl"
    sched = spec.to_dict()
    paper = evaluate("selftest-surface-d3-sd6-paper", None, sched, seed=11, candidate_id="surface-std",
                     leaderboard_path=path)
    diff = evaluate("selftest-surface-d3-sd6-diff", None, sched, seed=12, candidate_id="surface-std",
                    leaderboard_path=path)
    return {"paper": paper, "diff": diff, "path": path, "schedule": sched}
