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
  状态：fixed-pending-audit
  **修复说明（2026-10-02，评估器距离模块负责 agent）**：
  - 新增 `evaluators/distance.py`。`upper_bound(noisy_circuit, seed=...)` 依次跑 `shortest_graphlike_error`、`search_for_undetectable_logical_errors`、
    BP-OSD 随机 η 搜索（Eq. 12，默认 1500 次，osd_cs order 2），再对低权重 BP-OSD 解做 CP-SAT 邻域精修（LNS，96 个起点，确定性时间上限），
    取最短见证。每个见证都先注入验证（去噪声、原位置插入概率 1 的 Pauli 通道/测量翻转、采样确认 0 个 detector 触发且翻转 observable），
    验证不过的不计入。随机性只来自显式 seed，结果与进程数无关。实现搬进 evaluators，不 import baselines。
  - `evaluators/l0.py` 的 `circuit_distance` 改为调用 `distance.upper_bound`（子进程，硬超时默认 1800 s），诊断列出最短见证的全部故障
    （tick、噪声指令、比特、Pauli）、方法与注入验证结果。新参数 `distance_seed`、`distance_bposd_trials`、`distance_lns_starts`、
    `distance_lns_det_time`、`distance_num_workers`、`distance_early_stop`。
  - gross code（IBM depth-8，3 轮，sd6）：X 基底 seed 0–8 全部找到权重 10（3 进程 81–127 s），Z 基底 seed 0–2 全部 10（E-002 的 Z 基底只到 11）。
    旧路径（stim 截断搜索）仍是 12。E-002 文件里的见证也被本模块的注入验证独立确认。
  - 回归测试：`tests/test_distance.py::test_gross_code_X_3_rounds_upper_bound_at_most_10`、`::test_gross_code_l0_gate_rejects_threshold_11`（slow）。
  - **未解决**：这仍然只是上界。精确下界（CP-SAT/MaxSAT/HiGHS）只在小电路上可行（表面码 d≤5、BB72 1 轮）；gross 3 轮 10 分钟只证到 d_circ ≥ 5，
    所以不能声称 d_circ = 10，只能说 ≤ 10。详见 `evaluators/README.md` §3.1。L0 距离检查在 gross 上单进程约 4–6 分钟/基底。
  - 需要 auditor 复核：攻击思路包括构造 BP-OSD+LNS 漏掉的短逻辑错误、伪造见证骗过注入验证、种子/进程数是否影响判定。

- 2026-10-02 · experimenter（E-003）· **L0 误拒跨轮流水的合法电路，导致“最好已知电路”无法打分** ·
  Strikis 的 gross code 电路（arXiv 2603.05481 Fig. 12）辅助比特 CNOT 窗口跨越周期边界，电路中没有“干净切口”，
  `stabilizer_coverage` 只能切出一段，于是判每个生成元只测了 1 次而拒绝。其余检查（determinism、observables、logical_injection 等）双基底都通过。
  最小复现：`baselines/strikis.py` 生成的 3 轮无噪声电路 → `check_l0(..., basis="both")`。
  影响范围：H-003 的对照包络线需要这个电路，不修就无法在评估器下比较；联合搜索如果允许流水调度，同样会被误拒。
  这是 `evaluators/README.md` 已知局限中写明的一类。G1 冻结前必须扩展（例如用 stim flows 对整条电路做覆盖检查，不依赖切段）。
  状态：open

- 2026-10-02 · auditor（E-003 复核）· **L2 的 `boundary="paper"` 对流水电路不能消除边界差异** ·
  对辅助比特跨轮流水的电路（Strikis），`paper` 口径只去掉数据比特的制备/读出噪声，灌入/排空层里数据比特的空闲噪声仍在。
  流水与非流水电路相比，边界故障质量相差约 3%；在 pL 对 p 斜率约 8 的区间，这会被放大成约 1.25 倍的假差异。
  影响范围：H-003 包络线的对照（IBM 非流水 vs Strikis 流水），以及联合搜索中允许流水的调度。
  建议：比较时使用“两种轮数之差”（例如 24 轮减 12 轮）估计体内每轮错误率，或实现对所有电路一致的“拉平边界”口径。
  状态：open
