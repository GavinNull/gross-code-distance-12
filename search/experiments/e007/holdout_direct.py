"""不受速度预算限制的留出集复核：论文参数 与 若干配置（直接调官方包）在同一批留出集 shot 上，成对比较。
轮次制：每轮 12 个批（3 个 worker x 4 批，每轮重建解码器），累计到论文参数和各候选都达到每 sector >= target 次失败为止。
留出集由临时密钥派生（不能上榜）。bb90 的 stop 规则里每 sector 要 1000 次失败，太贵，这里用 target（默认 100）。
用法: holdout_direct.py <task> <target> <run_dir> <eval_index,...>
"""
import json
import sys
import time

import numpy as np

from search.experiments.e007 import common as C

C.use_temp_secret()
from search.experiments.e007 import direct  # noqa: E402
from evaluators import decoder_problem as dp  # noqa: E402
from evaluators.tasks import get_task  # noqa: E402

task_id, target, run_dir = sys.argv[1], int(sys.argv[2]), sys.argv[3]
idxs = [int(x) for x in sys.argv[4].split(",")]
max_rounds = int(sys.argv[5]) if len(sys.argv) > 5 else 40
task = get_task(task_id)
inst = dp.build_instance(task)
root = dp.split_root(task.task_id, task.hash(), "holdout")
bs = int(task.stop["batch_size"])
PER_ROUND = 12
evals = {r["eval_index"]: r for r in C.load_evals(run_dir)}
paper = dict(task.decoder["reference"]["params"])
cfgs = {"paper": paper}
for i in idxs:
    cfgs[f"e{i}"] = evals[i]["metrics"]["params"]
acc = {k: {"fz": [], "fx": [], "cz": [], "cx": []} for k in cfgs}
direct._STATE.update(task=task, inst=inst, bs=bs, task_id=task_id, batches={})
base_cpu = None
t0 = time.time()
rounds = 0
while rounds < max_rounds:
    ids = list(range(rounds * PER_ROUND, (rounds + 1) * PER_ROUND))
    for b in ids:
        direct._STATE["batches"][b] = dp.sample_batch(inst, root, b, bs)
    for k, params in cfgs.items():
        cap = None if (base_cpu is None or k == "paper") else {s: direct.K_UNRES * base_cpu[s] for s in ("Z", "X")}
        r = direct.run(params, 3, cap, batch_ids=ids)
        for s in ("Z", "X"):
            acc[k]["f" + s.lower()].append(r["fail_" + s])
            acc[k]["c" + s.lower()].append(r["cpu_" + s])
        if k == "paper" and base_cpu is None:
            base_cpu = {s: float(r["cpu_" + s].mean()) for s in ("Z", "X")}
    for b in ids:
        direct._STATE["batches"].pop(b)
    rounds += 1
    cnt = {k: (int(np.concatenate(v["fz"]).sum()), int(np.concatenate(v["fx"]).sum())) for k, v in acc.items()}
    print(f"round {rounds} shots {rounds * PER_ROUND * bs} counts(Z,X) {cnt} t={time.time() - t0:.0f}s", flush=True)
    if all(min(c) >= target for c in cnt.values()):
        break
out = {"task": task_id, "target_per_sector": target, "shots": rounds * PER_ROUND * bs, "temp_secret": True, "cfgs": cfgs}
for k, v in acc.items():
    fz, fx = np.concatenate(v["fz"]), np.concatenate(v["fx"])
    cz, cx = np.concatenate(v["cz"]), np.concatenate(v["cx"])
    out[k] = {"fail_Z": int(fz.sum()), "fail_X": int(fx.sum()), "fail_any": int((fz | fx).sum()),
              "cpu_Z_s": float(cz.sum()), "cpu_X_s": float(cx.sum())}
    np.savez_compressed(str(C.RESULTS / f"holdout-direct-{task_id.split('-')[0]}-{k}.npz"), fz=fz, fx=fx, cz=cz, cx=cx)
json.dump(out, open(str(C.RESULTS / f"holdout-direct-{task_id.split('-')[0]}.json"), "w"), indent=1)
print("done", json.dumps(out)[:2000])
