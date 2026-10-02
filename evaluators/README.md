# evaluators/：评估器第一部分（噪声模型 + L0 合法性检查）

状态：未冻结（P1 进行中）。冻结前需 auditor 攻击测试（G1）。
测试：`uv run pytest tests/test_l0.py tests/test_noise.py tests/test_codes.py tests/test_stats.py -q`（约 1 分钟，单核；距离检查改用 `distance.upper_bound` 后变慢，测试里用轻量预算 `FAST_DIST`）。
距离：`uv run pytest tests/test_distance.py -q -m "not slow"`（约 20 秒）；gross code 回归 `-m slow`（2 个测试，各约 2 分钟，3 进程）。

| 文件 | 内容 |
|---|---|
| `codes.py` | `CSSCode`（HX/HZ/LX/LZ，GF(2)）、自检、`code_dimension`、`compute_logicals`、GF(2) 工具、测试用 `rotated_surface_code_from_stim` |
| `noise.py` | `add_noise(circuit, model, p, ...)`，命名噪声模型 |
| `l0.py` | `check_l0(circuit, code, basis, constraints) -> L0Report` |
| `distance.py` | 电路级距离：`upper_bound(...) -> DistanceResult`（多方法取经注入验证的最短见证）、`lower_bound(...)`（CP-SAT / MaxSAT / HiGHS 精确法）、`verify_faults`，见 §3.1 |
| `stats.py` | 置信区间与统计口径约定（似然比因子 ↔ σ） |
| `l2.py` | `sample_l2(...) -> L2Result`：X/Z 联合采样的逻辑错误率（sinter 多进程、显式种子、可逐位复现），见 §7 |
| `leaderboard.py` | `build_entry` / `submit` / `verify_leaderboard`：`research/leaderboard.jsonl` 的唯一写入口（只追加、文件锁、哈希链），见 §8 |

---

## 1. 接口

```python
from evaluators.codes import CSSCode
from evaluators.noise import add_noise, SCORING_MODELS, DEFAULT_MODEL
from evaluators.l0 import check_l0, L0Constraints

code = CSSCode.from_checks(HX, HZ)          # 或 CSSCode(HX, HZ, LX, LZ)，构造时自检，不合法抛 ValueError
cons = L0Constraints(
    data_qubits=[...],          # 码第 j 列 -> 电路比特编号（由任务给定，不由候选给定）
    max_qubits=288, allowed_edges={(a, b), ...},   # None = 不限
    allowed_gates={"R","RX","M","MX","MR","MRX","H","CX","CZ","I"},   # 默认值
    rounds=12,                  # 每个稳定子生成元必须恰好被测 rounds 次
    min_circuit_distance=12,    # None = 不查距离
)
report = check_l0({"Z": circ_z, "X": circ_x}, code, "both", cons)   # 默认口径：两个基底
report.passed, report.d_circ          # d_circ = 两个基底电路级距离上界的较小值
print(report.to_text())               # 逐项 [PASS]/[FAIL]/[SKIPPED] 诊断，可直接喂给 LLM
report.per_basis["X"].get("circuit_distance").details
```

- 候选电路必须**无噪声**、用 TICK 分时间步。它是一个 memory 实验：数据比特显式复位 → 若干轮 syndrome 提取 → 数据比特在 basis 基下测量；observable 由最后的数据读出构成。
- `basis` 可为 `"Z"`、`"X"`、`"both"`。评估器打分一律用 `"both"`，两个基底都通过才算通过，距离取较差者（auditor E-001 H2）。
- `CSSCode` 支持冗余校验行（BB 码 HX 72 行秩 66）和 k>1。`compute_logicals` 给出配对好的 LX、LZ（LX·LZᵀ = I）。
- 搜索代码只应调用 `check_l0` / `add_noise` 这两个公开入口。

## 2. 噪声模型（`noise.py`）

`add_noise(circuit, model, p, *, idle=None, si1000_resonator_on_gate_qubits=False)`。
出处与系数核对见 `research/literature/noise-models.md`（lit-scout 读全文核对，2026-10-02）。

| 模型 | 用途 | 单比特门 | 双比特门 | 复位后翻转 | 测量 | 空闲 |
|---|---|---|---|---|---|---|
| `sd6`（**默认**） | 打分 | DEP1(p) | DEP2(p) | p | 测量前翻转 p | 每层未被操作的比特 DEP1(p) |
| `si1000` | 打分 | DEP1(p/10) | 仅 CZ，DEP2(p) | 2p | 测量前翻转 5p | DEP1(p/10)；含测量/复位的层里，既没被测量也没被复位的空闲比特**再叠加** DEP1(2p)（ResonatorIdle） |
| `gross_sd6` | 只复现 IBM baseline | DEP1(p)（论文未定义，自定） | DEP2(p) | p | **记录**翻转 p（`M(p)`） | **只在显式 I 门上** DEP1(p) |
| `uniform_depolarizing` | 通用 | DEP1(p) | DEP2(p) | p | 测量前翻转 p | `idle=True`（默认，= sd6）或 `idle=False` |
| `legacy_no_idle` | 只与 E-001 对照 | 同上 | 同上 | p | 测量前翻转 p | 无 |

- `SCORING_MODELS = ("sd6", "si1000")`，`DEFAULT_MODEL = "sd6"`；两者都有逐层空闲噪声，**不可关闭**（`sd6`/`si1000` 传 `idle=False` 直接报错）。
- `gross_sd6` 不在打分模型里：它的空闲噪声只来自显式 I 门，候选只要不写 I 就能躲开空闲噪声。
- `legacy_no_idle`（= `uniform_depolarizing(idle=False)`）与 `stim.Circuit.generated(after_clifford_depolarization=p, before_measure_flip_probability=p, after_reset_flip_probability=p)` 的 DEM 逐机制完全相同（测试覆盖 d=3,5，X/Z）。E-001 的口径还多一项 `before_round_data_depolarization=p`（每轮开头只对数据比特），需要知道“轮”的边界，本模块不实现；测试验证了两者差别正是这一项（我们的每个机制概率 ≤ E-001，且有严格更小的）。
- 共同规则：输入里有任何噪声指令（含概率为 0 的通道、`M(0.01)`、`HERALDED_*`、`MPAD(p)`、藏在 REPEAT 里的）→ `NoisyCircuitError`；没有 TICK、同一层同一比特被作用两次 → `ValueError`；MPP、经典控制等 → `NotImplementedError`；输出展开 REPEAT。
- 隐式空闲噪声施加于电路中出现过的全部比特，不按生命期裁剪（首次复位前/最后测量后的噪声对 DEM 无影响）。

**SI1000 的歧义处理（noise-models.md “需要负责人确认的歧义”）**：
- (a) ResonatorIdle 是否作用于该层正在做门的比特：默认**不作用**（物理上谐振腔共享只影响空闲比特），`si1000_resonator_on_gate_qubits=True` 切换为字面解读。
- Idle 与 ResonatorIdle 按表 1 脚注“规则叠加”，空闲比特在测量/复位层得到 p/10 与 2p 两个独立 DEP1。
- 原生双比特门只有 CZ：CX 电路直接报错，SI1000 电路要用 CZ+H 搭（不能只改系数）。
- (b) SI1000 下表面码的时间步划分：本模块完全按输入电路的 TICK 来，划分由电路决定。

## 3. L0 检查项与方法（`l0.py`）

语法层四项总是运行；语法层有失败时语义层全部 `skipped`；前面全部通过才算距离。`passed` = 没有任何 `fail`。

| 检查 | 方法 |
|---|---|
| `instructions` | 先按 REPEAT 次数估算展开规模（防 `REPEAT 1e9`），再逐条检查：门在 `allowed_gates` 里；无噪声（`find_noise_instructions`）；门的目标只能是比特（拒绝 `rec`/`sweep` 经典控制）；`DETECTOR`/`OBSERVABLE_INCLUDE` 只能引用测量记录（拒绝 `OBSERVABLE_INCLUDE(0) Z1` 这种 Pauli 目标）。`MPP`、`MPAD`、`SQRT_Y` 等默认不允许。 |
| `qubit_count` | `circuit.num_qubits`（最大编号+1，含只出现在 `QUBIT_COORDS` 里的比特）≤ `max_qubits` |
| `connectivity` | 每个双比特门的无序比特对 ∈ `allowed_edges` |
| `tick_structure` | 必须有 TICK；同一层（两个 TICK 之间）每个比特至多被一个操作作用。防止把整轮塞进一个时间步来逃避空闲噪声与深度计量。 |
| `determinism` | 无噪声电路 `detector_error_model(allow_gauge_detectors=False)` 不报错（stim 用反向传播精确判定，不靠采样）；失败时再跑 `detecting_regions()` 取出“哪个 detector 与哪个复位/测量反对易”放进诊断。 |
| `data_layout` | 每个数据比特：第一个操作是复位（R/RX/MR/MRX），且在任何涉及数据比特的双比特门之前只有复位和单比特门；最后一个操作是 basis 基测量（Z：M/MR；X：MX/MRX），即“最终读出”。不允许依赖 stim 的隐式 \|0⟩ 初态。 |
| `observables` | 结构检查：observable 数量 = k（或 `num_observables`）、编号 0..k-1；每个 observable 非空，只含数据比特最终读出的记录；对应向量 v 满足 H_other·v = 0（是逻辑算符）、v ∉ rowspace(H_basis)（不是稳定子），所有 observable 模稳定子线性无关。诊断里给出 v 在 L_basis 基下的坐标（`v·L_dualᵀ`）。 |
| `logical_injection` | 用 `circuit.detecting_regions(ticks=[t])` 取出 t 时刻每个 detector / observable 的敏感区域（Pauli 串）。在两个时刻注入每个逻辑算符（Z memory 注入 LX_j，X memory 注入 LZ_j，作用在 `data_qubits` 上）：t_start = 第一个数据双比特门之前的 TICK，t_end = 最终读出之前的 TICK。要求：不与任何 detector 反对易（逻辑算符对 detector 不可见），且 observable × 逻辑算符的翻转矩阵满秩。t_start 的检查保证逻辑信息**从头到尾**被保存，能抓住“中途测量并重置数据比特”这种 detector、observable 都确定但信息已被摧毁的电路。 |
| `stabilizer_coverage` | 在“干净切口”处把电路切段：对每个非数据比特追踪状态 idle（未用/测量后）、prepped（复位后只有单比特门）、busy（复位后做过双比特门、尚未测量）；没有 busy 比特的 TICK 是干净切口（从第一个数据双比特门所在层开始，排除最终读出）。每段单独成一条电路，开头重放 prepped 比特的复位与单比特门（MR 重放成 R），再对每个稳定子生成元 s 调用 `solve_flow_measurements([P_s -> 1])`（P_s = s 在数据比特上的 Pauli）：有非空解 = 本段测量了 s（输入时刻的 s 值等于这些测量的奇偶）；解为空 = s 被本段的复位抹掉；无解 = 未测。要求每个生成元（含冗余行，含非 basis 型）被测次数 = `rounds`（未给则全部相等且 ≥1）。 |
| `detector_coverage` | 用上一步每段的测量集合 M_r(s) 构造“应有的比较”：basis 型 s 的首轮 M_1（数据在 basis 基制备，确定）、相邻轮 M_r ⊕ M_{r+1}、末轮与数据读出 M_last ⊕ readout(supp s)；`require_opposite_type_detectors=True` 时非 basis 型的相邻轮比较也要。用 GF(2) 增量基（Python int 位集）检查每个比较都在 detector 记录集合的张成里。因为 `solve_flow_measurements` 的解不唯一（可相差段内确定的测量组合，例如冗余稳定子行的 meta-check），先用每段的 `flow_generators()` 取出“输入输出都为恒等”的段内确定奇偶，一并放进张成里再判断（它们不要求被声明为 detector）。 |
| `circuit_distance` | 对 `add_noise(circuit, distance_noise_model)`（默认 sd6，含空闲噪声）先生成 DEM（确认加噪声后也不报错），再调用 `distance.upper_bound`（§3.1）：`shortest_graphlike_error`、`search_for_undetectable_logical_errors`（截断 4/4/False）、BP-OSD 随机 η 见证搜索 + CP-SAT 邻域精修，取**经注入验证**的最短逻辑错误的权重作为 d_circ **上界**；要求 ≥ `min_circuit_distance`。种子 `distance_seed`（默认 0），预算 `distance_bposd_trials`/`distance_lns_starts`/`distance_lns_det_time`，并行 `distance_num_workers`（结果与它无关）。`distance_early_stop=True`（默认）时一旦找到低于门槛的见证就停止（判定不变）。在子进程里运行，`distance_timeout_s`（默认 1800 s）到时杀掉进程并判为不通过。诊断列出最短见证的每个故障（tick、噪声指令、比特、Pauli）、找到它的方法和注入验证结果，例如 `tick 2: DEPOLARIZE2 on [160, 228] -> Z228`，可直接告诉 LLM 哪一步的 hook 错误降低了距离；没通过注入验证的见证不计入，并在诊断里给出警告。 |

在旋转表面码（stim 生成，d=3,5，X/Z）上全部通过且 d_circ = d；我也手动在 `baselines/` 的 gross code（IBM depth-8 调度，3 轮，X/Z，`detectors="basis"`/`"both"`）无噪声电路上跑过语法层 + 语义层（不含距离），全部通过，每次约 0.5 s（只读调用，没有改 baselines，也没有把它写进测试，因为那边的代码还在开发中）。

### 攻击测试（`tests/test_l0.py`，全部被拒绝且诊断可读）

| 攻击 | 拒绝它的检查 |
|---|---|
| 删掉 observable / observable 为空 | observables |
| observable = 一个 Z 稳定子（确定但平凡） | observables、logical_injection |
| 逻辑算符 ⊕ 一个确定的辅助比特测量 | observables |
| `OBSERVABLE_INCLUDE(0) Z1`（Pauli 目标，不是测量） | instructions |
| k=1 却给两个相同 observable / 声明 2 个但线性相关 | observables |
| 某轮跳过一个稳定子（detector 跨轮比较，仍全部确定） | stabilizer_coverage |
| Z memory 完全不测 X 型稳定子（退化成重复码） | stabilizer_coverage |
| 轮数少于要求 | stabilizer_coverage |
| 加一个不确定的 detector | determinism |
| 删掉末轮与数据读出比较的 detector | detector_coverage |
| 使用 MPP / SQRT_Y / MPAD | instructions |
| 经典反馈 `CX rec[-1] 1` | instructions |
| 越过耦合图（两次抵消的 CX） | connectivity |
| 比特数超限 | qubit_count |
| 电路自带噪声（stim 生成的带噪声电路、`M(p)`、`DEPOLARIZE1(0)`） | instructions |
| 去掉所有 TICK / 合并两层 | tick_structure |
| 中途测量并重置数据比特（摧毁逻辑信息，其余都确定） | logical_injection |
| 不显式复位数据比特 | data_layout |
| 用 Z 基读出却声称是 X memory | data_layout |
| 合法但调度差（距离 5 → 3） | circuit_distance |
| 单个基底合格、另一个基底距离降到 3（“牺牲一个基底”） | X:circuit_distance（basis="both"） |
| 距离计算超时 | circuit_distance |
| `REPEAT 1000000000 {TICK}` | instructions（不展开就拒绝） |

### 3.1 电路级距离（`distance.py`）

起因：旧版距离检查只取 `search_for_undetectable_logical_errors`（截断 4/4）与 `shortest_graphlike_error` 的较小值，对 IBM gross code 电路报 12，而 E-002 已有经验证的权重 10 见证（`research/evaluator_issues.md` 2026-10-02 条）。

```python
from evaluators.distance import upper_bound, lower_bound, verify_faults
r = upper_bound(noisy_circuit, seed=0, num_workers=1)   # -> DistanceResult
r.weight, r.witness.describe(), r.summary(), r.methods   # 最短见证、每种方法的结果与耗时
lb = lower_bound(noisy_circuit, method="cpsat", time_limit_s=600, target=10)   # 证明 d_circ >= 10？
```

**上界 `upper_bound`**：依次运行（`methods` 可选）
1. `graphlike`：`shortest_graphlike_error`（BB 码上没有 graphlike 逻辑错误，直接 `none`）；
2. `stim_search`：`search_for_undetectable_logical_errors`（默认 4/4/False；`stim_search_timeout_s` 可放进子进程限时）。在 gross 上 (5,4) 4 分钟内存涨到 6 GB 仍没结束，`increasing=True` 则什么都找不到，所以这条路走不远；
3. `bposd`：arXiv 2308.07915 Eq.(12) 的随机 η 方法：η = a·L + b·D（a≠0 随机），BP-OSD（min-sum，osd_cs，order 2）解 [D; ηᵀ]ξ = (0,…,0,1)，默认 1500 次；
4. `bposd_lns`：对 BP-OSD 得到的低权重解（权重 ≤ 最好解 + 3，最多 96 个起点）做大邻域搜索：取解的支撑及与其共享 detector 的全部机制（1 跳邻域，约 300–600 列），以当前解为可行提示，用 CP-SAT（单线程，确定性时间 1.0）最小化；有改进就以新解为中心继续（最多 4 次）。gross 上找到 10 的正是这一步（BP-OSD 本身 1500 次一般停在 11–12）。

每个见证都先**注入验证**才计入：去掉全部噪声，在每个故障的原指令位置插入概率 1 的 Pauli 通道（测量翻转则把那一次测量改成 `M(1)`），用 detector 采样器确认 0 个 detector 触发、至少一个 observable 翻转；故障位置与电路对不上（指令名不符）直接判失败，不会被静默忽略。权重口径：DEM（`decompose_errors=False`）中症状相同的机制合并为一列，最少列数 = 最少故障数。

随机性只来自 `seed`：BP-OSD 按 25 次一块，用 `SeedSequence(seed).spawn` 给每块独立的流；LNS 每个起点的 CP-SAT 种子由 (seed, 起点序号) 决定；CP-SAT 用确定性时间上限而不是墙钟。所以结果只取决于 seed 和预算参数，与 `num_workers`（进程池并行）无关（测试覆盖）。`max_seconds` 是墙钟软上限，触发时结果依赖机器速度（`stopped_early=True`）。

**gross code 实测**（IBM depth-8 调度，3 轮，sd6，默认预算，3 个进程）：

| 基底 | seed | 结果 | 耗时 |
|---|---|---|---|
| X | 0–8（9 个） | 全部 **10**（stim_search 12；BP-OSD 本身 10–12） | 81–127 s |
| Z | 0–2 | 全部 **10**（E-002 的 BP-OSD 在 Z 基底只找到 11） | 120–130 s |

见证结构与 E-002 相同：8 个数据比特制备后的 Z 错误 + 2 个 tick 2 的 CNOT 故障（Z 辅助比特目标端的 Z，经后续 CNOT 扩散到数据比特）。E-002 文件里的见证本身也被 `verify_faults` 独立确认（`test_e002_witness_is_confirmed_by_injection`）。单进程约 4–6 分钟/基底。默认预算较小时（600 次 BP-OSD）9 个种子里有 1–2 个停在 11，所以默认值不要随便调低。表面码 d=3、5 上各方法都给出 d。

**下界 `lower_bound`（精确方法，可行性测试）**：同一个 0-1 问题 min |ξ|, Dξ=0, Lξ≠0。
`cpsat`（OR-tools CP-SAT，原生 XOR）、`maxsat`（`stim.Circuit.shortest_error_sat_problem` + pysat RC2，子进程限时）、`milp`（HiGHS，奇偶用整数松弛）。`target=w` 只问“有没有权重 ≤ w−1 的逻辑错误”，CP-SAT 的目标界在超时时仍是有效下界。新依赖 `ortools`、`python-sat`（pyproject 已加）。

| 电路（sd6） | 列 / detector | MILP（1 线程，300 s） | MaxSAT RC2（300 s） | CP-SAT（3 线程，300 s） |
|---|---|---|---|---|
| 表面码 d=3，3 轮 | 221 / 24 | 3，1.3 s | 3，1.3 s | 3，<1 s |
| 表面码 d=5，5 轮 | 1679 / 120 | **5，37–50 s** | 5，94 s | 5，116 s（1 线程 60 s 无进展） |
| 表面码 d=7，7 轮 | 5473 / 336 | 下界 3 | 超时 | 下界 4 |
| BB [[72,12,6]]，1 轮，X | 432 / 72 | 6，299 s | 6，84 s | **6，57 s** |
| BB [[72,12,6]]，1 轮，Z | 432 / 72 | 6，154 s | 6，94 s | – |
| BB72，2 轮，X | 792 / 108 | 下界 3 | 超时 | 下界 5（求最优与 target=6 都是 5） |
| BB72，3 轮，X | 1152 / 144 | 下界 2 | 超时 | 下界 5（target=6） |
| gross，1 轮，X | 864 / 144 | – | – | 下界 6（target=10，600 s） |
| gross，3 轮，X | 2304 / 288 | （E-002：1 轮 Z 120 s 下界 4） | – | 下界 5（target=10，600 s） |

结论：通用精确求解器只能证明到“约 400–1700 列、距离 ≤6”的规模；BB72 从 1 轮到 2 轮（列数 ×1.8）就从 1 分钟内证明变成 5 分钟证明不了，下界停在 5。gross code 3 轮（2304 列，目标 10）在 10 分钟、3 线程下只证到 5，差距 5，按上面的增长看在本机上不可行。**所以目前不能声称 gross 类电路的 d_circ = X，只能说 d_circ ≤ X（有经注入验证的见证）**。要证明需要利用结构：例如 BB 码的平移对称（DEM 在 ℓm 个平移下不变，可加“解至少含一个代表元”的对称破缺约束，搜索空间约缩小 ℓm 倍）、按时间切片的分解、或更强的 MaxSAT 求解器；都没做。小电路（表面码 d≤5、BB72 1 轮、以及 `target` 很小的“距离掉到 2–3”的坏调度）可以在秒到分钟级证明，测试里用到了。

## 4. 与 lead 转达的 5 点补充要求的对应

1. **空闲噪声必须是默认口径**：`DEFAULT_MODEL = "sd6"`，打分模型 `SCORING_MODELS = ("sd6","si1000")` 都含逐层空闲噪声且不可关闭；L0 距离检查默认用 sd6；无空闲噪声的口径只叫 `legacy_no_idle`，只用于与 E-001 对照。
2. **X、Z 两个基底**：`check_l0(..., basis="both")` 要求 `{"Z": ..., "X": ...}` 两条电路，都通过才通过，`d_circ` 取较差者，诊断带 `Z:`/`X:` 前缀；有“牺牲一个基底”的攻击测试。L2 用 X/Z 联合采样，报告 P_Z、P_X、P_any（同一 shot 任一失败），见 §7。
3. **噪声模型**：实现了 `gross_sd6`、`sd6`、`si1000`（含 ResonatorIdle 2p，歧义处理见 §2），另有 `legacy_no_idle` 与通用 `uniform_depolarizing`。
4. **统计约定**：`stats.py` 规定区间一律用似然比因子并标 σ（`likelihood_factor_to_sigma(1000) ≈ 3.72`；95% ↔ 因子 6.83），`BinomialInterval.label()` 输出“LR=1000 interval, ≈3.72σ”，不再写 95%；`MIN_LOGICAL_ERRORS_FOR_COMPARISON = 1000`。L2（§7）按这些约定报告区间，并在任一 sector 少于 1000 次错误时给出警告。
5. **种子**：噪声模块和 stats 没有随机性；L0 的确定性检查用 DEM 反向传播精确判定，不靠采样。距离上界搜索有随机性（BP-OSD 的 η、CP-SAT），种子由 `L0Constraints.distance_seed`（默认 0）显式给出，结果只取决于种子和预算，与进程数无关（§3.1）。测试 `test_report_is_deterministic` 验证同一输入两次报告相同。L2 的种子是必填参数，结果对给定 (seed, batch_size, 停止规则) 逐位可复现，与 worker 数无关（§7.3）。

## 5. 已知局限

- **电路级距离只是上界。** L0 的判定是“多种启发式找到的、经注入验证的最短逻辑错误 ≥ 下限”，真实距离可能更低（旧版在 gross 上报 12、实际 ≤10 就是这样漏的；新版在 gross 上 12 个种子都找到 10，但这仍不是证明）。精确下界只在小电路上可行（§3.1）：gross 规模不能声称 d_circ = X。L0 距离检查在 gross 上单进程约 4–6 分钟/基底（`distance_num_workers=3` 约 2 分钟），搜索内循环若嫌慢，只能调低预算并接受漏报风险。
- **要求“干净切口”**：每轮之间必须有一个时刻，所有辅助比特都不在纠缠中（允许已复位、只做过单比特门的“预制备”状态，因此 IBM 把 Z 检查的复位提前到上一周期的做法可以通过）。辅助比特跨轮流水（一个辅助比特还没测完，下一轮的另一个辅助比特已经和数据纠缠）、测量后不复位直接复用、辅助比特之间先做纠缠（猫态、flag 预处理）、一个稳定子的值由两个分属不同段的测量合成，这些合法电路目前都会被 `stabilizer_coverage` 误拒，诊断会写“cannot split ... / not measured”。如果搜索空间要包含这类电路，需要改成“按测量逐个求解 flow”或“用 detector 的时空结构”来判定覆盖。
- **observable 只能由最终数据读出构成**（按任务说明的定义）。“逻辑算符 ⊕ 若干辅助比特测量”的合法写法会被拒。
- **数据比特读出必须直接用 basis 基测量指令**（X memory 用 MX/MRX，不接受 H+M）。
- 逻辑注入只在两个时刻做（制备后、读出前）。中间时刻不查：轮中注入逻辑算符本来就可能被合法地检测到。
- `qubit_count` 用最大编号+1，不是实际用到的比特数（保守）。
- 没有检查 detector 是否“多余/重复”或坐标是否合理（L0 完全不依赖坐标，候选可以随意伪造坐标而不影响判定）。
- `gross_sd6` 对单比特门（论文电路里没有）施加 DEP1(p) 是自定约定。
- SI1000 的 ResonatorIdle 是否作用于正在做门的比特，默认选择“不作用”，待负责人裁决。

## 6. 评估器还缺的部分（建议）

1. **L1 未实现**：深度、CNOT 数、低权重逻辑错误计数。（L2 已实现，见 §7。）
2. **候选程序沙箱**：§5.2 的“候选不能读写文件/网络、种子由评估器控制”属于搜索框架，不在 L0。
3. **schedule → 电路的生成应由评估器完成**：现在 L0 接收现成电路，`data_qubits`、轮数、比特布局由任务给定。最稳妥的做法是候选只交 schedule，评估器自己生成两个基底的 memory 电路再过 L0，候选就碰不到 detector 与 observable 的声明。
4. **距离的独立复核路径**：`distance.lower_bound`（CP-SAT/MaxSAT/MILP）已有，但只对小电路可行（§3.1）；gross 规模需要利用对称性等结构的专门方法。
5. **跨轮数一致性**：同一调度在 rounds = d 与 rounds = 2d 下都应通过（防止只对特定轮数成立的“巧合”电路）。
6. **噪声模型与门集的绑定**：SI1000 打分要求 CZ 电路，需要约定 CX 调度如何编译成 CZ+H（编译方式会改变分数）。

## 7. L2：逻辑错误率（`l2.py`）

```python
from evaluators.l2 import sample_l2, DecoderConfig, StopRule
res = sample_l2(code, {"Z": circ_z, "X": circ_x}, data_qubits,   # 或 circuits=callable(basis, rounds)
                p=0.006, rounds=12, noise_model="sd6", boundary="paper",
                decoder=DecoderConfig("bposd"),                   # 默认 = E-002 / IBM 设置
                seed=20261002,                                    # 必填
                stop=StopRule(max_shots=10**5, max_errors=1000, min_sector_errors=1000, batch_size=25),
                num_workers=4)
print(res.summary()); res.to_dict()   # rates / per_round / counts / decoder / versions / reproducibility ...
```

输入是同一调度的两条**无噪声** memory 电路（L0 的约定）。`build_joint_circuit` 可单独调用，用于诊断。

### 7.1 X/Z 联合采样（auditor E-002 M1 的修正）

对任意 CSS 码与调度，评估器把两条电路合成一条“联合电路”，在**同一批 shot、同一次噪声实现**里同时得到
两个 sector 的 detector 与 observable：

1. 去掉数据比特的制备（首个双比特门之前的操作）和最终读出后，两条电路的“主体”必须逐层相同（层内顺序无关），
   否则报错。噪声由 `noise.add_noise` 加在整条电路上，主体取 Z 电路的带噪声版本。
2. 加 k 个无噪声参考比特，用 `stim.Tableau.from_stabilizers` 生成无噪声编码电路，制备
   HZ、HX 的独立行与 LZ_j⊗Z_{r_j}、LX_j⊗X_{r_j} 全部为 +1 的态（完美码态，每个逻辑比特与参考比特成 Bell 对），
   所以 Z 型、X 型逻辑同时确定。末尾对这 n+k 个生成元做无噪声 MPP。
3. 候选 detector / observable 中引用数据读出的部分（一个 Z 型或 X 型 Pauli）在 GF(2) 上展开为生成元乘积，
   换成对应 MPP 记录；辅助比特测量按 (层, 比特) 映射。detector 坐标 (0,) = Z sector，(1,) = X sector；
   observable 先 Z 电路的 k 个，再 X 电路的 k 个。
4. 解码：联合 DEM 的每个机制限制到各自 sector（Y 型故障两边各算一次），合并相同症状后每个 sector 建一个解码器
   ——与 E-002 / IBM “X、Z 分开译码” 相同；相关性保留在采样里，只在译码时丢掉。
5. 报告 P_Z、P_X、P_any（同一 shot 任一 sector 失败 = 论文定义）、P_both，以及 `P_indep_approx`
   （= 1−(1−P_Z)(1−P_X)，**只作对照**，不是分数）。`res.joint["approximation"]` 恒为 None：
   不存在需要近似的情形；做不到联合（两基底主体不同、数据比特中途测量等）就报错，而不是退回独立近似。

正确性检查（`tests/test_l2.py`）：`boundary="noisy"` 时，联合 DEM 限制到 Z（X）sector 后与
“带噪声的 Z（X）memory 电路”的 DEM **逐机制相同**（误差 <1e-12；表面码 d=3，sd6 / gross_sd6 / legacy_no_idle；
k=2 的 [[4,2,2]] 码 1、3 轮）；p=0 时联合电路所有 detector / observable 恒为 0。gross code 上 sd6 加在 IBM 无噪声
电路上的 DEM 与 E-002 自带噪声的 DEM 也逐机制相同（`scripts/validate_l2_gross.py` 的 check 部分）。

### 7.2 边界口径 `boundary`

| 口径 | 初态 | 读出 | 用途 |
|---|---|---|---|
| `"paper"`（默认） | 完美码态 | 完美（等价于论文的 1 个无噪声收尾 cycle + 无噪声读出） | **与文献比较**（arXiv:2308.07915 §6 口径）；也是榜单默认 |
| `"noisy"` | 带噪声复位（Z sector 有 R 后 X_ERROR，X sector 有 RX 后 Z_ERROR） | 带噪声测量 | 项目内部口径（E-002 的边界），每个 sector 的边缘分布与单基底带噪声 memory 实验完全一致；只用于同一管线内比较，**不可与论文数字直接比较** |

细节：`paper` 只去掉**数据比特**在其制备结束（含）之前、最终读出所在层（含）之后的噪声；辅助比特的噪声一律保留，
包括第一轮前预先复位的辅助比特（IBM 调度第 0 层的 Z 辅助比特复位翻转）。auditor 的 paper1 变体把第 0 层整层的噪声都去掉了，
所以本实现每 shot 多 72 个复位翻转位置（相当于首轮的测量错误），影响很小。`noisy` 要求每个数据比特的制备恰好是一个
basis 基复位（R / RX），否则报错。

每轮换算：`per_round[P] = 1−(1−P)^(1/rounds)`（论文 §3），区间是对 LR 区间端点做单调变换；另附 sinter 公式
`(1−(1−2P)^(1/r))/2` 的点估计（P≥0.5 时为 None）。区间用 `stats.binomial_interval`（默认 LR=1000，≈3.72σ），
标签写明 LR 因子和 σ。任一 sector 失败数 < `MIN_LOGICAL_ERRORS_FOR_COMPARISON`（1000）时结果带警告。

### 7.3 解码器

- `DecoderConfig("bposd", params)`：ldpc 2.x `BpOsdDecoder`，每个 sector 一个。默认 `IBM_BPOSD_PARAMS` =
  `max_iter=10000, bp_method="min_sum", ms_scaling_factor=0（ldpc 2.x 为自适应缩放，auditor E-002 §3）,
  osd_method="osd_cs", osd_order=7, schedule="parallel"`。结果里记录请求参数和解码器对象回读的实际参数
  （`res.decoder["effective"]`，如 `bp_method="minimum_sum"`、`osd_method="OSD_CS"`）以及每个 sector 的机制数。
- `DecoderConfig("pymatching")`：每个 sector 单独生成一条只含本 sector detector 的电路，由 stim 做 graphlike 分解
  （联合 DEM 直接分解会产生跨 sector 的分量，不能用）。只适用于每个 sector 可 graphlike 分解的码（表面码）。
- `res.versions` 记录 python / stim / sinter / ldpc / pymatching / numpy / scipy 版本与平台。

### 7.4 随机性与可复现性（实际能力）

- **sinter 不能设种子**：sinter 1.16 源码里没有 seed 参数；默认采样器调用 `circuit.compile_detector_sampler()`
  （系统熵），批大小按耗时自适应（ramp throttle）。所以直接用 sinter 的默认采样器不可复现（E-001 auditor M3）。
- 本模块用自定义 `sinter.Sampler`（sinter 仍负责多进程）：关闭 ramp 节流，批大小固定为 `stop.batch_size`；
  批编号 b 由加 `fcntl` 锁的计数文件分配，第 b 批用 stim 种子 `SeedSequence([seed, b])`；每批结果（含逐 shot 失败位）
  原子写入工作目录。sinter 返回后，取**按编号从 0 开始、满足停止规则的最短前缀**为正式结果；前缀中缺失的批（sinter
  停止时在途、被丢弃的）在主进程按同一种子补算；前缀之后多算的批丢弃（编号记在 `reproducibility` 里）。
- 因此正式结果只取决于 (电路, 噪声, 解码器参数, seed, batch_size, 停止规则) 与库版本，**与 num_workers、进程调度、
  耗时无关**。测试：同 seed 下 1 个 worker 与 3 个 worker 的计数与区间完全相同；同一批两次运行逐 shot 相同；换 seed 不同。
- 限制：stim 文档说明同一种子在不同 stim 版本或不同 SIMD 宽度的机器上可能给出不同样本，所以逐位复现只在同一 stim
  版本 + 同类 CPU 上成立；跨机器只能是统计复现。BP-OSD（parallel、osd_cs）与 pymatching 本身是确定性的。
- 改变 `batch_size` 会改变样本（批的划分不同），它是结果身份的一部分，已写进 `inputs.stop`。

### 7.5 停止规则 `StopRule(max_shots, max_errors=None, min_sector_errors=None, batch_size=256)`

满足任一即停：shots ≥ max_shots；或 P_any 失败数 ≥ max_errors 且（若给出）Z、X 两个 sector 的失败数都 ≥ min_sector_errors。
打分 / 比较时建议 `min_sector_errors=1000`（stats.py 约定）。判定作用于批前缀，所以停止点也是确定的。

### 7.6 gross code 验证（`scripts/validate_l2_gross.py`，结果在 `results/l2-validation/`，不上榜）

命令：`uv run python scripts/validate_l2_gross.py --p 0.006 --shots 1000 --batch-size 25 --workers 4 --seed 20261002`
（IBM depth-8 调度，12 个噪声 cycle，sd6，boundary="paper"，BP-OSD IBM 参数）。sd6 加在 IBM 无噪声电路上与 E-002
自带噪声逐机制相同（每基底 8784 个机制，最大概率差 0）。结果 `results/l2-validation/gross_paper_p0.006_r12_seed20261002.json`：

| | 失败 / 1000 shots | 12 cycle 概率 [LR=1000, ≈3.72σ] | 每轮 pL [同区间变换] |
|---|---|---|---|
| Z sector | 319 | 0.319 [0.266, 0.375] | 0.0315 [0.0254, 0.0384] |
| X sector | 284 | 0.284 [0.233, 0.339] | 0.0275 [0.0219, 0.0339] |
| **任一失败 P_any** | 465（两者同时 138） | 0.465 [0.407, 0.524] | **0.0508** [0.0426, 0.0599] |
| 独立近似（仅对照） | — | 0.512 | 0.0582 |

对照：论文拟合 0.0511（arXiv:2308.07915 Table 6 拟合式，本实验 / 论文 = 0.99）；auditor 联合采样 paper1 变体
0.0537 [bootstrap 95%: 0.0459, 0.0628]，320 shots（本实验 / auditor = 0.95）。三者在误差内一致。
X/Z 同时失败 0.138，独立时应为 0.091，正相关与 auditor 的发现一致；独立近似会把每轮 pL 高估约 15%。
耗时：墙钟 1438 s，解码 CPU 5114 s（约 5.1 CPU 秒/shot），4 个 worker，前缀 40 批全部由 sinter 完成，无丢弃、无补算。
注意每轮的 sinter 公式 `(1−(1−2P)^(1/r))/2` 只对单个 observable 有意义，k=12 时不要用（P_any 给出 0.099）。

### 7.7 已知局限

- 联合采样要求两个基底的主体完全相同，且数据比特在制备与最终读出之间不被测量 / 复位；observable 只能由最终数据读出构成
  （与 L0 一致）。
- 最终读出必须紧跟数据比特的最后一个双比特门（中间不能有单比特门）。
- `noisy` 口径的“联合分布”是构造出来的：物理上不能同时在 Z 基和 X 基制备 / 读出，所以只有两个 sector 的边缘分布有物理意义，
  P_any 是内部约定。
- 解码按 sector 分开（丢掉 Y 相关性），与 IBM 一致；用相关解码会更好，但会改变分数口径。
- BP-OSD 逐 shot 在 Python 里循环调用（gross code p=0.006 约 4–5 CPU 秒/shot，两 sector 合计），全零 syndrome 跳过。
- 每次 `sample_l2` 都会新开 sinter 进程池并在每个 worker 里重建解码器（gross code 约 10–20 s）。

## 8. 成绩单（`leaderboard.py`）

```python
from evaluators.leaderboard import build_entry, submit, verify_leaderboard
entry = build_entry("cand-0007", code=code, circuits={"Z": cz, "X": cx}, l0_report=l0_report,
                    distance_upper_bound=l0_report.d_circ, l2=res)
rec = submit(entry)                 # 默认追加到 research/leaderboard.jsonl；测试必须传临时路径
assert verify_leaderboard() == []
```

- 每行字段：`candidate_id`、`code`（n、k、行数、校验矩阵 sha256）、`schedule_hash`（两条无噪声候选电路的 sha256）、
  `noise_model`、`p`、`rounds`、`boundary`、`l0`（passed、d_circ、各检查状态、各基底 d_circ）、`distance_upper_bound`、
  `l2`（完整 L2Result）、`extra`，以及由 `submit` 自动填写的 `time`（UTC）、`evaluator`（`scripts/freeze_evaluator.py`
  的同一哈希函数算出的评估器哈希、是否冻结、是否与 FROZEN 记录一致）、`git`（commit、evaluators/ 是否有未提交修改）、
  `versions`、`prev_hash`、`entry_hash`。
- **只追加**：`open(..., "a+")` + `fcntl.flock` 排他锁，锁内读最后一行取 `prev_hash`、追加、`fsync`。文件不以换行结尾
  （疑似被截断）或最后一行不是合法记录时拒绝追加。
- **哈希链**：`entry_hash` = 除自身外所有字段规范 JSON 的 sha256；`prev_hash` = 上一行的 `entry_hash`（首行 64 个 0）。
  `verify_leaderboard` 能发现改写任何一行或删行。注意哈希链防的是“事后悄悄改”，不防“有人连同后续所有行一起重算”；
  配合 git 历史使用。
- 拒绝：缺必备字段；调用方自带系统字段（如伪造 `evaluator`）；L0 未通过；L2 结果标注为近似。
- 测试（`tests/test_leaderboard.py`）：追加与哈希链、评估器哈希与 `freeze_evaluator.py hash` 一致、篡改 / 删行 / 截断被发现、
  6 个进程并发各写 5 行不损坏，并检查真正的 `research/leaderboard.jsonl` 在测试前后不变。
