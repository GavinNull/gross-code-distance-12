# 研究状态

> 由 lead agent 在每个会话结束前更新。这是“现在在哪”的唯一来源。

**最后更新**：2026-10-02（项目初始化，未开始研究）
**当前阶段**：P0 复现 baseline（未开始）
**下一个关卡**：G0

## 待人决策

（无）

## 已确认结果

（无。只有经 auditor 复核通过的结果才能写在这里。）

## 正在进行

（无）

## 下一步（按优先级）

1. `lit-scout`：核对 `docs/课题说明.md` §9 的参考文献，补全 arXiv 编号；
   检索 2025 年以来 “syndrome extraction schedule / qLDPC / bivariate bicycle / AlphaEvolve QEC” 相关工作，
   写进 `research/literature/`，重点回答：调度搜索这个方向是否已被人做过、做到什么程度。
2. 复现表面码 baseline：rotated surface code d=3,5,7，均匀去极化，p 扫 1e-3 ~ 5e-3，
   结果与 Stim/PyMatching 文献中的阈值行为吻合。
3. 复现 gross code [[144,12,12]] 的标准 syndrome 提取电路（IBM 深度-8 调度），
   用 BP-OSD 估逻辑错误率，与原论文数字对比。
4. 2 和 3 完成后写 G0 关卡报告。

## 已知风险 / 备注

- 文献数字目前均为记忆整理，未核实。
