---
name: run-experiment
description: 单个实验的执行协议：按 experiments/<id>.yaml 运行、保存原始结果、写实验日志。lead agent 或 experimenter 执行任何实验时使用。
---

# 执行单个实验

## 运行前
1. 读 yaml，确认 `prediction` 已写好（没写就补上再跑，并注明“事后补写”）。
2. 记录 git commit：`git rev-parse --short HEAD`；有未提交改动就先提交，保证可复现。
3. 评估器已冻结时，先跑 `uv run python scripts/freeze_evaluator.py verify`，失败就停止并报告。

## 运行
- 原始输出写到 `results/<exp-id>/`（CSV / JSON / 日志）。
- 长任务放后台，定期看输出，不要干等。
- 超预算就停止并记录。

## 日志
写 `research/journal/YYYY-MM-DD-<exp-id>.md`：

```markdown
# <exp-id>
- 日期 / git commit / 评估器哈希：
- 假设：H-xxx
- 问题：
- 事先预测：
- 复现命令：

## 结果
（表格：配置 × 指标 × 置信区间；图放 results/<exp-id>/ 并链接）

## 与预测对比
符合 / 不符合，差多少？

## 异常与疑点
（任何看起来奇怪的地方，包括“好得不像真的”）

## 结论
一句话。是否需要 auditor 复核？
```

## 禁止
- 不要换种子挑好结果；所有种子的结果都要列出。
- 不要在看过结果后改 `prediction`。
- 不要删除失败运行的输出。
