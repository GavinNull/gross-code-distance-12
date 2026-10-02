"""S5 种子挑选：seed 由调用方给。submit=False（或写到临时成绩单）不留任何记录，搜索程序可以对同一调度
私下试 N 个种子，再用最好的种子做“第一次”正式提交；attempt 计数与“只按第一次排名”都挡不住。

另外比较：对调度做无关紧要的改动（换哈希）来“重抽”——README §11 已承认。

用法：uv run python s5_seed_shopping.py [N]
"""
import sys
import tempfile
from pathlib import Path

from common import surface
from evaluators import leaderboard as lb
from evaluators import pipeline

PAPER = "selftest-surface-d3-sd6-paper"


def main(N=12):
    _, spec = surface(3)
    sched = spec.to_dict()
    scores = {}
    for s in range(N):
        rep = pipeline.evaluate(PAPER, None, sched, seed=1000 + s, submit=False)
        scores[1000 + s] = (rep.score["per_round_P_any"], rep.l2["counts"])
        print(f"seed {1000 + s}: per-round P_any {rep.score['per_round_P_any']['best']:.4e} "
              f"[{rep.score['per_round_P_any']['low']:.4e}, {rep.score['per_round_P_any']['high']:.4e}] "
              f"fails Z/X {rep.l2['counts']['fail_Z']}/{rep.l2['counts']['fail_X']} shots {rep.l2['counts']['shots']}")
    best = min(scores, key=lambda k: scores[k][0]["best"])
    worst = max(scores, key=lambda k: scores[k][0]["best"])
    b, w = scores[best][0]["best"], scores[worst][0]["best"]
    print(f"best seed {best}: {b:.4e}; worst seed {worst}: {w:.4e}; best/worst = {b / w:.3f}; "
          f"best/median = {b / sorted(v[0]['best'] for v in scores.values())[N // 2]:.3f}")
    board = Path(tempfile.mkdtemp(prefix="s5_")) / "board.jsonl"
    rep = pipeline.evaluate(PAPER, None, sched, seed=best, candidate_id="seed-shopped", leaderboard_path=board)
    print(f"submitted with the best seed: attempt={rep.leaderboard_record['attempt']}, "
          f"table={[(r['candidate_id'], round(r['per_round_P_any'], 6), r['submissions']) for r in lb.table(PAPER, board)]}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 12)
