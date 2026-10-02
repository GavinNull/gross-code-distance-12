# evaluators/：评估器第一部分（噪声模型 + L0 合法性检查）

状态：未冻结（P1 进行中）。冻结前需 auditor 攻击测试（G1）。
测试：`uv run pytest tests/test_l0.py tests/test_noise.py tests/test_codes.py tests/test_stats.py -q`（约 10 秒，单核）。

| 文件 | 内容 |
|---|---|
| `codes.py` | `CSSCode`（HX/HZ/LX/LZ，GF(2)）、自检、`code_dimension`、`compute_logicals`、GF(2) 工具、测试用 `rotated_surface_code_from_stim` |
| `noise.py` | `add_noise(circuit, model, p, ...)`，命名噪声模型 |
| `l0.py` | `check_l0(circuit, code, basis, constraints) -> L0Report` |
| `stats.py` | 置信区间与统计口径约定（似然比因子 ↔ σ） |

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
| `circuit_distance` | 对 `add_noise(circuit, distance_noise_model)`（默认 sd6，含空闲噪声）先生成 DEM（确认加噪声后也不报错），再取 `search_for_undetectable_logical_errors`（截断参数可配，默认 4/4/False）与 `shortest_graphlike_error` 两者中较短的那个错误集合的大小，作为 d_circ **上界**；要求 ≥ `min_circuit_distance`。在子进程里运行，`distance_timeout_s`（默认 120 s）到时杀掉进程并判为不通过。诊断列出这条最小权重逻辑错误的每个组成部分（tick、噪声指令、比特、Pauli），例如 `tick 4: DEPOLARIZE2 on [8, 9] -> X8*Y9`，可直接告诉 LLM 哪一步的 hook 错误降低了距离。 |

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

## 4. 与 lead 转达的 5 点补充要求的对应

1. **空闲噪声必须是默认口径**：`DEFAULT_MODEL = "sd6"`，打分模型 `SCORING_MODELS = ("sd6","si1000")` 都含逐层空闲噪声且不可关闭；L0 距离检查默认用 sd6；无空闲噪声的口径只叫 `legacy_no_idle`，只用于与 E-001 对照。
2. **X、Z 两个基底**：`check_l0(..., basis="both")` 要求 `{"Z": ..., "X": ...}` 两条电路，都通过才通过，`d_circ` 取较差者，诊断带 `Z:`/`X:` 前缀；有“牺牲一个基底”的攻击测试。L2 的逻辑错误率合并（取较差或求和）还没实现。
3. **噪声模型**：实现了 `gross_sd6`、`sd6`、`si1000`（含 ResonatorIdle 2p，歧义处理见 §2），另有 `legacy_no_idle` 与通用 `uniform_depolarizing`。
4. **统计约定**：`stats.py` 规定区间一律用似然比因子并标 σ（`likelihood_factor_to_sigma(1000) ≈ 3.72`；95% ↔ 因子 6.83），`BinomialInterval.label()` 输出“LR=1000 interval, ≈3.72σ”，不再写 95%；`MIN_LOGICAL_ERRORS_FOR_COMPARISON = 1000`。真正执行这些约定的 L2 采样还没写。
5. **种子**：L0、噪声模块和 stats 都没有随机性：确定性用 DEM 反向传播精确判定，不靠采样；距离搜索是确定性算法。测试 `test_report_is_deterministic` 验证同一输入两次报告相同。L2 采样的种子要由显式参数给出并记录（待实现）。

## 5. 已知局限

- **电路级距离只是上界。** stim 文档明说 `search_for_undetectable_logical_errors` 是启发式（截断后可能漏掉更短的错误），`shortest_graphlike_error` 只看 graphlike 机制。所以 L0 的判定是“找到的最短逻辑错误 ≥ 下限”，真实距离可能更低。冻结前的最终结果应提高截断参数，或用 SAT/ILP（`shortest_error_sat_problem`，或 baselines 里的方法）独立复核。gross code 上默认截断参数的耗时没测过（只测了表面码 d≤5，<1 s）。
- **要求“干净切口”**：每轮之间必须有一个时刻，所有辅助比特都不在纠缠中（允许已复位、只做过单比特门的“预制备”状态，因此 IBM 把 Z 检查的复位提前到上一周期的做法可以通过）。辅助比特跨轮流水（一个辅助比特还没测完，下一轮的另一个辅助比特已经和数据纠缠）、测量后不复位直接复用、辅助比特之间先做纠缠（猫态、flag 预处理）、一个稳定子的值由两个分属不同段的测量合成，这些合法电路目前都会被 `stabilizer_coverage` 误拒，诊断会写“cannot split ... / not measured”。如果搜索空间要包含这类电路，需要改成“按测量逐个求解 flow”或“用 detector 的时空结构”来判定覆盖。
- **observable 只能由最终数据读出构成**（按任务说明的定义）。“逻辑算符 ⊕ 若干辅助比特测量”的合法写法会被拒。
- **数据比特读出必须直接用 basis 基测量指令**（X memory 用 MX/MRX，不接受 H+M）。
- 逻辑注入只在两个时刻做（制备后、读出前）。中间时刻不查：轮中注入逻辑算符本来就可能被合法地检测到。
- `qubit_count` 用最大编号+1，不是实际用到的比特数（保守）。
- 没有检查 detector 是否“多余/重复”或坐标是否合理（L0 完全不依赖坐标，候选可以随意伪造坐标而不影响判定）。
- `gross_sd6` 对单比特门（论文电路里没有）施加 DEP1(p) 是自定约定。
- SI1000 的 ResonatorIdle 是否作用于正在做门的比特，默认选择“不作用”，待负责人裁决。

## 6. 评估器还缺的部分（建议）

1. **L1/L2 未实现**：深度、CNOT 数、低权重逻辑错误计数；sinter 采样（两个基底合并打分、似然比区间、≥1000 次错误、显式种子、解码器版本钉死）。
2. **候选程序沙箱**：§5.2 的“候选不能读写文件/网络、种子由评估器控制”属于搜索框架，不在 L0。
3. **schedule → 电路的生成应由评估器完成**：现在 L0 接收现成电路，`data_qubits`、轮数、比特布局由任务给定。最稳妥的做法是候选只交 schedule，评估器自己生成两个基底的 memory 电路再过 L0，候选就碰不到 detector 与 observable 的声明。
4. **距离的独立复核路径**（SAT/ILP），至少用于榜单上的结果。
5. **跨轮数一致性**：同一调度在 rounds = d 与 rounds = 2d 下都应通过（防止只对特定轮数成立的“巧合”电路）。
6. **噪声模型与门集的绑定**：SI1000 打分要求 CZ 电路，需要约定 CX 调度如何编译成 CZ+H（编译方式会改变分数）。
