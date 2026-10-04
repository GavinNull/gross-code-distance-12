"""CPU 记账：候选 CPU（sector cpu_total_s 之和）+ 构建（每次评估约 3 worker x 2 sector x ~1.8 s，按 11 s 估）+ 参考一次
（评估器进程内缓存，每个 SA 进程 / 每个 task 只跑一次）。无法精确记的部分（沙箱启动、父进程采样）不计，约 <5%。"""
import json, sys
from pathlib import Path
tot = {}
for d in sorted(Path("results/E-007-relay-sa-tuning").glob("sa-*")):
    n = 0; cand = 0.0; ref = 0.0
    for l in (d / "evaluations.jsonl").read_text().splitlines():
        r = json.loads(l); m = r["metrics"]; n += 1
        if "sectors" in m:
            cand += sum(s["cpu_total_s"] for s in m["sectors"].values()) + 11
            sp = m["speed"]; sh = m["counts"]["shots"]
            if "reference_cpu_per_shot_ms" in sp: ref = sp["reference_cpu_per_shot_ms"] * 1e-3 * sh
        else:
            cand += m["speed"]["cpu_total_s"]
    print(f"{d.name}: evals={n} cand_cpu={cand/3600:.2f}h ref_cpu={ref/3600:.2f}h")
    tot[d.name] = (cand + ref) / 3600
print("total h", round(sum(tot.values()), 2))
