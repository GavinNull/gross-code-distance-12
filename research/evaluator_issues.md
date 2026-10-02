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
  状态：fixed-pending-audit
  **修复说明（2026-10-02，评估器修补 agent）**：
  - `evaluators/l0.py` 的 `stabilizer_coverage` / `detector_coverage` 默认改为 flow 方法（新参数 `L0Constraints.coverage_method="flows"`；
    旧的切段方法保留为 `"segments"`，只作对照；已有参数含义不变）。去掉数据制备与最终读出后，对整条电路求一次 `flow_generators()`，
    GF(2) 消元得到确定奇偶空间 D 和每个生成元 s 的测量陪集 A_s = M_s + D（flow `s_in -> 1`）。s 的测量次数 = 时间上不重叠、各含 A_s
    一个元素的层区间的最大个数，用 D 的最小跨度基（MSGM）+ 区间调度精确求解；区间之前的门全部计入，所以不需要干净切口。
    detector 覆盖用每个区间的代表元构造首轮 / 相邻轮 / 末轮与读出的比较，允许模掉“完全落在 s 的单个区间内”的确定奇偶（meta-check 等），
    并证明这不会让检查变空。细节见 `evaluators/README.md` §3.2。
  - 结果：Strikis 电路（`baselines/strikis.py`，3 轮、12 轮，两个基底）通过 L0（不含距离检查）；IBM 电路照样通过；有干净切口的电路上
    新旧方法计数相同。已有的全部 L0 攻击测试仍被拒绝。
  - 新增攻击测试（全部被拒）：流水电路第 0 轮某 Z 检查少一个 CNOT（全部确定、逻辑注入通过）→ stabilizer_coverage；排空阶段最后一轮
    X 辅助比特不测（Z / X memory）→ stabilizer_coverage；灌入阶段 detector 缺失 → detector_coverage；流水电路跳过一个稳定子 / 少一轮 /
    多一轮 / 删末轮 detector；Strikis gross 电路删掉第 0 轮全部 Z detector → detector_coverage。测试用流水电路生成器
    `tests/memory_builder.py:build_pipelined_memory`。
  - **请 auditor 复核的语义变化**：计数是“不重叠的测量窗口数”，一轮测两次、另一轮不测会被接受（旧方法按段计会拒绝；这不减少噪声）；
    冗余关系下可以省略一个 detector（等价于不声明 meta-check，与旧方法相同；gross 上单删 1 个第 0 轮 Z detector 会被接受）；
    测量后不复位直接复用辅助比特仍被误拒（3 轮数成 2 次）。

- 2026-10-02 · auditor（E-003 复核）· **L2 的 `boundary="paper"` 对流水电路不能消除边界差异** ·
  对辅助比特跨轮流水的电路（Strikis），`paper` 口径只去掉数据比特的制备/读出噪声，灌入/排空层里数据比特的空闲噪声仍在。
  流水与非流水电路相比，边界故障质量相差约 3%；在 pL 对 p 斜率约 8 的区间，这会被放大成约 1.25 倍的假差异。
  影响范围：H-003 包络线的对照（IBM 非流水 vs Strikis 流水），以及联合搜索中允许流水的调度。
  建议：比较时使用“两种轮数之差”（例如 24 轮减 12 轮）估计体内每轮错误率，或实现对所有电路一致的“拉平边界”口径。
  状态：fixed-pending-audit
  **修复说明（2026-10-02，评估器修补 agent）**：
  - `evaluators/l2.py` 新增两种口径（`paper` 默认不变，只新增参数）：
    `boundary="diff"`（推荐）：`sample_l2(..., rounds=r2, boundary="diff", diff_rounds=r1, diff_inner_boundary="paper")` 做两次独立采样，
    按 `1 - cP(r) = B(1 - c·eps)^r`（c = 2^K/(2^K-1)，K = 失败事件涉及的 observable 数）相减消去边界因子 B，得到体内每轮错误率 eps；
    K=1 时就是 `(log(1-2P(r2)) - log(1-2P(r1)))/(r2-r1) = log(1-2eps)`，k>1 时 c≈1，退化为存活率之比。区间为对 B 取剖面似然的
    LR 区间（默认 LR=1000），与 delta 法吻合，模拟覆盖率正确。公开函数 `diff_per_round`。推导见 README §7.2.1。
    `boundary="flat"`：auditor 的拉平口径（paper + 去掉数据比特第一个 / 最后一个双比特门之外的单比特噪声）；gross 上与 auditor 的
    trim 逐项一致（去掉 720 / 288 个位置，Z 基底 Σ先验 58.28 / 57.85）。
  - 表面码 d=3（sd6，p=0.005，每 sector ≥2000 次失败）：diff(3,9)、diff(9,27)、diff(6,30) 的体内每轮 P_Z = 0.0185 / 0.0180 / 0.0176，
    与 paper 口径 27、54 轮单次运行的每轮值（1−2P 形式）0.0178 / 0.0170 在误差内一致；paper 9 轮单次的值低约 15%（完美边界稀释）。
  - IBM vs Strikis（gross，p=0.005，sd6，解码器 A，diff 4/12 轮、inner=flat，每 sector ≥100 次失败，3 workers）：
    Strikis/IBM 体内每轮比值 P_any 0.84 [bootstrap 95%: 0.64, 1.10]，Z 0.84 [0.58, 1.21]，X 0.79 [0.54, 1.11]；同一批的 flat 12 轮
    单次比值 P_any 0.98 [0.80, 1.20]（X+Z 独立近似 0.95）。与 auditor 拉平结果 1.12 [0.87, 1.45] 区间重叠，都与 1 无显著差异；
    4 轮时 Strikis 失败率是 IBM 的约 1.8 倍、12 轮时几乎相同，说明额外失败主要来自边界。统计量小（±30%），只作口径验证，不上榜。
    结果在 `results/evaluator-fix-diff/`。
  - `evaluators/leaderboard.py`：条目新增 `boundary_detail`（口径、分数定义；diff 另记两个轮数与子采样口径）。
  - 已知局限：diff 假设边界与轮数无关、每轮独立，r1 太小时不成立；差分放大误差；diff 的分数与单次运行的每轮值不是同一个量，不能混排。

- 2026-10-02 · auditor（G1 前全面攻击，报告 `research/audits/2026-10-02-evaluator-G1.md`，结论 **NOT READY**）· 新发现，均为 open：
  1. **严重 A1/A1b 伪轮次**：1 轮真提取 + 反复重测辅助比特即可通过全部 L0（含 d_circ = d），分数虚高 4.5–70 倍。lead 已在 d=3 上复现（伪电路 10 tick、诚实电路 21 tick，都判“测了 3 次”）。
     README 中“同一轮测两次、另一轮不测无害”的说法是错的。
  2. **严重 LB1–LB7 成绩单**：`rounds` 不与电路核对；`submit` 接受伪造的 L0/L2 字典、非打分噪声模型、与采样电路不符的 schedule_hash；删末行或重算哈希链不被发现；不同 p / 解码器 / 码混在同一张榜。
  3. **高 N1/N2 SI1000**：`I` 门可躲开 ResonatorIdle 噪声（错误率减半）；L0/L2 对 CZ+H 电路误拒。
  4. **高 L2-2 diff**：短轮数电路由候选提供且不过 L0，可操纵差分得到虚低甚至负值；区间倒置。
  5. **中 L2-1 paper 边界**：在首个 CNOT 前插 `I` 可把复位后的空闲噪声算成“制备”而被移除（约 6%）。
  6. **中 L0-2 冗余校验行**：冗余行可以每轮不测而仍被视为测过（需 PI 决定规则）。
  7. **中 L2-4**：小样本下换种子挑结果（最好/最差 0.69），成绩单只给警告。
  8. **高 F1–F6 冻结机制**：hook 大小写敏感；Bash 写绕过 hook；伪造 `.pyc` / 同名 `.so` 不被哈希发现；冻结脚本自身、`uv.lock`、库版本不在哈希范围内。
  状态：fixed-pending-audit（评估器 v2，分支 worktree-agent-ad3344517947afa89，未合并，未冻结）
  **修复说明（2026-10-02，评估器 v2 agent）**——总体设计：候选**只提交调度 JSON，不提交电路**（`evaluators/candidate.py`），
  评估器用固定模板生成电路；唯一入口 `evaluators/pipeline.py:evaluate(task_id, code_spec, schedule, *, seed)`；任务注册表
  `evaluators/tasks.py`；只有 pipeline 能写成绩单。L0 保留为第二道防线。逐项：
  1. **A1/A1b 伪轮次** → 修复 + 结构性排除。模板电路每个校验每轮恰好一次“复位 → 全部 CNOT → 测量”，数据读出单独在最后一层，
     候选无法写出重测。L0 `stabilizer_coverage` 新增重提取判据（README §3.2.1）：相邻窗口代表元之差的 detecting region 在
     [窗口 j−1 结束, 窗口 j 结束) 内某时刻限制到数据比特上恰为 s（不成立时模掉窗口内确定奇偶再判）；`data_layout` 拒绝最终数据
     读出之后的任何测量。回归 `tests/test_g1_attacks.py::test_A1_fake_rounds_rejected[3-3 / 5-10]`、`test_A1b_*`（含
     min_circuit_distance=d 的配置），诚实电路（表面码、Steane、[[4,2,2]] 流水、冗余行、gross IBM / Strikis 3 / 12 轮）仍通过。
     README 中“一轮测两次另一轮不测无害”的错误说法已改正。
  2. **LB1–LB7 成绩单** → 修复 + 结构性排除。`leaderboard.submit` / `build_entry` 删除（调用报 PermissionError），私有 `_append`
     只认 pipeline 的凭证对象，记录由 pipeline 组装；记录带 task_id / task_hash、规范化调度及评估器算的 schedule_hash、每个轮数的
     电路哈希、L0 实测轮数（rounds_verified）；`entry_problems` 在写入前与 `verify_leaderboard` 时核对任务一致性（噪声、p、轮数、
     边界、解码器、停止规则、码哈希）、从调度重新生成电路核对哈希、L2 采样电路 = 评估器电路、分数可由计数重算、每 sector ≥1000
     次失败。LB5/LB6：链本身仍挡不住，新增 git 外部锚点（`anchor_line()` 写进 commit message，`verify_leaderboard()` 自动读取
     git 历史中的锚点核对）。LB7：`table(task_id)` 按任务分榜。回归 `tests/test_leaderboard.py`（19 种伪造变体，即使持有凭证也被拒；
     删末行 / 整链重算在有锚点时被发现）、`tests/test_pipeline.py`（候选给 rounds / noise 字段被拒）。
     局限（已写 README §8/§11）：同进程恶意代码可伪造计数自洽的记录，需沙箱 + `reproduce_entry` 抽查。
  3. **N1/N2 SI1000** → N1 修复：有隐式空闲噪声且 I 门噪声 ≠ 空闲噪声的模型（si1000）里 `I` 按空闲处理（空闲 + ResonatorIdle），
     回归 `test_N1_identity_gate_no_longer_dodges_resonator_idle`。N2 未修 → si1000 **移出打分模型**（`SCORING_MODELS = ("sd6",)`），
     任务注册表只允许 sd6（`Task.validate`）。
  4. **L2-2 diff** → 修复 + 结构性排除。diff 的两个轮数的电路都由评估器从同一调度生成且都过 L0；`diff_per_round` 两端分别截断
     （不再倒置），新增 `valid` 标记，负估计在 pipeline 判 `rejected_l2`。回归 `test_diff_selftest_*`、`test_negative_diff_estimate_is_a_failure`、
     `tests/test_l2.py::test_diff_per_round_closed_form_and_interval`。
  5. **L2-1 paper 边界** → 修复：制备结束 = 首个双比特门之前最后一个复位所在层，复位后的 I / 单比特门 / 空闲照常带噪声；模板里也没有
     I 门。回归 `test_L2_1_identity_before_first_cnot_no_longer_removes_noise`（I 填充前后 Σ先验相等）。副作用：两个基底复位之后的
     单比特门必须相同（R+H 对 R+I 的组合现在被拒，test_l2 已相应修改）。
  6. **L0-2 冗余行** → 结构性排除（待 PI 裁决）：模板要求每一行（含冗余行）每轮都测，少列一行即拒；任务字段
     `allow_redundant_row_omission` 在裁决前不能为 True。原始电路上的 L0 仍接受“冗余行不测”，写进 README §5 局限。
  7. **L2-4 选择性报告 / 小样本** → 修复：任务停止规则要求每 sector ≥1000 次失败，预算耗尽仍不足 → `insufficient_statistics`，
     不上榜；同一调度重复提交记 attempt，排名只用第一次。局限：对调度做无关改动可“重抽”（±3–6%），写进 README §11。
  8. **F1–F6 冻结机制** → 修复（F2 只能缓解）。哈希覆盖 evaluators/ 全部文件 + 冻结脚本 + hook + pyproject.toml + uv.lock + 评估器测试；
     清单外文件、.so/.pyd/.dylib、符号链接即篡改；__pycache__/*.pyc 必须与对应源文件重新编译的代码对象逐项相等（F3）；冻结记录另写
     `research/evaluator_freeze.{sha256,json}`（shasum -c 可独立校验）；hook 解析符号链接、大小写不敏感、拒绝硬链接（F1）；关键库
     `==` 固定并与 `tasks.PINNED_VERSIONS` 一致，pipeline 写榜前核对（F6）；正式成绩单只接受已冻结且完整的评估器。F2（Bash 绕过 hook）
     未改 settings.json，冻结后靠 PI 用 chmod / chflags 锁目录（README §10 列出命令，未执行）。回归 `tests/test_freeze.py`。
  - 另：模板电路与 baselines 逐机制一致（IBM、Strikis，1 / 3 轮，两个基底，`tests/test_candidate.py`）；示例任务 `gross-sd6-p4e-3`
    的漏斗层级与预算为空，等 E-004；距离门槛 10 暂定。需要 auditor 再审。
