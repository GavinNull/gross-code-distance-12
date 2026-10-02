# AI 原生研究流程（给 PI 看）

## 思路

传统做法是人做研究、AI 帮写代码。这里倒过来：**AI agent 做研究，人当 PI**。
人负责定方向、在关卡拍板、守住裁判的独立性；日常的选题、实验、记录、复核都交给 agent。

这件事在这个课题上能成立，是因为有一个客观的裁判（Stim 评估器）。
所以整套设计围绕一个问题展开：**怎样让 agent 全速跑，又不会自欺欺人。**

## 两层循环

| | 内循环 | 外循环 |
|---|---|---|
| 谁 | 搜索程序里的 LLM（API 调用） | Claude Code agent |
| 做什么 | 生成、变异候选调度或码 | 提假设、设计实验、分析结果、决定下一步 |
| 速度 | 每秒到每分钟一轮 | 每小时到每天一轮 |
| 位置 | `search/llm_evolve/` | `CLAUDE.md` + `research/` |

## 防自欺的四道闸

1. **冻结裁判**：评估器通过 G1 后冻结。hook 拦截 agent 对 `evaluators/` 的编辑，
   哈希清单可发现绕过 hook 的修改，每条 leaderboard 记录带评估器哈希。
2. **独立红队**：任何改进结论都要由新开的 `auditor` agent 独立复现并试图推翻。
3. **预注册**：实验跑之前必须写下预测，事后不许改。
4. **经典对照**：LLM 的结果必须和同算力的模拟退火比较。

## 你（PI）要做的事

- **关卡处拍板**：agent 到关卡会写报告到 `research/gates/`，在 `research/STATE.md` 的“待人决策”里提醒你，然后停下来。
- **写决定**：把决定写进 `research/decisions.md`（一行即可），agent 下次会话会读到。
- **冻结评估器**：G1 批准后亲手执行
  ```bash
  uv run python scripts/freeze_evaluator.py freeze
  ```
- **裁决评估器争议**：看 `research/evaluator_issues.md`。

## 日常怎么用

在 `~/Desktop/qec-ai-search` 目录开一个 Claude Code 会话，说一句“推进一轮研究”即可。
agent 会读 `STATE.md`、跑 `research-cycle`、结束前更新状态并提交 git。
想看进度，只需要读 `research/STATE.md`。

## 文件地图

| 文件 | 谁写 | 作用 |
|---|---|---|
| `CLAUDE.md` | 人 | agent 的研究宪法：铁律、流程、关卡 |
| `research/STATE.md` | agent | 现在在哪、下一步、待人决策 |
| `research/decisions.md` | 人 | 你的指示 |
| `research/hypotheses.md` | agent | 假设台账（含被推翻的） |
| `research/journal/` | agent | 每个实验一篇日志 |
| `research/audits/` | auditor | 红队复核报告 |
| `research/gates/` | agent | 关卡报告 |
| `research/leaderboard.jsonl` | 评估器脚本 | 唯一的成绩单 |
| `.claude/agents/` | 人 | lit-scout / experimenter / auditor |
| `.claude/skills/` | 人 | research-cycle / run-experiment / gate-review |
| `.claude/hooks/guard_frozen.py` | 人 | 保护裁判 |
