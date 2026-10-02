# 评估器疑似问题

> 评估器冻结后，agent 发现的任何疑似 bug 都写在这里，由人裁决。
> 格式：日期 · 发现者 · 现象 · 最小复现命令 · 影响范围 · 状态（open / fixed / not-a-bug）

---

（暂无）

- 2026-10-02 · auditor（E-002 复核）· **L0 电路距离检查在 gross code 上严重高估** ·
  `check_l0` 默认的距离检查（`search_for_undetectable_logical_errors` 截断搜索与 `shortest_graphlike_error` 取较小者）对 IBM gross code 电路报出 d_circ = 12，
  但 E-002 已找到并经 auditor 独立注入验证了一个权重 10 的不可检测逻辑错误（`results/E-002-gross-baseline/circuit_distance_witness_X_r3.json`）。
  最小复现：对 E-002 的 X 基底 3 轮电路运行 `check_l0`，并与上述见证对比。
  影响范围：**L0 的 `min_circuit_distance` 下限检查会放行距离不达标的候选**，这是评估器最重要的一道闸，评估器冻结前必须修复。
  建议：把 E-002 的 BP-OSD 随机 η 见证搜索（arXiv 2308.07915 Eq. 12）并入 L0 作为第二条上界路径，取所有方法的最小值；所有声称的距离仍需 SAT/ILP 下界证明。
  状态：open

- 2026-10-02 · experimenter（E-003）· **L0 误拒跨轮流水的合法电路，导致“最好已知电路”无法打分** ·
  Strikis 的 gross code 电路（arXiv 2603.05481 Fig. 12）辅助比特 CNOT 窗口跨越周期边界，电路中没有“干净切口”，
  `stabilizer_coverage` 只能切出一段，于是判每个生成元只测了 1 次而拒绝。其余检查（determinism、observables、logical_injection 等）双基底都通过。
  最小复现：`baselines/strikis.py` 生成的 3 轮无噪声电路 → `check_l0(..., basis="both")`。
  影响范围：H-003 的对照包络线需要这个电路，不修就无法在评估器下比较；联合搜索如果允许流水调度，同样会被误拒。
  这是 `evaluators/README.md` 已知局限中写明的一类。G1 冻结前必须扩展（例如用 stim flows 对整条电路做覆盖检查，不依赖切段）。
  状态：open
