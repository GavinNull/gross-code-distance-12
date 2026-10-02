---
name: research-cycle
description: 推进一轮研究循环：读状态、选假设、设计实验、派发执行、记录结果、更新状态。lead agent 每次要“往前推一步”时使用。
---

# 一轮研究循环

## 1. 定位
- 读 `research/STATE.md`、`research/decisions.md`（最新几条）、`research/hypotheses.md`。
- 有未答复的“待人决策”时，只做与之无关的工作。
- 已到达关卡 → 停止，改用 `gate-review`。

## 2. 选题
从 STATE 的“下一步”或 `open` 的假设里挑**一个**最能减少不确定性的。
优先级：能推翻核心假设的实验 > 能解锁关卡的实验 > 改进型实验。
新方向先派 `lit-scout` 确认没人做过。

## 3. 设计
写 `experiments/<exp-id>.yaml`（exp-id 格式 `E-NNN-短名`）：

```yaml
id: E-001-surface-baseline
hypothesis: H-001          # 或 baseline / infra
question: 一句话：这个实验要回答什么？
prediction: 跑之前写下你预期的结果（防止事后合理化）
command: uv run python -m baselines.surface --config experiments/E-001-surface-baseline.yaml
seeds: [0, 1, 2]
noise: {model: uniform_depolarizing, p: [0.001, 0.002, 0.003, 0.005]}
budget: {cpu_hours: 2, llm_tokens: 0}
stop_rule: 每个点收集 ≥100 次逻辑错误或 1e7 shots
```

## 4. 执行
- 小实验自己跑；独立的多个实验并行派发 `experimenter`，每个 agent 一个 yaml。
- 跑超过几分钟的命令放后台运行，不要干等。

## 5. 记录
- 确认每个实验都有 `research/journal/` 条目。
- 更新 `hypotheses.md`：把实验 id 加进“相关实验”，必要时改状态。
- 结果看起来是改进 → **先派 `auditor`**，复核通过才能写进 STATE 的“已确认结果”。

## 6. 收尾
- 更新 `research/STATE.md`（做了什么、下一步、新的待人决策）。
- `git add -A && git commit -m "<exp-id>: <一句话结论>"`
