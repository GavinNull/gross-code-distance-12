"""S10 正式成绩单的守卫用字符串比较：`to_official = leaderboard_path is None or str(leaderboard_path) == str(DEFAULT_PATH)`。
传一个**指向同一文件的不同写法**（相对路径、带 ..、符号链接），“正式成绩单只收已冻结评估器 + purpose=score 的任务”
这两条就不检查了；verify_leaderboard() 的语义核对也不看 purpose / 评估器是否冻结。

在临时项目副本里做（副本自己的 research/leaderboard.jsonl），不碰真实成绩单。
用法：uv run python s10_official_path_bypass.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

CODE = r'''
import sys
sys.path.insert(0, "tests")
from schedule_helpers import surface_schedule
from evaluators import pipeline, leaderboard as lb
_, spec = surface_schedule(3)
print("DEFAULT_PATH:", lb.DEFAULT_PATH)
for p in (None, "research/leaderboard.jsonl", "research/../research/leaderboard.jsonl"):
    rep = pipeline.evaluate("selftest-surface-d3-sd6-paper", None, spec.to_dict(), seed=3, candidate_id=f"via {p}",
                            leaderboard_path=p)
    print(f"leaderboard_path={p!r}: status {rep.status}, written={rep.leaderboard_record is not None}, "
          f"ineligible={rep.ineligible_reasons}")
recs = lb.read_leaderboard()
print("official board (copy) lines:", len(recs), [(r["task_id"], r["purpose"], r["evaluator"]["frozen"]) for r in recs])
print("verify_leaderboard() =", lb.verify_leaderboard())
'''


def main():
    root = Path(tempfile.mkdtemp(prefix="s10_")).resolve() / "proj"
    for d in ("evaluators", "scripts", "tests", ".claude"):
        shutil.copytree(REPO / d, root / d, ignore=shutil.ignore_patterns("__pycache__", "worktrees"))
    for f in ("pyproject.toml", "uv.lock"):
        shutil.copy2(REPO / f, root / f)
    (root / "research").mkdir()
    (root / "research" / "leaderboard.jsonl").write_text("")
    env = dict(os.environ, PYTHONPATH=str(root))
    r = subprocess.run([sys.executable, "-c", CODE], cwd=root, env=env, capture_output=True, text=True)
    print(r.stdout)
    print(r.stderr[-2000:])
    print("copy:", root)


if __name__ == "__main__":
    main()
