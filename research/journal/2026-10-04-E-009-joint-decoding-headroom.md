# E-009 · 联合（X/Z）解码的提升空间

- 日期：2026-10-04 / 执行者：lead / git commit：见本文件提交 / 评估器：未冻结
- 假设：H-005
- 复现命令：
  ```bash
  PYTHONPATH=. uv run python search/experiments/e009/relay_only.py        # Relay 分 sector 对联合，6000 shot
  uv run python -m search.experiments.e009.joint --code bb72 --p 0.004 --shots 2000 --batch 25 --workers 4   # 四解码器（未完成）
  ```

## 事先预测
1) 联合 MLE 比分 sector MLE 好 3–10 倍；2) 联合 Relay 比分 sector Relay 好 2–5 倍；3) 联合 Relay / 联合 MLE 在 2–5 倍。

## 结果
- **Relay 分 sector 对联合**（BB72，sd6，p=4e-3，6000 shot，种子 20261004，Relay5 参数）：分 sector 失败 492，**联合失败 208**（好 2.37 倍），两者都失败 137。
  `results/E-009-joint-decoding-headroom/bb72_relay_sector_vs_joint.json`。
- **四解码器对比未完成**：联合 DEM 有 17928 个机制（单 sector 2232 个）。联合 MLE 用 HiGHS MILP 时，30 s 时限内 25 个 shot 有 11 个超时（机器同时运行 E-007）；
  改用 CP-SAT（`evaluators/decoder_mle.py` 的写法），8 个 shot 里仍有 2 个在 30 s 内无法证明最优（1 线程和 4 线程都是如此）。运行已由 lead 按 PID 停止，部分记录保留在 `results/E-009-joint-decoding-headroom/bb72_p0.004_records.jsonl`（25 shot，不用于结论）。

## 与预测对比
- 2) **符合**（2.37 倍，在 2–5 倍内）。
- 1)、3) **无法检验**：精确的联合 MLE 在本机上不可行。

## 推理与结论
- X/Z 关联是解码器最大的杠杆，但**官方 Relay-BP 直接跑在联合 DEM 上就已经拿走了这 2.4 倍**，甚至优于分 sector 的理论最优（约 492/1.29≈380）。
- 剩下的空间（联合 Relay 对联合最优）**本机无法测量**；而真正的大空间在 gross、低 p，正是 Tesseract、Cascade、telescoping 等组带着 GPU / 近最优解码器在攻的区间。
- 评估器的解码器任务规定分 sector 解码，排除了最大的杠杆。如果以后继续解码器线，任务必须改为联合解码（DEM 大 8 倍）。
- **结论（lead，依据 E-006、E-008、E-009）**：在本项目的条件下，解码器线没有现实可行的颠覆性路径。暂停 H-005，回到 H-004。
