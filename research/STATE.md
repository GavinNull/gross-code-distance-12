# 研究状态

> 由 lead agent 在每个会话结束前更新。这是“现在在哪”的唯一来源。

**最后更新**：2026-10-02
**当前阶段**：P1 完善评估器 + 联合设计准备（G0 已批准，方向：码 + 电路联合设计）
**下一个关卡**：G1（冻结评估器）

## 待人决策

1. （未答复）是否在 `.claude/agents/experimenter.md` 加一条：禁止按模式批量杀进程。目前在每个 agent 的任务说明里单独禁止。
2. （未答复）SI1000 ResonatorIdle 的处理：lead 选择“不作用于正在做门的比特”，PI 未表态，暂按此执行。

## 已确认结果

（无。只有经 auditor 复核通过的结果才能写在这里。）

## 正在进行（P1，2026-10-02 派发）

- 评估器·距离模块：修复 L0 距离漏报，并入 BP-OSD 见证搜索；测试下界证明（ILP/SAT）的可行性 → `evaluators/distance.py`
- 评估器·L2 + 成绩单：X/Z 联合采样、paper/noisy 两种边界口径、leaderboard 写入 → `evaluators/l2.py`、`evaluators/leaderboard.py`
- E-003：复现 Strikis d_circ=11 电路，作为“最好已知电路”对照 → `experiments/E-003-strikis-gross.yaml`
- lit-scout：联合设计竞争格局与资源指标，为 H-003 指标定稿 → `research/literature/codesign-landscape.md`、`resource-metrics.md`
- 码族枚举与筛选工具（BB/2BGA，含 IBM 表 3 复现与小规模试运行）→ `search/codes/`

## P0 已完成（摘要）
- E-001/E-001b 表面码、E-002 gross code baseline，均经 auditor 有条件确认；G0 报告：`research/gates/G0-2026-10-02.md`
- 评估器第一部分（噪声 + 双基底 L0 + 28 个攻击测试）；LLM 进化框架（35 测试，mock）
- 文献：参考文献核对、gross code 细节、新颖性（H-001 已被先发表）、噪声模型、qLDPC 码目录、交错电路

## 下一步（按优先级）

1. 收齐上述 5 项，提交并让 auditor 复核距离模块和 L2。
2. 根据 lit-scout 结果定稿 H-003 的指标（建议同时报告“每逻辑比特物理比特数”和“每逻辑比特每轮错误率”）。
3. auditor 对完整评估器做攻击测试 → G1 关卡报告 → PI 冻结评估器。
4. G1 之后：联合搜索。先用模拟退火 / 穷举做对照，再上 LLM 进化（需要 PI 配置 API key 并批准预算）。

## 已知风险 / 备注

- ~~待办：判定 IBM 原调度是否交错~~ 已完成：**是交错的**（见方向建议书风险第 4 条），方案 1 先验下调。
- 流程事故：E-002 experimenter 执行过 `pkill -f "multiprocessing.spawn"`，可能误杀其他 agent 的进程。经检查无实际损失。
  建议 PI 在 `.claude/agents/experimenter.md` 加一条：禁止用模式匹配批量杀进程，只能杀自己启动的 PID。

- 文献数字目前均为记忆整理，未核实。
- E-001 教训：噪声模型口径决定阈值数字。gross code 对比必须使用与 IBM 论文相同的噪声定义，并在评估器中钉死。
