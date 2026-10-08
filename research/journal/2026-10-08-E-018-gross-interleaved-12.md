# E-018 · gross 码交错电路能否 d_circ = 12（阶段 a 汇总 + 阶段 b 精确 lift 检验 + 阶段 c 交错设计）

- 日期：2026-10-08 / 执行者：experimenter（阶段 a 的 DFS 由 lead 跑）/ 代码基线：git 16bef12 / 评估器未冻结，只读使用其公开入口（`build_circuits`、`add_noise`、`pipeline.screen`）
- 假设：H-004；配置：`experiments/E-018-gross-interleaved-12.yaml`
- 事先预测（yaml，未改）：1) 每侧权重 11 扩展码逻辑 10^4–10^6；2) ≤10^5 时 lift 证明本机可行；3) 约三成概率存在保持 Fig. 12 各校验顺序、只改时序的交错电路，评估器上界达到 12。
- 代码：`search/experiments/e018/`；原始结果：`results/E-018-gross-interleaved-12/`
- 预算：24 CPU h，≤6 进程。

## 进行中（阶段记录，按时间）

- [开工] 读了 CLAUDE.md、experimenter.md、STATE、`gross_ext.py`、`ibm_lift.py`、audit 2026-10-05 B7（lift 论证与任意 R 推广）。lead 的三个补跑（full_X_c0_s0/s1、full_Z_c0_s3）仍在运行。
