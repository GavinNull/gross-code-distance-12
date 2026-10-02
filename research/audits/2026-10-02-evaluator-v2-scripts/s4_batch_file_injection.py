"""S4 L2 批文件注入：另一个进程（只知道目录位置，不 import 评估器、不碰凭证）改写 sample_l2 的批结果文件。

sample_l2 把每批结果写成 <state_dir>/batch_<i>.json，之后**原样信任**这些文件（shots、失败数都不核对：
不检查 shots == batch_size、不由 bits 重算失败数、不检查 index 与文件名一致）。pipeline.evaluate 的公开参数
work_dir 让调用方决定这个目录；不传时目录是 $TMPDIR/l2_*（同一用户可见）。

攻击进程：轮询目录，一旦 batch_000000000.json 出现就用 os.replace 换成
{"shots": 10^7, "fail_Z": 1000, "fail_X": 1000, "fail_any": 1999, ...}。前缀规则在第 0 批就满足停止条件。

  A  evaluate(..., work_dir=<调用方目录>)
  B  evaluate(..., work_dir=None)，攻击进程扫描 $TMPDIR 里新出现的 l2_* 目录

结果写进临时成绩单（不碰 research/leaderboard.jsonl）。
用法：uv run python s4_batch_file_injection.py
"""
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from common import surface
from evaluators import leaderboard as lb
from evaluators import pipeline

PAPER = "selftest-surface-d3-sd6-paper"

ATTACKER = r'''
import json, os, sys, time, glob
mode, target, deadline = sys.argv[1], sys.argv[2], time.time() + float(sys.argv[3])
fake = {"index": 0, "stim_seed": 0, "shots": 10**7, "fail_Z": 1000, "fail_X": 1000, "fail_any": 1999,
        "fail_both": 1, "bits_Z": "", "bits_X": "", "cpu_s": 0.0}
done = set()
before = set(glob.glob(os.path.join(target, "l2_*"))) if mode == "scan" else set()
while time.time() < deadline:
    dirs = [target] if mode == "dir" else [d for d in glob.glob(os.path.join(target, "l2_*")) if d not in before]
    for d in dirs:
        f = os.path.join(d, "batch_000000000.json")
        if d not in done and os.path.exists(f):
            tmp = os.path.join(d, ".x.tmp")
            open(tmp, "w").write(json.dumps(fake))
            os.replace(tmp, f)
            done.add(d)
            print("attacker: replaced", f, flush=True)
    time.sleep(0.001)
'''


def run(label, work_dir, attacker_args, board):
    _, spec = surface(3)
    atk = subprocess.Popen([sys.executable, "-c", ATTACKER, *attacker_args], stdout=subprocess.PIPE, text=True)
    time.sleep(0.5)
    try:
        rep = pipeline.evaluate(PAPER, None, spec.to_dict(), seed=11, candidate_id=f"injected-{label}",
                                leaderboard_path=board, work_dir=work_dir)
    finally:
        atk.terminate()
        out = atk.communicate()[0]
    print(out.strip())
    s = rep.score["per_round_P_any"] if rep.score else None
    print(f"[{label}] status {rep.status}; counts {rep.l2 and rep.l2['counts']}; per-round P_any "
          f"{s and round(s['best'], 7)}; written to board: {rep.leaderboard_record is not None}")
    return rep


def main():
    td = Path(tempfile.mkdtemp(prefix="s4_"))
    board = td / "board.jsonl"
    _, spec = surface(3)
    hon = pipeline.evaluate(PAPER, None, spec.to_dict(), seed=11, candidate_id="honest", submit=False)
    print(f"[honest] per-round P_any {hon.score['per_round_P_any']['best']:.4e}, counts {hon.l2['counts']}")
    wd = td / "work"
    run("A work_dir", str(wd), ["dir", str(wd), "120"], board)
    run("B default tmp dir", None, ["scan", tempfile.gettempdir(), "120"], board)
    print("verify_leaderboard(board) =", lb.verify_leaderboard(board))
    print("table:", [(r["candidate_id"], r["per_round_P_any"]) for r in lb.table(PAPER, board)])


if __name__ == "__main__":
    main()
