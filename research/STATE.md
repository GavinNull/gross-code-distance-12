# 研究状态

> 由 lead agent 在每个会话结束前更新。这是“现在在哪”的唯一来源。

**最后更新**：2026-10-02
**当前阶段**：P0 复现 baseline（进行中）
**下一个关卡**：G0

## 待人决策

1. **研究方向调整** → 建议书：`research/proposals/2026-10-02-方向调整.md`
   建议：攻 2603.05481 原文列出的开放问题“交错电路能否让 gross code 达到 d_circ=12”；
   第一步先做公平基准 + 精确电路距离验证（含独立验证 Strikis 的 d_circ=11 猜想），H-002 作为方法论贡献。

## 已确认结果

（无。只有经 auditor 复核通过的结果才能写在这里。）

## 正在进行

- lit-scout：核对参考文献、提取 gross code 论文细节、调度搜索新颖性调研 → `research/literature/`
- E-002 gross code baseline（experimenter）→ `experiments/E-002-gross-baseline.yaml`
- auditor：独立复现 E-001/E-001b → `research/audits/2026-10-02-E-001.md`
- 评估器构建（P1 提前开工，未冻结）：噪声模型 + L0 合法性检查 + 攻击测试 → `evaluators/`、`tests/`
- LLM 进化搜索框架（mock LLM + 玩具问题，不花 token）→ `search/llm_evolve/`
- ~~lit-scout #3~~ 已完成：交错电路达到 d_circ=12 属于空白（证据中等），开放问题已在原文核实
- lit-scout #2：噪声模型精确定义、E-001 阈值文献核对、qLDPC 码目录 → `research/literature/`
- ~~E-001 表面码 baseline~~ 已完成 → `research/journal/2026-10-02-E-001-surface-baseline.md`：流水线可用，阈值约 1.2%；初始预测因噪声口径错误未命中

## 下一步（按优先级）

1. ~~lit-scout #1：参考文献核对 + 新颖性调研~~ 已完成 → `research/literature/` 三份笔记。关键结论：H-001 已被先发表。
2. 复现表面码 baseline：rotated surface code d=3,5,7，均匀去极化，p 扫 1e-3 ~ 5e-3，
   结果与 Stim/PyMatching 文献中的阈值行为吻合。
3. 复现 gross code [[144,12,12]] 的标准 syndrome 提取电路（IBM 深度-8 调度），
   用 BP-OSD 估逻辑错误率，与原论文数字对比。
4. 2 和 3 完成后写 G0 关卡报告。

## 已知风险 / 备注

- 待办：E-002 完成后，写脚本判定 IBM 原调度是否交错（影响方向建议）。

- 文献数字目前均为记忆整理，未核实。
- E-001 教训：噪声模型口径决定阈值数字。gross code 对比必须使用与 IBM 论文相同的噪声定义，并在评估器中钉死。
