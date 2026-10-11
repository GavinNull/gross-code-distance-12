# E-024b · gross 码 d_circ = 12 压周期：Fig. 12 以外的 d_ext = 11 扩展码类

- 日期：2026-10-11 / 执行者：experimenter / 代码基线：git aff00f4 / 评估器只读使用公开入口
- 假设：H-004；配置：`experiments/E-024b-gross12-other-classes.yaml`（预测跑前提交 25a027c）
- 代码：`search/experiments/e024b/`；原始结果：`results/E-024b-gross12-other-classes/`
- 预算：40 CPU h，≤4 进程（E-024a 用另外 4 核）。

## 进行中（按时间）

- [开工] 读了 CLAUDE.md、experimenter.md、STATE（已确认 1、3、7、9、10）、E-021 日志与审计。要点：
  扩展码只取决于每校验 (P1, T, P3)；5/10 三元组类允许；均匀顺序 90/90 d_ext ≤ 10；Fig. 12 类颜色对称 P = 8 944/944 失败、流水 P = 10 体内 UNSAT；
  最短认证周期 21。dfs128 速度约 3.75e7 节点/核·秒（E-014 X 侧 2.0e10 节点 540 核·秒），所以 |H| = 24 的类 W=10 证明约 10 核·分钟，W=11 完整枚举约 1.6 核·小时/侧。
