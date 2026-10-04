"""留出集复核（临时密钥，不能上榜）。
- bb72：直接走公开入口 evaluate_decoder(split="holdout", submit=False)，停止规则是任务自带的（每 sector >= 1000 次失败）。
- bb90：1000 次失败太贵（见 README 12.7，约 14-21 CPU 小时/个）。按任务要求降到每 sector >= 100 次失败：把进程内
  已注册任务的 stop.min_sector_errors 改成 100、max_errors 改成 0（只改本进程内存里的对象，不改文件），再调评估器内部的
  `_evaluate`（不是公开入口）。这会改变任务哈希，所以 bb90 的留出集 shot 流与“正式任务哈希”下的不同，但同一进程里的所有候选和
  参考共用同一条流，成对比较有效；结果不能上榜。
用法: holdout.py <task> <run_dir> <eval_index,...> [tag]
"""
import json
import sys
import time

from search.experiments.e007 import common as C

C.use_temp_secret()
from evaluators import decoder_eval as DE  # noqa: E402
from evaluators.tasks import get_task  # noqa: E402

task_id, run_dir, idxs = sys.argv[1], sys.argv[2], [int(x) for x in sys.argv[3].split(",")]
tag = sys.argv[4] if len(sys.argv) > 4 else "holdout"
evals = {r["eval_index"]: r for r in C.load_evals(run_dir)}
task = get_task(task_id)
if task_id.startswith("bb90"):
    task.stop["min_sector_errors"] = 100      # 进程内改动（本实验的降级要求）
    task.stop["max_errors"] = 0
out = []
for i in idxs:
    src = evals[i]["src"]
    t0 = time.perf_counter()
    if task_id.startswith("bb90"):
        s, err = DE._resolve_program(task, src, False)
        assert not err
        rep = DE._evaluate(task, src, s, split="holdout", shots=None, candidate_id=f"e007-{i}", leaderboard_path=None,
                           submit=False, num_workers=3, use_os_sandbox=None, with_features=False, t0=t0)
        rep = DE._finish(rep, t0)
    else:
        rep = DE.evaluate_decoder(task_id, src, split="holdout", submit=False, num_workers=3, with_features=False)
    d = {"eval_index": i, "status": rep.status, "shots": rep.shots, "counts": rep.counts, "rates": rep.rates,
         "ref_counts": rep.reference["counts"], "ref_rates": rep.reference["rates"], "speed": rep.speed,
         "overlap": rep.overlap, "sectors": {s_: {k: v for k, v in st.items() if k != "build_cpu_s"}
                                              for s_, st in rep.sectors.items()},
         "search_score": evals[i]["score"], "wall_s": time.perf_counter() - t0, "stop": dict(task.stop),
         "temp_secret": True}
    print(json.dumps(d), flush=True)
    out.append(d)
    json.dump(out, open(str(C.RESULTS / f"{tag}-{task_id.split('-')[0]}.json"), "w"), indent=1)
