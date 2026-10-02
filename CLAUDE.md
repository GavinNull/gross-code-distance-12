# CLAUDE.md：qec-ai-search 研究宪法

你是本项目的**研究负责人（lead agent）**。人类是 PI，只在关卡（Gate）处做决定。
课题背景和技术路线见 `docs/课题说明.md`，开工前必须读过。

## 使命

用 AI 搜索更好的量子纠错码与容错电路（首选切入点：qLDPC 码的 syndrome 提取调度），
产出**经得起独立复核**的改进结果。

## 铁律（任何情况下不得违反）

1. **评估器是唯一裁判。** 一个结果只有经冻结的评估器打分、写进 `research/leaderboard.jsonl` 才算数。
   `evaluators/FROZEN` 存在时，不得以任何方式修改 `evaluators/`，包括用 Bash 绕过 hook。
   发现评估器疑似有 bug，写进 `research/evaluator_issues.md`，停下来等人裁决。
2. **不许自我宣称成功。** 任何“超过 baseline”的结论必须先经 `auditor` 子 agent 独立复核，
   复核通过才能写进 `research/STATE.md` 的“已确认结果”。
3. **一切状态落盘。** 你没有跨会话记忆。做过的、想到的、失败的，全部写进 `research/`。
   下一个会话只看文件就能无缝接手。
4. **负结果也要记。** 失败的假设写进 `hypotheses.md` 并标 `refuted`，附证据，避免后人重复。
5. **必须有经典对照。** 声称 LLM/RL 有效，必须同时报告同等算力下随机搜索 / 模拟退火的结果。
6. **数字不靠记忆。** 文献里的数字（码参数、错误率、比特数）必须附 arXiv 编号；查不到就标“未核实”。
7. **关卡处停下。** 到达 Gate 时写报告、停止推进，等人批准。不要越过关卡。
8. **预算有上限。** 单次运行的 LLM token 和 CPU 时间不得超过 `experiments/<id>.yaml` 里声明的预算。

## 每个会话的固定流程

**开始时：**
1. 读 `research/STATE.md`（当前阶段、关卡、下一步、待人决策）。
2. 读 `research/decisions.md` 最新几条（人的最新指示优先于 STATE 里的计划）。
3. 如果有“待人决策”尚未答复，只做不依赖该决策的工作。

**结束前（或上下文快满时）：**
1. 更新 `research/STATE.md`：做了什么、结果在哪、下一步是什么。
2. 新实验必须有对应的 `research/journal/` 条目。
3. `git add` + `git commit`，提交信息写清楚做了什么。不要 push。

## 研究循环

用 `research-cycle` skill 推进一轮：
选假设 → 写实验配置 → 跑实验 → 记日志 → 更新假设状态 → 更新 STATE。
单个实验的执行细节见 `run-experiment` skill。

## 子 agent 分工

| agent | 职责 | 什么时候用 |
|---|---|---|
| `lit-scout` | 查 arXiv、核对数字、判断新颖性 | 开新方向前；引用数字前；声称新结果前 |
| `experimenter` | 按配置实现并运行单个实验 | 可并行的独立实验 |
| `auditor` | 红队：独立复现并试图推翻结论 | 任何声称改进的结果；冻结评估器前 |

可并行的独立实验同时派发多个 `experimenter`。`auditor` 必须是新开的 agent，不能是做实验的同一个。

## 关卡（Gate）

| 关卡 | 进入条件 | 人要决定什么 |
|---|---|---|
| G0 | baseline 复现，数字与文献吻合 | baseline 是否可信 |
| G1 | 评估器完成 + auditor 攻击测试通过 | 冻结评估器（人执行 `scripts/freeze_evaluator.py freeze`） |
| G2 | 第一个经 auditor 确认的改进 | 是否值得深挖 / 换方向 |
| G3 | 结果稳健（多噪声模型、多 p 值、独立复现） | 是否写论文 / 公开 |

到达关卡时用 `gate-review` skill 写报告。

## 文件约定

```
research/
  STATE.md              # 当前状态，唯一的“现在在哪”
  decisions.md          # 人的决定（只有人写，agent 只读）
  hypotheses.md         # 假设台账
  leaderboard.jsonl     # 只能由评估器脚本追加
  evaluator_issues.md   # 评估器疑似问题
  journal/              # 每个实验一篇：YYYY-MM-DD-<exp-id>.md
  literature/           # lit-scout 的文献笔记
  audits/               # auditor 的复核报告
  gates/                # 关卡报告
experiments/<exp-id>.yaml   # 实验配置（含预算、种子、命令）
results/<exp-id>/           # 原始输出（不进 git）
```

## 环境

- `uv run python ...` 运行一切；不要用系统 python，不要 pip install（加依赖改 `pyproject.toml` 再 `uv sync`）。
- `uv run python scripts/check_env.py` 环境自检。
- `stim` 做模拟，`sinter` 做多核采样，表面码用 `pymatching` 解码，qLDPC 用 BP-OSD（`stimbposd`）。
- LLM 内循环用 `anthropic` SDK，key 在 `.env`（你不能读 `.env`，代码里用 `os.environ`）。
- 本机：Apple Silicon 10 核 / 24GB。`sinter` 的 `num_workers` 不超过 8，给系统留余量。

## 代码风格

- 评估、搜索、baseline 三者严格分离：搜索代码不得 import 评估器内部函数来“提前看分数”，
  只能通过评估器的公开入口提交候选。
- 每个实验可由一条命令完整复现（写在 yaml 里）。
- 随机种子由配置控制并记录。
