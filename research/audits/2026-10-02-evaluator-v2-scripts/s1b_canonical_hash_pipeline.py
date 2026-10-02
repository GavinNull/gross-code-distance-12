"""S1b：S1 的后果走一遍 pipeline（自检任务，临时成绩单）。

找一个“平移依赖”且通过 L0 的合法调度，用 pipeline.evaluate 提交**非规范**的平移代表：
L2 照常跑完，然后 _append 的 entry_problems 从规范调度重新生成电路，哈希对不上 → 写榜时抛 ValueError
（正式任务上意味着跑完几小时 L2 后整个评估崩掉）。另外比较两种平移代表生成的电路在同一 seed 下的分数。

用法：uv run python s1b_canonical_hash_pipeline.py
"""
import random
import tempfile
import traceback
from pathlib import Path

from common import cand, circuit_hash, deterministic, random_free_schedule, surface
from evaluators.l0 import check_l0
from evaluators import pipeline, tasks as T
from s1_canonical_hash import shifted

TASK = "selftest-surface-d3-sd6-paper"


def main():
    code, _ = surface(3)
    task = T.get_task(TASK)
    rng = random.Random(7)
    found = None
    for t in range(3000):
        D = rng.randint(6, 9)
        spec = random_free_schedule(code, D, rng)
        if spec is None or not deterministic(spec, code):
            continue
        hs = {s: circuit_hash(cand.build_circuits(shifted(spec, s), code, 3)) for s in range(D)}
        canon_h = circuit_hash(cand.build_circuits(spec.canonical(), code, 3))
        bad = [s for s in range(D) if hs[s] != canon_h]
        if not bad:
            continue
        sub = shifted(spec, bad[0])
        r = check_l0(cand.build_circuits(sub, code, 3), code, "both",
                     pipeline._l0_constraints(task, code, 3, with_distance=True))
        if r.passed:
            found = (sub, spec.canonical())
            print(f"trial {t}: found non-canonical shift whose circuit != canonical circuit; L0 passes, d_circ={r.d_circ}")
            break
    if not found:
        print("no example found")
        return
    sub, canon = found
    (Path(__file__).with_name("s1b_schedule_submitted.json")).write_text(__import__("json").dumps(sub.to_dict()))
    print("submitted:", sub.to_dict())
    print("hash(submitted) == hash(canonical):", sub.hash() == canon.hash())
    with tempfile.TemporaryDirectory() as td:
        board = Path(td) / "board.jsonl"
        for name, s in (("canonical", canon), ("submitted(non-canonical shift)", sub)):
            try:
                rep = pipeline.evaluate(TASK, None, s.to_dict(), seed=101, leaderboard_path=board)
                sc = rep.score["per_round_P_any"] if rep.score else None
                print(f"[{name}] status={rep.status} circuit_hash={rep.circuit_hashes} score={sc} "
                      f"written={'yes seq %d' % rep.leaderboard_record['seq'] if rep.leaderboard_record else 'no'} "
                      f"wall={rep.timing['wall_s']}s")
            except Exception as e:  # noqa: BLE001
                print(f"[{name}] evaluate RAISED {type(e).__name__}: {str(e)[:400]}")
                traceback.print_exc(limit=2)
        print("board lines:", len(board.read_text().splitlines()) if board.exists() else 0)


if __name__ == "__main__":
    main()
