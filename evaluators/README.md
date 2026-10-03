# evaluators/：评估器（v2.1：候选只交调度，评估器生成电路、跑 L0 / 距离 / L2、写成绩单）

状态：未冻结。评估器 v2（2026-10-02）修复了 auditor G1 前全面攻击（`research/audits/2026-10-02-evaluator-G1.md`）
的全部问题；**v2.1（2026-10-03）修复了第二轮审计（`research/audits/2026-10-02-evaluator-v2.md`）“冻结前必须修”的
第 1–7 条，并为 H-004 加了只评距离的任务**（§0.1）。需 auditor 复审 §0.1 各项后由 PI 冻结（§10）。
**H-005（2026-10-03）新增解码器任务**（`kind="decoder"`，候选提交解码程序，§12），同样需要 auditor 攻击后再冻结。

## 0.1 评估器 v2.1 变更一览（auditor v2 §4 与 H-004）

```python
from evaluators.pipeline import evaluate, screen
rep = screen("bb90-dcirc", None, schedule_json)    # 搜索内循环：L0 + 距离，不跑 L2，不写榜（bb90 约 1 分钟，3 进程）
print(rep.to_text())                               # 含最短见证的调度坐标（轮次、时间步、校验、数据列、Pauli）
rep = evaluate("bb90-dcirc", None, schedule_json)  # 正式：同上，并在满足条件时写榜（距离任务单独排名）
```

| # | 问题 | 修复 | 回归测试（全部在 `tests/test_v21_audit_fixes.py`，除非另注） |
|---|---|---|---|
| S4 | 批文件注入：改写 L2 批结果文件即可写进低 260 倍的分数 | (a) `l2._load_batches` 逐批核对：文件名 = index、shots = batch_size、stim 种子 = SeedSequence([seed, index])、fail_Z/X/any/both = 逐 shot 失败位的 popcount；(b) 每次运行随机生成 32 字节 HMAC 密钥（只在内存里，经 sinter 的 pickle 传给 worker），每个批文件带签名，主进程验签；另外主进程随机抽 `spot_checks`（默认 2）个批按同一种子重算、逐位比较；任何不符 → `L2IntegrityError`，pipeline 状态 `integrity_error`、不写榜；(c) `pipeline.evaluate` 与 `reproduce_entry` 去掉 `work_dir`，目录由 `tempfile.mkdtemp` 创建（0700），`sample_l2(work_dir=...)` 也会 chmod 0700；(d) `entry_problems` 核对 shots = batches_used × batch_size 及计数自洽 | `test_S4_*`：auditor 的攻击进程（扫描新 `l2_*` 目录替换第 0 批）→ `integrity_error`；未签名 / 改动 / 重签但不一致的批文件逐项被拒；W1 式 shots×3 伪造被 entry_problems 发现 |
| S8 | 冗余行的组合被数成额外窗口（BB72 12 个合法自由窗口调度误拒 10 个，gross 3 个误拒 1 个） | L0 新参数 `generator_ancillas`（{"X3": 比特, ...}）：给出时 flow 计数只数**跨度包含该行自己辅助比特某次测量所在层**的窗口（§3.2.2）。pipeline 的模板电路总是给出；原始电路不给，行为不变。另外 `candidate.template_round_counts` 直接读电路核对“每行每轮恰好一次 复位→全部 CNOT→测量”，pipeline 要求它与 L0 计数一致 | `test_S8_*`：auditor 的 12 个 BB72 调度与 3 个 gross 调度全部通过；声称 2/4 轮的 3 轮电路仍被拒；`tests/test_g1_attacks.py`（A1/A1b 伪轮次等）全部照常通过 |
| S1 | 全局平移改变生成的电路（同一哈希两种电路） | pipeline 一律用 `spec.canonical()` 生成电路（`pipeline.circuits_for`），`entry_problems` 同样 | 200 个随机自由调度 × 全部平移：哈希、电路都相同；Strikis 8 个平移 1 种电路；auditor 的非规范平移调度能打分并写榜 |
| S10 / W2 | 正式成绩单守卫用字符串比较路径；verify 不看 purpose / 冻结 / 版本 | `leaderboard.is_official_path`：resolve 后比较，并认硬链接（samefile）；`verify_leaderboard(official=None)` 对正式榜自动加 `official_problems`：purpose=score、记录的评估器 frozen 且 verified、哈希 = `research/evaluator_freeze.json`、库版本 = `PINNED_VERSIONS`（`library_versions` 现在也记录 ortools、python-sat） | 相对路径 / `..` / 符号链接 / 硬链接都被认作正式榜；自检任务经相对路径不再写入；伪造 evaluator / versions 字段被报出 |
| S5 | 种子可以挑 | purpose="score" 的任务：L2 种子 = `derive_seed(task_hash, schedule_hash, "l2")`（sha256 的前 63 位），调用方的 seed 被忽略并在 `Report.diagnostics` 里记一条；`entry_problems` 核对记录的种子；距离任务的距离种子同样派生（"distance"）。自检任务仍可用调用方种子（None = 派生） | 两个不同 seed 计数逐位相同、种子 = 派生值；改种子的记录被拒 |
| F7 | `PYTHONPYCACHEPREFIX` 让 evaluators/ 之外的伪造 pyc 被加载 | `pipeline.runtime_integrity()`：`sys.pycache_prefix` 必须为 None；每个已加载的 `evaluators.*` 模块 `__file__` / `__spec__.origin` 在 evaluators/ 内、由 `SourceFileLoader` 从 .py 加载、`__cached__` 在 `evaluators/__pycache__` 内。`evaluate` / `screen` 开头断言（否则 RuntimeError），`environment_check` 也报告 | 设 prefix、注入外部模块、改 `__cached__` 都被报出；带 PYTHONPYCACHEPREFIX 的子进程里 screen 拒绝运行 |
| R2 | reproduce_entry 只比顶层 counts（diff 任务） | `reproduce_entry` 比较每个 component 的计数与每轮 P_any；`entry_problems` 核对顶层 `counts["rounds_r"]` = `components[r].counts`、顶层 shots = 两者之和 | auditor 的 R2 伪造被两者都发现 |
| — | numpy 整数 / ScheduleSpec 对象绕过解析（auditor v2 S2 小问题） | `parse_schedule` 接受 numpy 整数并规范成 int；ScheduleSpec 对象也先转成 dict 再严格解析（period 上限、时间步范围） | `test_numpy_*`、`test_schedule_object_*` |
| H-004 | 只评距离的任务、screen 入口、见证翻译 | §9.4 | `tests/test_distance_tasks.py` |

**没有改的**：`.claude/settings.json` 是否纳入冻结清单（auditor v2 F9）等 PI 决定。冻结清单 `EXTRA_FILES` 加了
`tests/test_v21_audit_fixes.py`、`tests/test_distance_tasks.py`、`tests/v21_helpers.py`。

## 0. 评估器 v2 一览（先读这里）

```python
from evaluators.pipeline import evaluate
rep = evaluate("gross-sd6-p4e-3", None, schedule_json, seed=20261002, candidate_id="cand-0007")
print(rep.to_text())     # 逐项诊断（可直接喂给 LLM）；rep.status / rep.score / rep.leaderboard_record
```

- **候选只提交调度 JSON，不提交电路**（§9.1）。评估器用固定模板生成双基底、任意轮数的无噪声 memory 电路，噪声按任务
  由 `noise.py` 加。伪轮次、轮数造假、读出后再测、`I` 门把空闲变“制备”、自带噪声 / 指令等攻击在结构上不可能。
- **唯一入口** `pipeline.evaluate(task_id, code_spec, schedule, *, seed)`（§9.2）：任务注册表（`tasks.py`）冻结码族、
  噪声（只允许 sd6）、p、解码器、边界、轮数、停止规则、L0 距离门槛与预算、分层漏斗（等 E-004）。
- **只有 pipeline 能写成绩单**（§8）：`leaderboard.submit` / `build_entry` 已删除；记录带 task_id、task_hash、规范化
  调度及其哈希、每个轮数的电路哈希、L0 实测轮数；写入前和 `verify_leaderboard` 都做语义核对；哈希链需要 git 外部锚点。
- L0 仍保留作为第二道防线，并修了伪轮次（§3.2.1）。底层接口 `check_l0` / `sample_l2` 仍可单独调用（诊断、实验），
  但它们的结果不能上榜。
- 冻结：`scripts/freeze_evaluator.py` 哈希 evaluators/ 下全部文件 + 冻结脚本 + hook + pyproject.toml + uv.lock + 评估器测试，
  拒绝清单外文件、伪造 .pyc、扩展模块；关键库版本固定（§10）。

测试（评估器 v2）：`uv run pytest tests -q`（全部；含 `test_candidate.py`、`test_pipeline.py`、`test_g1_attacks.py`、
`test_freeze.py`、`test_leaderboard.py`）；慢测试 `-m slow`。
测试：`uv run pytest tests/test_l0.py tests/test_noise.py tests/test_codes.py tests/test_stats.py -q`（约 2 分钟，单核；距离检查改用 `distance.upper_bound` 后变慢，测试里用轻量预算 `FAST_DIST`；`test_l0.py` 含 gross code 的 Strikis / IBM 电路，读 `baselines/`）。
距离：`uv run pytest tests/test_distance.py -q -m "not slow"`（约 20 秒）；gross code 回归 `-m slow`（2 个测试，各约 2 分钟，3 进程）。

| 文件 | 内容 |
|---|---|
| `codes.py` | `CSSCode`（HX/HZ/LX/LZ，GF(2)）、自检、`code_dimension`、`compute_logicals`、GF(2) 工具、测试用 `rotated_surface_code_from_stim` |
| `noise.py` | `add_noise(circuit, model, p, ...)`，命名噪声模型 |
| `l0.py` | `check_l0(circuit, code, basis, constraints) -> L0Report` |
| `distance.py` | 电路级距离：`upper_bound(...) -> DistanceResult`（多方法取经注入验证的最短见证）、`lower_bound(...)`（CP-SAT / MaxSAT / HiGHS 精确法）、`verify_faults`，见 §3.1 |
| `stats.py` | 置信区间与统计口径约定（似然比因子 ↔ σ） |
| `l2.py` | `sample_l2(...) -> L2Result`：X/Z 联合采样的逻辑错误率（sinter 多进程、显式种子、可逐位复现），见 §7 |
| `leaderboard.py` | 成绩单：只接受 pipeline 的写入（私有 `_append` + 凭证）、语义核对 `entry_problems`、`verify_leaderboard`（哈希链 + git 锚点）、`table(task_id)`、`reproduce_entry`，见 §8 |
| `candidate.py` | 候选调度 JSON 规范、模板约束 `validate_schedule`、模板电路 `memory_circuit` / `build_circuits`，见 §9.1（v2） |
| `tasks.py` | 任务注册表 `TASKS`（码族、噪声、p、解码器、边界、轮数、停止规则、L0 门槛、漏斗）、`PINNED_VERSIONS`，见 §9.3（v2） |
| `pipeline.py` | 唯一评估入口 `evaluate(task_id, code_spec, schedule, *, seed) -> Report`，见 §9.2（v2） |

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
- ~~搜索代码只应调用 `check_l0` / `add_noise` 这两个公开入口。~~ 评估器 v2 起，搜索代码只应调用
  `evaluators.pipeline.evaluate`（提交调度 JSON）；`check_l0` 是 pipeline 内部的第二道防线，也可用于诊断。

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

- **评估器 v2：`SCORING_MODELS = ("sd6",)`**，`DEFAULT_MODEL = "sd6"`。si1000 移出打分模型：auditor G1 N1（`I` 门躲开
  ResonatorIdle）已修——在有隐式空闲噪声且 I 门噪声与空闲不同的模型（si1000）里，`I` 按空闲比特处理（空闲 + ResonatorIdle）；
  但 N2（SI1000 原生 CZ+H 电路被 L0 / L2 误拒）没修，且模板电路只用 CX，CX→CZ+H 的编译约定也没定。修好之前任务注册表只允许 sd6。
  sd6 / si1000 都有逐层空闲噪声，**不可关闭**（传 `idle=False` 直接报错）。
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
| `stabilizer_coverage` | **默认（`coverage_method="flows"`，2026-10-02 起）：对整条电路求 flow，不切段，支持辅助比特跨轮流水，方法见 §3.2。** 旧方法（`coverage_method="segments"`，只为对照保留）：在“干净切口”处把电路切段：对每个非数据比特追踪状态 idle（未用/测量后）、prepped（复位后只有单比特门）、busy（复位后做过双比特门、尚未测量）；没有 busy 比特的 TICK 是干净切口（从第一个数据双比特门所在层开始，排除最终读出）。每段单独成一条电路，开头重放 prepped 比特的复位与单比特门（MR 重放成 R），再对每个稳定子生成元 s 调用 `solve_flow_measurements([P_s -> 1])`（P_s = s 在数据比特上的 Pauli）：有非空解 = 本段测量了 s（输入时刻的 s 值等于这些测量的奇偶）；解为空 = s 被本段的复位抹掉；无解 = 未测。要求每个生成元（含冗余行，含非 basis 型）被测次数 = `rounds`（未给则全部相等且 ≥1）。 |
| `detector_coverage` | 用上一步每段的测量集合 M_r(s) 构造“应有的比较”：basis 型 s 的首轮 M_1（数据在 basis 基制备，确定）、相邻轮 M_r ⊕ M_{r+1}、末轮与数据读出 M_last ⊕ readout(supp s)；`require_opposite_type_detectors=True` 时非 basis 型的相邻轮比较也要。用 GF(2) 增量基（Python int 位集）检查每个比较都在 detector 记录集合的张成里。因为 `solve_flow_measurements` 的解不唯一（可相差段内确定的测量组合，例如冗余稳定子行的 meta-check），先用每段的 `flow_generators()` 取出“输入输出都为恒等”的段内确定奇偶，一并放进张成里再判断（它们不要求被声明为 detector）。默认的 flow 方法用同样的比较，代表元与“窗口内确定奇偶”的定义见 §3.2。 |
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
| **流水电路**（`memory_builder.build_pipelined_memory`，没有干净切口）：第 0 轮某 Z 检查少一个 CNOT，detector 相应改写，全部确定、逻辑注入通过 | stabilizer_coverage（该稳定子只测 2 次） |
| 流水电路排空阶段少测一轮（最后一轮 X 辅助比特做完 CNOT 不测量），Z / X memory | stabilizer_coverage（X 型只测 2 次） |
| 流水电路灌入阶段（第 0 轮）detector 全部缺失 | detector_coverage（first round vs. preparation） |
| 流水电路某轮跳过一个稳定子 / 轮数少一轮 / 多一轮 / 删掉末轮与读出的比较 | stabilizer_coverage / detector_coverage |
| Strikis gross 电路（arXiv:2603.05481 Fig. 12）删掉第 0 轮全部 72 个 Z detector | detector_coverage |

正面：表面码、Steane、[[4,2,2]] 的流水电路两个基底都通过（旧的切段方法误拒，测试里作为对照）；gross code 的
Strikis 流水电路（E-003）与 IBM 电路在 3 轮、12 轮、两个基底下都通过 L0（不含距离；Strikis 12 轮两个基底约 8 s，
IBM 约 6 s）。有干净切口的电路上两种方法的计数相同（测试）。

### 3.2 覆盖检查的 flow 方法（`coverage_method="flows"`，默认；修复 evaluator_issues 2026-10-02 E-003 条）

旧方法要在“干净切口”处切段，辅助比特跨轮流水的电路（Strikis，arXiv:2603.05481 Fig. 12）没有切口，整条电路只切出一段，
每个生成元被判“只测了 1 次”。新方法不切段：

1. **body**：去掉数据比特的制备（首个数据双比特门之前作用在数据比特上的复位 / 单比特门）和最终读出，辅助比特的复位全部保留；
   数据比特的输入因此是自由的。
2. **一次 `flow_generators()`**：把每个 flow 写成位向量（测量 ‖ 输入 Pauli ‖ 输出 Pauli），GF(2) 消元（最高位为主元）。
   得到 D = 所有“输入、输出都是恒等”的 flow 的测量集合（与数据输入无关的确定奇偶，包括所有合法的 detector），以及每个
   稳定子生成元 s 的一个特解 M_s（flow `s ⊗ I → 1`：这组测量的奇偶 = 输入时刻 s 的值）。“测量了 s 的测量集合”恰好是陪集
   A_s = M_s + D。无解 = 输入时刻的 s 从未被确定（例如被测量了反对易的东西扰乱，或根本没测）。
3. **计数**：s 被测 r 次 ⇔ 存在 r 个时间上互不重叠的层区间，每个区间里都有 A_s 的一个元素。区间只限制“用哪些测量记录”，
   区间之前的门全部算在内（反向传播一直走到 body 开头），所以不需要干净切口：流水电路里 X 辅助比特跨过 Z 检查的窗口起点，
   这些项在全电路里自然抵消。求解：对 D 求**最小跨度基**（trellis 理论的 MSGM：所有基向量的最低位互不相同、最高位也互不相同），
   插入 M_s 得到 D + span{M_s} 的最小跨度基，并标记含 M_s 的基向量（phi=1）。性质：任意组合的最低 / 最高位就是所用基向量的
   最低 / 最高位中的最小 / 最大者，所以“区间里有 A_s 的元素 ⇔ 有一个 phi=1 的基向量跨度落在区间内”，最大不相交区间数 =
   这些跨度的区间调度贪心解（按结束层排序）。要求计数 = `rounds`（未给则全部相等且 ≥1）；多测一轮也拒绝。
4. **detector 覆盖**：每个区间选中的基向量就是该轮的代表 c_j。要求首轮 c_1（basis 型）、相邻轮 c_j ⊕ c_{j+1}、末轮与读出
   c_r ⊕ readout(s) 在 detector 张成里；允许模掉 **“完全落在 s 的某一个区间之内”的确定奇偶**（D 中跨度在单个区间内的基向量，
   例如冗余行的 meta-check、对面类型的 meta-check；它们是代表元不唯一带来的歧义）。这不会让检查变空：c_j ⊕ c_{j+1} 若是若干
   窗口内确定奇偶之和，限制到第 j 个窗口就得到 c_j ∈ D，与 c_j ∈ A_s 矛盾。

代价：gross code 12 轮每个基底约 2000 个 flow 生成元，`flow_generators` 0.2 s；整个覆盖检查与旧方法耗时相当（同机同负载下每个基底约 6 s，两种方法相差 <10%）。

**这一方法能接受、旧方法误拒的电路**：辅助比特跨轮流水；一个稳定子的值由多个测量合成（猫态 / flag 式的组合测量，只要这些
测量在同一个时间窗内）。**仍然不支持**：测量后不复位直接复用辅助比特（第 j 轮的值是 m_{j-1} ⊕ m_j，与上一轮的窗口重叠，
3 轮会被数成 2 次而拒绝，已用 stim 表面码电路把 MR 换成 M 验证）。

### 3.2.1 重提取判据（评估器 v2，修复 auditor G1 A1/A1b “伪轮次”）

上面的计数只要求“窗口里的测量奇偶等于输入时刻 s 的值”。auditor 发现：1 轮真提取之后反复重测同一个（测量后不复位的）
辅助比特，每次重测都等于 s_in，于是被数成很多轮，分数虚高 4.5–70 倍。现在额外要求**每个窗口都从数据比特重新提取 s**：

- 对相邻窗口的代表元之差 d_j = c_{j−1} ⊕ c_j（属于 D，确定），在 body 上加成 detector，用 `detecting_regions` 求它在
  每个时刻的敏感区域；要求在 [窗口 j−1 结束层, 窗口 j 结束层) 之间存在某个时刻，区域限制到数据比特上**恰好是 s**
  （s 支撑上的数据错误在这段时间里会翻转这次比较）。伪轮次的区域只在辅助比特上，被拒（诊断写明 “fake”）。
- 代表元不唯一：严格判据不成立时，允许加上完全落在窗口 j 内的确定奇偶（D 的最小跨度基中跨度在窗口内的向量，例如冗余行的
  meta-check）的区域再比较（GF(2) 张成判定）。另外，区间调度在结束层相同时优先选跨度最短的候选，使代表元是“自然的”单次提取。
  两条措施各自都能让 Strikis 流水电路通过（测试过）。
- `data_layout` 新增：最终数据读出之后不允许再有任何测量（A1b）。
- 回归：`tests/test_g1_attacks.py::test_A1_*`、`test_A1b_*`（d=3/3 轮、d=5/10 轮，两个基底，含距离门槛时也被拒）；
  已有全部 L0 测试（表面码、Steane、[[4,2,2]] 流水、冗余行、gross IBM / Strikis 3 与 12 轮）照常通过。

**语义与可接受的“软”情形**（auditor 请复核）：
- 计数的是“时间上不重叠的、能确定 s 输入值的测量”，不是“每个 cycle 恰好一次”。在一轮里用新的 CNOT 连续提取两次、另一轮不测，
  计数仍是 r，会被接受（每次都是真提取）。~~这不是对候选有利的作弊~~——auditor G1 指出旧版的这一说法对“只重测辅助比特”是错的；
  v2 的重提取判据已堵住。模板电路（pipeline）里每个校验每轮恰好一次，这一情形不会出现。
- 冗余行 s3 = s1 + s2：某轮不测 s3、只测 s1 和 s2，s3 在该轮仍算“被测了”（它的值确定）。与旧方法相同。
- 冗余关系下单个 detector 可以省略：例如 gross code 的 HZ 有 6 个冗余关系，删掉一个第 0 轮的 Z detector，它等于其余行的
  detector ⊕ 一个该轮内部的 meta-check，而 meta-check 不要求声明，所以被接受（与旧方法相同）。这只让译码器少一条信息，
  不能降低逻辑错误率或抬高距离；测试里删掉全部 72 个第 0 轮 detector 才会被拒。

### 3.2.2 按“自己的辅助比特”计数（评估器 v2.1，修复 auditor v2 S8）

现象：BB 码有冗余行。若冗余行 s = s₁ + … + s_k，而 s₁..s_k 的测量时刻都不同于 s 自己的测量时刻，那么“s₁..s_k 这一轮的
测量”也是 A_s 的元素，它的跨度与 s 自己的测量不重叠，§3.2 的区间调度就把每轮数成 2 次（“测了 6 次，要求 3 次”）。
IBM 调度所有校验同一时刻测量，所以不受影响；逐检查自由的调度大多会撞上。

修复：`L0Constraints.generator_ancillas = {"X3": q, "Z5": q', ...}`（类型 + HX/HZ 行号 → 该行的辅助比特）。给出时，
第 2 步的候选窗口只保留**跨度包含该辅助比特某次测量所在层**的那些。由最小跨度基的性质，单个自测量 {m_j} ∈ A_s 时
一定存在跨度落在 [layer(m_j), layer(m_j)] 内的 phi=1 基向量，所以诚实电路的每一轮都被数到；别的行的组合只要不跨过
自测量的层就不再计数（跨过时，按结束层排序的贪心会先选到自测量那个更短的窗口）。这一过滤**只会让计数变少**，
少测仍然被拒；重提取判据与 detector 覆盖照旧在选中的窗口上运行。pipeline 总是给出这个映射（模板布局已知），并另外用
`candidate.template_round_counts` 直接读生成的电路核对“每行每轮恰好一次 复位 → 全部 CNOT → 测量”，两者都要等于轮数。
原始电路（`check_l0` 直接调用、不给映射）的计数口径不变，G1 的 A1 / A1b 伪轮次回归测试照常被拒。

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
- ~~要求“干净切口”~~（2026-10-02 已改为 flow 方法，§3.2，流水电路可以通过）。仍不支持：**测量后不复位直接复用辅助比特**（会被数少一次而拒绝）。
  覆盖计数的语义是“时间上不重叠、且每个都从数据比特重新提取的测量窗口数”（v2，§3.2.1）。
- **冗余校验行（L0-2，PI 未裁决）**：在原始电路上，L0 仍把“冗余行 s3 = s1 + s2 从不单独测量”视为每轮都测了（它的值确定）。
  pipeline 不受影响：模板要求每一行（含冗余行）都有自己的辅助比特、每轮测一次；任务的 `allow_redundant_row_omission`
  在 PI 裁决前不能为 True。
- **冗余 / 复合 detector 会让 graphlike 与 stim_search 失明**（auditor G1 D1），此时距离只靠 BP-OSD（+LNS）一条路径；
  模板电路的 detector 由评估器生成（每个 basis 型校验每轮一个），不存在这一情形。
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
3. ~~schedule → 电路的生成应由评估器完成~~：评估器 v2 已实现（§9）。
4. **距离的独立复核路径**：`distance.lower_bound`（CP-SAT/MaxSAT/MILP）已有，但只对小电路可行（§3.1）；gross 规模需要利用对称性等结构的专门方法。
5. ~~跨轮数一致性~~：pipeline 对每个打分轮数（diff 时两个）与距离轮数都由同一调度生成电路，打分轮数的电路都过 L0（v2）。
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
| `"flat"`（2026-10-02） | 同 paper，并去掉每个数据比特**第一个双比特门之前、最后一个之后**的全部单比特噪声（灌入 / 排空层的数据空闲） | 同 paper | auditor E-003 的“拉平”口径（`trim.py`），单次运行即可比较流水与非流水电路；gross 上与 auditor 逐项一致（Strikis 去掉 720 个位置、IBM 288 个；Z 基底 DEM Σ先验 58.28 / 57.85，测试覆盖）。辅助比特噪声和全部双比特门噪声保留，所以流水电路首末轮 CNOT 之间的等待（gross 上 144 个位置）仍然多出来 |
| `"diff"`（2026-10-02，**推荐用于流水 vs 非流水**） | 两次采样（轮数 r1 < r2，各自用 `diff_inner_boundary`，默认 paper） | 同左 | 用差分消去边界，估计**体内每轮错误率**，对所有电路一致，见 §7.2.1 |

`paper` 不能消除流水电路的边界差异（evaluator_issues 2026-10-02 auditor E-003 条）：它只去掉数据比特的制备与读出，
灌入 / 排空层里数据比特的空闲噪声还在。gross code 12 轮、p=0.005、sd6 的 Z 基底 DEM Σ先验：IBM 60.22（noisy）→ 58.80（paper）→ 57.85（flat），
Strikis 62.02 → 60.62 → 58.28，即 paper 下 Strikis 仍多 3.1%，flat 下多 0.7%。

细节：`paper` 只去掉**数据比特**在其制备结束（含）之前、最终读出所在层（含）之后的噪声。**评估器 v2（auditor G1 L2-1）：
“制备结束”= 数据比特第一个双比特门之前的最后一个复位所在层**；复位之后的单比特门（含 `I`）与空闲照常带噪声（旧版把
“首个双比特门之前的复位 + 单比特门”整段算作制备，在第一个 CNOT 前插一个 `I` 就能把复位后的空闲噪声去掉，Σ先验 −2.4%）。
回归 `tests/test_g1_attacks.py::test_L2_1_*`。辅助比特的噪声一律保留，
包括第一轮前预先复位的辅助比特（IBM 调度第 0 层的 Z 辅助比特复位翻转）。auditor 的 paper1 变体把第 0 层整层的噪声都去掉了，
所以本实现每 shot 多 72 个复位翻转位置（相当于首轮的测量错误），影响很小。`noisy` 要求每个数据比特的制备恰好是一个
basis 基复位（R / RX），否则报错。

每轮换算：`per_round[P] = 1−(1−P)^(1/rounds)`（论文 §3），区间是对 LR 区间端点做单调变换；另附 sinter 公式
`(1−(1−2P)^(1/r))/2` 的点估计（P≥0.5 时为 None）。区间用 `stats.binomial_interval`（默认 LR=1000，≈3.72σ），
标签写明 LR 因子和 σ。任一 sector 失败数 < `MIN_LOGICAL_ERRORS_FOR_COMPARISON`（1000）时结果带警告。

### 7.2.1 `boundary="diff"`：两种轮数之差

```python
res = sample_l2(code, lambda b, r: make_circuit(b, r), data_qubits, p=0.005, rounds=12, boundary="diff",
                diff_rounds=4, diff_inner_boundary="paper", seed=..., stop=StopRule(...))
res.per_round["P_any"]          # {"best", "low", "high", "diff": {...}}：体内每轮错误率（分数）
res.rates                       # 较长那次（rounds=r2）的原始失败概率，只作参考
res.components["4"], ["12"]     # 两次子采样的完整 L2Result（种子 SeedSequence([seed, r, 0xD1FF])）
```

`circuits` 必须能给出两个轮数的电路：`callable(basis, rounds)` 或 `{r1: {"Z","X"}, r2: {...}}`。

**推导。** 设每轮的逻辑错误独立、以概率 ε 发生，发生时把失败事件涉及的 K 个 observable 的取值均匀打乱到 V−1 个非零类之一
（V = 2^K）；边界（初态、读出、灌入 / 排空）贡献一个与轮数无关的独立错误。对 GF(2)^K 上的随机游走取特征函数：每轮对任一非零
特征 χ 的期望是 1 − cε（c = V/(V−1)），边界是常数 B，且“没有失败”的概率 = 2^{−K} Σ_χ E[χ]，于是
`1 − c·P(r) = B·(1 − cε)^r`。取对数、两个轮数相减，B 消掉：

  Δ = log(1 − c·P(r2)) − log(1 − c·P(r1)) = (r2 − r1)·log(1 − cε)，  ε = (1 − exp(Δ/(r2 − r1)))/c。

- **k=1、单个 sector**：K=1，c=2，就是 `(log(1−2P(r2)) − log(1−2P(r1)))/(r2−r1) = log(1−2ε)`，在独立翻转模型下精确
  （与 sinter 的 `(1−(1−2P)^{1/r})/2` 同一模型）。
- **k>1**：一个 sector 的失败事件涉及 K=k 个 observable，P_any 涉及 K=2k 个。gross code（k=12）c = 1 + 2.4e-4（sector）/
  1 + 6e-8（P_any），实际上就是存活率之比 `ε = 1 − ((1−P2)/(1−P1))^{1/(r2−r1)}`，与论文的每轮定义 `1−(1−P)^{1/r}` 同一模型
  （只差边界因子 B）。均匀打乱是近似：真实的每轮错误集中在少数逻辑类上，“两轮错误恰好抵消”的概率与模型不同，偏差是
  O(ε·P) 量级；K 大时这个抵消本来就可忽略。所以对 k>1 用存活率形式，对 k=1 用 1−2P 形式，由 `num_observables` 自动选择。
- **前提**：r1 足够大，使两次运行的边界结构完全相同、且边界与体内的相关可以忽略（流水电路的灌入 / 排空层数与轮数无关：
  `unroll_schedule` 选的全局平移不依赖轮数）。建议 r1 ≥ 流水深度对应的轮数，并取 r2 − r1 尽量大（方差 ∝ 1/(r2−r1)²）。
- **置信区间**：两个独立二项样本，两个参数 (ε, B)，模型恰好饱和。对 B 取剖面似然，
  `{ε : max_B LL(ε, B) ≥ LL_max − ln F}`，F = `likelihood_factor`（默认 1000），按 Wilks（1 个感兴趣参数）对应 √(2 ln F) σ，
  与 `stats.py` 的约定一致。数值上与 delta 法吻合（100/1000 与 200/1000 时 95% 区间两端差 <5%），模拟 200 次的 95% 区间覆盖率
  在 0.90–0.99 之间（测试；独立的 300 次模拟为 95.3%）。**评估器 v2（auditor G1 L2-2）**：区间与 [0, ∞) 取交，low、high 分别
  截断到 0（原始值在 `diff.low_unclipped` / `diff.high_unclipped`），不再出现 low > high 的倒置区间；P(r2) < P(r1) 时点估计为负，
  `diff.valid = False` 并给出警告，pipeline 把它判为失败（`rejected_l2`），不给分。两个轮数的电路只能由评估器从同一调度生成
  （§9.2），候选无法单独操纵短轮数电路的边界。

**表面码验证**（d=3，sd6，p=0.005，pymatching，每个 sector ≥2000 次失败；`results/evaluator-fix-diff/surface_d3_p0.005.json`）：

| 口径 | P_Z 每轮 | P_X 每轮 |
|---|---|---|
| diff(3, 9) | 0.0185 [0.0163, 0.0208] | 0.0189 [0.0167, 0.0213] |
| diff(9, 27) | 0.0180 [0.0154, 0.0210] | 0.0184 [0.0157, 0.0214] |
| diff(6, 30) | 0.0176 [0.0155, 0.0201] | 0.0182 [0.0160, 0.0207] |
| paper 9 轮，单次，`(1−(1−2P)^{1/r})/2` | 0.0163 | 0.0162 |
| paper 27 轮，单次，同上 | 0.0178 | 0.0183 |
| paper 54 轮，单次，同上 | 0.0170 | 0.0188 |
| paper 9 / 27 / 54 / 90 轮，`1−(1−P)^{1/r}` | 0.0152 / 0.0137 / 0.0101 / 0.0071 | 0.0151 / 0.0140 / 0.0106 / 0.0074 |

（区间均为 LR=1000，≈3.72σ。）三组 diff 互相一致，并与 paper 口径长 memory（27、54 轮）的每轮错误率在误差内一致，满足
“同一电路上 diff 与 paper 的体内每轮错误率一致”。两个要注意的现象：(1) paper 9 轮的每轮值低 12–20%：paper 的完美初态 /
读出让首末轮比体内“轻”，单次运行的每轮值被边界稀释；(2) k=1 时论文公式 `1−(1−P)^{1/r}` 在 P 接近 0.5 时严重低估
（90 轮只剩 0.0071），因为它不考虑偶数次翻转抵消。这也是 diff 对 k=1 用 1−2P 形式的原因。
测试 `tests/test_l2.py::test_diff_boundary_agrees_with_paper_long_memory_on_surface_code` 用 diff(3, 9) 对 paper 27 轮做同样的比较。

**IBM vs Strikis（gross code，p=0.005）**：见 §7.2.2。

### 7.2.2 IBM vs Strikis 小规模对照（diff 口径，2026-10-02）

设置与 auditor E-003 §3 相同：gross code，sd6，p=0.005，BP-OSD IBM 参数（auditor 的解码器 A），X/Z 联合采样；
`boundary="diff"`，`diff_rounds=4`、`rounds=12`，`diff_inner_boundary="flat"`（所以 12 轮那次同时给出一个 flat 口径的单次结果），
StopRule(max_errors=100, min_sector_errors=100, batch_size=25)，seed 20261003，3 个 worker。
IBM 用 `baselines.circuit.memory_circuit`，Strikis 用 `pipelined_memory_circuit`（无噪声电路，噪声由评估器加）。
墙钟 IBM 1970 s、Strikis 1727 s，解码 CPU 合计约 10,000 s。脚本与结果：`results/evaluator-fix-diff/`
（`gross_{ibm,strikis}_diff4-12_flat_p0.005.json`、`ibm_vs_strikis_summary.json`）。

| | 4 轮失败 Z / X / any | 12 轮失败 Z / X / any | diff 体内每轮 P_any [LR=1000] | flat 12 轮单次每轮 P_any |
|---|---|---|---|---|
| IBM | 128 / 100 / 219 （7025 shot） | 104 / 108 / 185 （1075） | 0.0195 [0.0136, 0.0264] | 0.0156 |
| Strikis | 101 / 114 / 206 （3925） | 101 / 106 / 186 （1100） | 0.0163 [0.0103, 0.0232] | 0.0153 |

Strikis / IBM 比值（参数 bootstrap 95%，与 auditor 的区间同口径）：

| | diff（体内） | flat 12 轮单次 | auditor 拉平（trim，12 轮，600 shot/基底） |
|---|---|---|---|
| Z sector | 0.84 [0.58, 1.21] | 0.95 [0.72, 1.25] | 1.06 |
| X sector | 0.79 [0.54, 1.11] | 0.96 [0.73, 1.25] | 1.18 |
| P_any（真联合） | **0.84 [0.64, 1.10]** | 0.98 [0.80, 1.20] | — |
| X+Z 合并（独立近似） | 0.81 | 0.95 | **1.12 [0.87, 1.45]** |

读法：
- 三种拉平 / 去边界的口径都与 1 没有显著差异，区间互相重叠；与 auditor 的 1.12 [0.87, 1.45] 一致。E-003 未拉平时的 1.3 倍
  不出现。
- 边界效应直接可见：4 轮时 Strikis 的失败率是 IBM 的约 1.8 倍（P_any 5.2% 对 3.1%），12 轮时两者几乎相同。也就是说，
  Strikis 的额外失败主要集中在与轮数无关的边界上，diff 把它消掉后体内点估计反而略低于 IBM（0.84，不显著）。
- 每个 sector 只有约 100 次失败，diff 的比值区间约 ±30%，不足以区分 0.85 与 1.0。要下结论需要每点 ≥1000 次失败（stats.py
  约定），本次只是口径验证，**不是** H-003 的结论，也不上榜。
- 和 auditor 一样，p=0.005 下大部分失败是 BP-OSD 没找到最优解造成的（E-003 审计 §2），比值反映“电路 + 解码器”。

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
- `diff` 依赖“每轮独立、边界与轮数无关”的模型；解码器在短电路上的时间边界效应（例如 r1 小于解码器需要的时间窗）会被算进
  “边界”，只要两个轮数下边界相同就会消掉，但 r1 太小时这一前提不成立。代价是两次采样，且差分放大相对误差：每个 sector 各
  100 次失败时 ε 的相对误差约 ±20%（1σ 约 ±10%），比单次运行大得多。
- `diff` 的分数是体内每轮错误率，与 paper / noisy / flat 的“单次运行每轮值”不是同一个量，榜单上不能混排（`boundary_detail`
  记录了口径）。
- `flat` 只去掉数据比特的单比特噪声；流水电路首末轮 CNOT 之间的数据等待和辅助比特的灌入 / 排空噪声仍在，不是完全拉平。

## 8. 成绩单（`leaderboard.py`，评估器 v2）

**只有 `pipeline.evaluate` 能写成绩单。** 修复 auditor G1 LB1–LB7：

| 攻击 | v2 的处理 |
|---|---|
| LB1 `sample_l2(rounds=30)` 用在 3 轮电路上 | 结构性排除：候选不能给轮数；轮数来自任务，电路由评估器按该轮数生成，L0 实测每个生成元的测量次数并核对（`rounds_verified`），记录与 verify 都检查 |
| LB2 伪造 L0 / L2 字典 | `submit` / `build_entry` 删除（调用即 `PermissionError`）；私有 `_append` 只认 pipeline 的凭证对象；记录由 pipeline 自己组装；即使拿到凭证，`entry_problems` 也会拒绝不一致的记录（L0 未过、分数 ≠ 由计数重算的每轮值、失败数 < 1000、距离低于门槛……） |
| LB3 非打分噪声模型 | 任务只允许 `SCORING_MODELS = ("sd6",)`；记录的噪声必须等于任务的 |
| LB4 schedule_hash 与采样电路不符 | schedule_hash 由评估器对规范化调度计算；记录保存调度本身、每个轮数的电路哈希；verify 从调度重新生成电路核对，L2 的 candidate_hash 必须等于它 |
| LB5 删末行 / LB6 改后重算整条链 | 链本身发现不了（写明）。外部锚点：`anchor_line()` 写进 git commit message；`verify_leaderboard()` 对默认路径自动读 git 历史里的全部锚点，锚定过的第 N 行必须仍在且哈希不变 |
| LB7 不同 p / 解码器 / 码混榜 | 记录带 task_id + task_hash；p、噪声、解码器参数、停止规则、码哈希都必须等于任务；`table(task_id)` 只看一个任务 |
| L2-4 换种子挑结果、小样本 | 任务的停止规则要求每个 sector ≥ 1000 次失败，预算耗尽仍不足的结果 `insufficient_statistics`、不上榜；同一调度的重复提交记 `attempt`，`table` 只按第一次提交排名 |

```python
from evaluators import leaderboard as lb
lb.table("gross-sd6-p4e-3")                 # 一个任务的排名（同一调度只按第一次提交）
lb.verify_leaderboard()                     # 哈希链 + git 锚点 + 每条记录的语义核对（会重新生成电路），[] = 完整
lb.anchor_line()                            # 'leaderboard-anchor: lines=N head=<sha256>'，写进 commit message
lb.reproduce_entry(rec)                     # 按记录的 (task, code, schedule, seed) 重跑，L2 计数必须逐位相同（慢，抽查用）
```

记录字段：`candidate_id`、`task_id`、`task_hash`、`purpose`、`code`（规范化 spec、n、k、校验矩阵 sha256）、`schedule`
（规范化调度）、`schedule_hash`、`circuit_hashes`（轮数 → 两个基底无噪声电路的 sha256）、`rounds_verified`、`noise_model`、
`p`、`rounds`、`boundary`、`boundary_options`、`seed`、`l0`（每次 L0 的 passed / d_circ / 各项状态）、`distance_upper_bound`、
`score`（每轮 P_any 与每逻辑比特每轮值）、`l2`（完整 L2Result），以及系统字段 `seq`、`attempt`、`time`、`evaluator`
（哈希、是否冻结、是否与冻结清单一致）、`git`、`versions`、`prev_hash`、`entry_hash`。

写入规则：
- 只追加；`fcntl.flock` 排他锁内读末行取 `prev_hash`、`seq`，追加、fsync；末行不完整（不以换行结尾）则拒绝追加。
- 正式成绩单（默认路径）只接受 `purpose="score"` 的任务，且评估器必须**已冻结并与清单一致**；自检任务（`selftest-*`）永远
  不进正式成绩单。测试一律写临时路径（有测试检查正式文件前后不变）。
- 库版本必须等于 `tasks.PINNED_VERSIONS`，否则不写榜。

**外部锚点（PI / lead 的操作约定）**：每次有新成绩写进 `research/leaderboard.jsonl` 后提交 git，并在 commit message
里带上锚点：

```bash
uv run python -c "from evaluators.leaderboard import anchor_line; print(anchor_line())"
git add research/leaderboard.jsonl && git commit -m "leaderboard: <说明>

<上一条命令输出的 leaderboard-anchor: lines=N head=...>"
```

**防伪的边界**：凭证与语义核对挡住的是“绕过入口、拼字典”的误用和数字不一致的伪造；与评估器在同一进程里的恶意代码
仍可以构造计数自洽的假记录。这一层靠：搜索程序在沙箱里运行，只把调度 JSON 交给评估器进程；auditor 用 `reproduce_entry`
抽查（同一种子逐位复现）；git 锚点防事后改写。

## 9. 候选调度、评估入口与任务注册表（评估器 v2）

### 9.1 调度规范与模板（`candidate.py`）

候选**只提交调度，不提交电路**。JSON 规范（完整说明见 `candidate.py` 文件头）：

```json
{"format": "qec-schedule/v1", "period": 8,
 "x_checks": [{"prep": 0, "meas": 7, "cnots": [[data_col, t], ...]}, ...],   // 每个 HX 行一项（含冗余行）
 "z_checks": [{"prep": 7, "meas": 6, "cnots": [[data_col, t], ...]}, ...],   // 每个 HZ 行一项
 "name": "可选，不参与哈希"}
```

- 时间步是周期内的 0..D−1，**按周期循环解释**：从 prep 循环读，CNOT 必须严格在 prep 之后、meas 之前；窗口可以跨越周期边界
  （IBM 的 Z 校验、Strikis 的流水电路）。每个校验的窗口短于一个周期（一个辅助比特同一时刻只服务一个实例）。
- 能表达：IBM depth-8（`baselines.schedule.ibm_depth8` 转换，测试）、Strikis Fig. 12（跨周期流水，测试）、逐检查完全自由的
  调度（每个校验自己的 prep / CNOT / meas 时间与窗口长度，测试用 Steane 码）。转换器见 `tests/schedule_helpers.py:from_baseline`。
- 模板强制约束（违反即拒绝，逐条可读诊断）：每个周期内每个校验恰好一次“复位辅助比特 → 与其全部数据比特各一次 CNOT →
  测量”；cnots 的列集合 = 该行支撑；同一时间步每个比特至多一个操作；**所有行（含冗余行）每轮都测**（PI 对 L0-2 答复前）；
  数据比特只在第 0 层复位、最后单独一层读出；不允许任何其他字段（噪声、门、轮数、detector、observable、电路一律拒绝）。
- 电路生成（`memory_circuit(spec, code, basis, rounds)`）：比特布局、展开规则（与 `baselines.circuit.unroll_schedule` 相同，
  代码搬进评估器，评估器不 import baselines）、detector（basis 型：首轮、相邻轮、末轮与读出）、observable（评估器从
  HX/HZ 计算的 k 个逻辑算符）全部由评估器决定。噪声之后由 `noise.add_noise` 按任务加。
- **与 baselines 逐机制一致**（`tests/test_candidate.py`）：IBM 调度生成的电路加 sd6 后，DEM 与 `baselines.circuit.memory_circuit`
  （E-002 的电路生成器，噪声口径相同）逐机制相同（合并相同症状后最大概率差 < 1e-12；1、3 轮，两个基底）；Strikis 调度与
  `pipelined_memory_circuit`（E-003）同样逐机制相同。
- `ScheduleSpec.hash()`：规范化调度的 sha256（全局时间平移不改变生成的电路，取字典序最小的平移代表；name 不参与）。

### 9.2 评估入口（`pipeline.py`）

`evaluate(task_id, code_spec, schedule, *, seed=None, candidate_id=None, leaderboard_path=None, submit=True) -> Report`
（v2.1：正式任务忽略 seed、改用派生种子；没有 work_dir；电路由规范化调度生成；状态新增 `integrity_error`；另有
`screen(...)`，见 §0.1、§9.4）：

1. 取任务（导入时记录注册表哈希，运行时被改动的任务对象拒绝评估）；按任务码族把 `code_spec` 变成 `CSSCode`（fixed 码的任务传 None）。
2. 解析、校验调度 → 不合法：`rejected_schedule`，`Report.diagnostics` 逐条列出。
3. 评估器生成每个需要的轮数的两个基底电路：打分轮数（paper：`rounds`；diff：`diff_rounds` 与 `rounds`）与距离轮数
   （`l0.distance_rounds`；gross 12 轮算距离太慢，用 3 轮电路，同一调度同一模板）。
4. L0：每个打分轮数都过完整 L0（门集 {R, RX, M, MX, CX}、连接 = Tanner 图、比特数、轮数 = 该轮数），距离门槛在距离轮数的
   电路上检查；并核对 L0 实测的测量次数 = 轮数。任一不过：`rejected_l0`，附 L0 诊断。
5. 分层漏斗（`task.funnel.tiers`，见 §9.3）：每层一次小预算 paper 采样，不达标 `filtered`。
6. L2：任务的噪声、p、解码器、边界、停止规则、`seed`；diff 的两个子采样都用评估器生成的电路。diff 估计无效（负 / 饱和）：
   `rejected_l2`。否则 `scored`，`score.per_round_P_any`（{best, low, high}）与 `per_round_per_logical`（÷k，H-003 指标 B）。
7. 上榜资格：每个 sector（diff 时两次运行各自）≥ 1000 次失败，否则 `insufficient_statistics`；库版本一致；正式成绩单还要求
   评估器已冻结且完整、任务 `purpose="score"`。满足才由 pipeline 写入（§8）。

`Report.to_text()` 给出状态、诊断、每次 L0 的逐项结果、漏斗决定、分数和不上榜的原因，可直接喂给 LLM。
状态集合：`scored`、`rejected_code`、`rejected_schedule`、`rejected_l0`、`filtered`、`rejected_l2`、`insufficient_statistics`。
自检任务上的耗时（d=3 表面码，3 worker，机器满载时）：paper 约 18 s，diff 约 19 s。gross 任务（IBM / Strikis 调度）
L0（12 轮两个基底 + 3 轮距离门槛 10）加一个 50 shot 的 L2 约 7–7.5 分钟（3 worker，机器被 E-004 占满时；
慢测试 `tests/test_pipeline.py::test_gross_task_end_to_end_small_budget`，两者 d_circ 上界都 ≥ 10、实测轮数 12）。
正式 L2（每 sector ≥1000 次失败）的代价远大于此，这正是漏斗要解决的问题（§9.3）。

### 9.3 任务注册表（`tasks.py`）

`TASKS` 就是文件里的列表，随评估器冻结；没有运行时注册接口（新增 / 修改任务 = 修改 evaluators/ = 重新冻结）。
`Task.validate()` 在导入时检查：噪声 ∈ SCORING_MODELS（只有 sd6）、边界 ∈ {paper, diff}、`stop.min_sector_errors ≥ 1000`、
`num_workers ≤ 3`、`allow_redundant_row_omission` 为 False。

| task_id | 码 | 噪声 / p | 解码器 | 边界 / 轮数 | 停止规则 | L0 | 漏斗 |
|---|---|---|---|---|---|---|---|
| `gross-sd6-p4e-3` | gross [[144,12,12]]（固定，BB l=12 m=6 A=x³+y+y² B=y³+x+x²） | sd6 / 4e-3 | BP-OSD，IBM 参数 | paper / 12 | 每 sector ≥1000，max_shots 2e6，batch 25 | d_circ 上界 ≥ 10（3 轮电路，默认预算，暂定，待 PI 确认） | **待 E-004**（空） |
| `selftest-surface-d3-sd6-paper` | 旋转表面码 d=3 | sd6 / 5e-3 | pymatching | paper / 3 | 每 sector ≥1000 | ≥ 3 | 无 |
| `selftest-surface-d3-sd6-diff` | 同上 | 同上 | pymatching | diff 3→9（inner paper） | 每 sector ≥1000（两次运行各自） | ≥ 3 | 无 |

- 码族：`{"kind": "bb", "fixed": {...}}` 或 `{"kind": "bb", "constraints": {"max_n", "max_row_weight", "min_k"}}`
  （H-003 自由搜码时用；thickness ≤ 2 还没有在评估器里检查，见 §11），以及自检用的 `rotated_surface`。BB 码与
  `baselines/bb_code.py` 逐元素相同（测试）。
- **分层漏斗（留成配置，等 E-004）**：`funnel = {"status": ..., "tiers": [{"name", "stop": {StopRule 覆盖}, 
  "promote_if_per_round_P_any_below": 阈值 | None}, ...]}`。每层在打分轮数上做一次 paper 采样（种子由 seed 与层号派生），
  每轮 P_any 的区间下端 ≥ 阈值则 `filtered`；全部通过才做正式 L2。gross 任务目前 `tiers = []`（直接做正式 L2，代价很高：
  p=4e-3 下每 sector 1000 次失败约需 10⁵ shot × 数 CPU 秒）。E-004 给出代理指标的保真度后，由 lead 填层级与预算并重新冻结。

### 9.4 只评距离的任务（`kind="distance"`，评估器 v2.1，H-004）

| task_id | 码（出处） | IBM 项顺序调度的 d_circ 上界（本预算下复现） |
|---|---|---|
| `bb72-dcirc` | [[72,12,6]]，l=m=6，A=x³+y+y²，B=y³+x+x²（arXiv:2308.07915 Table 3） | 6 |
| `bb90-dcirc` | [[90,8,10]]，l=15,m=3，A=x⁹+y+y²，B=1+x²+x⁷（同上） | 8 |
| `bb108-dcirc` | [[108,8,10]]，l=9,m=6，A=x³+y+y²，B=y³+x+x²（同上） | 8 |
| `bb120-dcirc` | [[120,8,12]]，l=20,m=3，A=1+x³y²+x⁷y²，B=1+x¹⁶y+x⁹y（E-004 用的码，`search/proxy/candidates.py`；与 arXiv:2601.09911 的 [[120,8,12]] 是否等价**未核实**） | 10 |
| `cp126-dcirc` | coprime [[126,12,10]]，l=7,m=9，A=1+π+π⁵⁸，B=1+π¹³+π⁴¹，π=xy（arXiv:2408.10001 Table 2），写成 A=1+xy+x²y⁴，B=1+x⁶y⁴+x⁶y⁵ | 9 |
| `gross-dcirc` | [[144,12,12]]（arXiv:2308.07915 Table 3） | 10 |

（右列是本机用任务预算对 E-004 的 IBM 项顺序调度实测的值，见 `research/evaluator_issues.md` 2026-10-03 条；码的矩阵与
`search.codes.construct` 的构造逐元素相同，测试 `tests/test_distance_tasks.py`。码的构造逻辑在 `tasks.bb_matrices`，
评估器不 import search / baselines。）

- **约束**：每校验一个辅助比特、所有行每轮都测（模板结构）；`schedule_constraints={"max_period": 8}`（IBM 原电路的摊销深度）。
- **距离**：3 轮电路、两个基底、sd6 的故障位置（p 无关）；方法 graphlike + BP-OSD 随机 η + LNS；不早停。
  种子 = `derive_seed(task_hash, schedule_hash, "distance")`；调用方的 seed 被忽略。预算写死在任务里：
  n ≤ 126：`DCIRC_BUDGET` = BP-OSD 600 次 + 32 个 LNS 起点（CP-SAT 确定性时间 1.0）；gross：`DCIRC_BUDGET_GROSS` = 1500 + 96
  （与 L0 默认相同）。标定：在 IBM 调度上，n ≤ 126 的四个码各 3 个种子、BB120 9 个种子都复现已知上界（E-004 的低预算
  200 + 8 在 BB120 上只到 11，所以加大）；gross 2 个种子都是 10。单个候选的耗时见 `evaluator_issues.md` 2026-10-03 条。
- **分数**（越靠前越好）：`sort_key = [-d, w, D]`。d = 两个基底距离上界的较小值（经注入验证的见证）；
  w = **最小权重见证数**：在 d 达到最小值的基底里，固定预算搜索（BP-OSD 解 + LNS 终点）找到的**不同**的权重为 d 的
  DEM 逻辑错误（Dξ = 0、Lξ ≠ 0 的列集合；症状相同的机制合并成一列）的个数之和；见证来自其他方法而这里一个也没有时记 1。
  它只取决于派生种子与预算，是“低权重逻辑错误有多少”的可复现代理，不是精确计数。D = 调度周期（摊销深度）。
- **Report.distance**：每个基底的权重、方法、最小权重见证数、权重直方图、最短见证的原始故障与**调度坐标**：
  `candidate.describe_faults(spec, code, rounds, faults)` 把每个故障翻译成 cycle / step（step 就是调度 JSON 的周期内时间步）、
  模板操作（cnot / reset / measure / idle / data_reset / readout）、校验（`X#i` / `Z#i`）与它的第几轮实例、数据列、各比特上的 Pauli。
  `Report.to_text()` 列出这些行，例如 `cycle 1 step 2 (layer 12): CNOT of X#16 (round 1) with data col 49: DEPOLARIZE2 -> Z on data col 49`。
  L2 任务的 L0 距离结果也带同样的翻译。
- **成绩单**：与 L2 任务同一个文件，按 task_id 分开排名（`table(task_id)` 按 sort_key）。记录带 `distance_params`（= 任务
  预算）、每个基底的最短见证（原始故障 + 调度坐标）、最小权重见证数。`entry_problems` 从调度重新生成电路，把每个见证
  **重新注入验证**，并核对 d = 两个见证权重的较小值、w、sort_key、派生种子、预算；声称的距离偏大（藏起更短的见证）只能靠
  `reproduce_entry`（同一种子复算，逐个比较见证）发现。正式榜规则与 L2 任务相同（冻结、purpose=score）。
- **`screen(task_id, code_spec, schedule)`**：调度校验 + L0（含任务的距离预算），不跑漏斗与 L2，永不写榜，状态 `screened`。
  距离任务上与 `evaluate` 的距离分数完全相同（同一派生种子与预算）。给搜索程序的内循环用。
- 局限：距离仍只是上界；3 轮电路；w 依赖搜索预算；`max_period` 只限制周期，不限制辅助比特窗口长度。

## 10. 冻结流程（PI 执行；agent 不得执行 freeze）

`scripts/freeze_evaluator.py`（修复 auditor G1 F3–F6）：
- 哈希范围：evaluators/ 下**全部文件**（任何扩展名）+ `scripts/freeze_evaluator.py` + `.claude/hooks/guard_frozen.py` +
  `pyproject.toml` + `uv.lock` + 评估器测试（`EXTRA_FILES`：`tests/test_{l0,l2,noise,distance,leaderboard,stats,codes,candidate,pipeline,g1_attacks,freeze,decoder_eval}.py`、
  `tests/{conftest,memory_builder,schedule_helpers}.py`）。`uv run python scripts/freeze_evaluator.py list` 列出全部。
- 清单外出现的任何文件 = 篡改；`.so` / `.pyd` / `.dylib`、符号链接、`__pycache__` 里的非 .pyc 文件一律拒绝；
  `__pycache__/*.pyc` 只有在“与对应受保护源文件重新编译的代码对象逐项相等”时才允许（伪造 pyc 头部的 mtime / size 无用）。
  有这些文件时 `freeze` 拒绝执行。
- 关键库固定到 `==`（pyproject.toml：stim 1.16.0、sinter 1.16.0、ldpc 2.4.1、pymatching 2.4.0、numpy 2.2.6、scipy 1.18.1、
  ortools 9.15.6755、python-sat 1.9.dev15），与 `tasks.PINNED_VERSIONS` 一致（测试），pipeline 写榜前核对已安装版本。
- `freeze` 写 `evaluators/MANIFEST.sha256`、`evaluators/FROZEN`，并在 evaluators/ 之外写 `research/evaluator_freeze.sha256`
  （`shasum -a 256 -c` 格式）与 `research/evaluator_freeze.json`（哈希、文件数、时间、库版本）。`verify` 核对四者一致。
- hook（`.claude/hooks/guard_frozen.py`，F1）：路径解析符号链接后**大小写不敏感**比较；冻结后禁止编辑 evaluators/ 与清单里的
  全部文件，硬链接也拒绝；成绩单与冻结记录永远不能由 agent 编辑。hook 只拦截 Edit / Write / NotebookEdit，Bash 写不经过它（F2）。

**PI 冻结时执行的命令**（agent 不执行；按顺序）：

```bash
cd /Users/ephemeral/Desktop/qec-ai-search
find evaluators -name __pycache__ -type d -prune -exec rm -r {} +     # 清掉字节码缓存（可选；verify 会核对它们）
uv sync --locked                                                      # 环境与 uv.lock 一致
uv run pytest tests -q                                                # 全部测试通过
uv run python scripts/freeze_evaluator.py freeze
git add evaluators/FROZEN evaluators/MANIFEST.sha256 research/evaluator_freeze.sha256 research/evaluator_freeze.json
git commit -m "冻结评估器 <evaluator_hash>"
git tag evaluator-frozen-<evaluator_hash>                             # 外部锚点（可选）
chmod -R a-w evaluators                                               # 文件系统层面锁定（Python 也无法再写 __pycache__）
chflags -R uchg evaluators                                            # macOS：用户不可变标志（解锁：chflags -R nouchg evaluators）
```

之后每次实验前：`uv run python scripts/freeze_evaluator.py verify`；独立于本脚本的校验：
`shasum -a 256 -c research/evaluator_freeze.sha256`，再用 `git diff evaluator-frozen-<hash> -- research/evaluator_freeze.*`
确认冻结记录没被改；清单外新文件：`comm -13 <(cut -d' ' -f3- research/evaluator_freeze.sha256 | grep '^evaluators/' | sort) <(find evaluators -type f ! -path '*/__pycache__/*' ! -name FROZEN ! -name MANIFEST.sha256 | sort)`。
建议（需改 `.claude/settings.json`，本次未改）：给 Bash 加一个 PreToolUse hook，拒绝提到 `evaluators/`、`leaderboard.jsonl` 的写命令
（只能减少误操作，挡不住故意绕过）；并考虑把 `.claude/settings.json` 也纳入冻结清单（它决定 hook 是否生效）。

## 11. 已知局限（评估器 v2）

- 能改评估器的人也能改冻结脚本，脚本自报“完整”不是证明；外部锚点是 git 里的 `research/evaluator_freeze.*`、git tag 与
  `shasum -c`，以及文件系统锁。
- 写榜凭证只防误用；同进程恶意代码可伪造计数自洽的记录，需沙箱 + `reproduce_entry` 抽查 + git 锚点（§8）。
- 哈希链本身挡不住删末行与整链重算，需要每次写榜后把锚点写进 commit message（§8）；`verify_leaderboard` 只能核对已有锚点之前的部分。
- 同一调度换种子重交只记 attempt、按第一次排名；但候选可以对调度做无关紧要的改动（不同的哈希）来“重抽”。每 sector ≥1000 次
  失败时单次抽样的相对误差约 ±3–6%，这一操纵的收益有限，但没有被完全排除。
- 距离仍只是上界（§3.1），且 gross 任务在 3 轮电路上算距离（12 轮太慢）；门槛 10 是暂定值。
- 码族约束只实现了 n、行重、k；H-003 的 thickness ≤ 2 没有在评估器里检查（`search/codes/constraints.py` 有实现，未搬进来）。
- si1000 不能用于打分（N2 未修，CX→CZ+H 编译约定未定）。
- L0-2（冗余行可否不测）等 PI 裁决；在此之前模板要求每行每轮都测。
- 漏斗层级与预算等 E-004。
- `__pycache__` 校验依赖“同一 Python 版本重新编译得到相等的代码对象”；版本不同或源文件改过会报错（偏保守：删掉 __pycache__ 即可）。
- 底层 `check_l0` / `sample_l2` 仍接受任意电路（诊断用）；它们的结果不能上榜。原始电路上 L0 的已知局限见 §5。

## 12. 解码器任务（`kind="decoder"`，H-005，2026-10-03）

```python
from evaluators.decoder_eval import evaluate_decoder, reference_report, near_optimal_gap
rep = evaluate_decoder("bb72-dec-p3e-3", program_src, split="search")    # 搜索集：固定 shot，永不写榜
print(rep.to_text())                                                    # 诊断（可直接给 LLM）
rep = evaluate_decoder("bb72-dec-p3e-3", program_src, split="holdout")  # 留出集：按停止规则采样，满足条件时写榜
reference_report("bb72-dec-p3e-3", split="search")                      # 主参考 + 次要参考，同一套沙箱与计时
near_optimal_gap("bb72-dec-p3e-3", split="public", shots=200)           # CP-SAT MLE 小样本差距（不打分）
uv run python -m evaluators.decoder_eval init-secret                    # PI：在 repo 外生成密钥（一次）
```

文件：`decoder_problem.py`（电路、解码问题、密钥与种子、采样）、`decoder_sandbox.py` + `_decoder_runner.py`（沙箱会话，
从 `search/llm_evolve/sandbox.py` 复制并扩展，评估器不依赖 search/）、`decoder_eval.py`（入口、速度预算、报告、写榜）、
`decoder_refs.py`（参考解码器程序）、`decoder_mp.py`（mp_rule 白名单与引擎）、`decoder_mle.py`（近最优参考接口）。
测试：`tests/test_decoder_eval.py`（约 10 分钟，单 worker；在冻结清单 EXTRA_FILES 里）。

### 12.1 任务

| task_id | 码 | 电路 | 接口 | 主参考（速度基准） | 次要参考 |
|---|---|---|---|---|---|
| `bb72-dec-p3e-3` | [[72,12,6]]（arXiv:2308.07915 Table 3） | IBM depth-8，sd6，p=3e-3，6 轮，paper 边界 | program | Relay-BP（论文参数） | BP-OSD（E-002 设置）、BP+LSD |
| `bb90-dec-p3e-3` | [[90,8,10]]（同上） | 同上，10 轮 | program | 同上 | 同上 |
| `bb72-mp-p3e-3` | [[72,12,6]] | 同 bb72 | mp_rule（总迭代 ≤ 500） | 引擎里的 Relay 规则 | 官方 Relay-BP（只作对照） |
| `selftest-surface-d5-dec` | 旋转表面码 d=5 | stim 标准 CNOT 顺序，sd6，p=5e-3，5 轮 | program | Relay-BP | pymatching |

- 解码器相关设置全部放在已有的 `decoder` 映射里（interface、schedule、reference、secondary_references、speed、search、
  near_optimal、mp），Task 没有加字段，**已有 9 个任务的哈希不变**（测试 `test_existing_task_hashes_unchanged`）。
- 电路由评估器生成：IBM 调度（`decoder_problem.ibm_schedule`，与 `baselines/schedule.py:ibm_depth8` 规范化哈希相同，测试）、
  模板 `candidate.memory_circuit`、`l2.build_joint_circuit`（X/Z 联合采样，paper 边界）。每个 sector 的解码问题 = 联合 DEM
  限制到该 sector、合并相同症状后有症状的机制（与 l2 的 BP-OSD 路径相同）：BB72 每个 sector 252 个 detector × 2232 个机制。
- Relay-BP 参数（arXiv:2506.01779，Relay-BP-5、XZ 解码；对照官方包 relay-bp 0.2.2 的签名与 README 核实）：min-sum、
  `alpha=None`（无缩放）、`gamma0=0.125`、`pre_iter=80`、`num_sets=300`（加上第 0 段共 301 段）、`set_max_iter=60`、
  `gamma_dist_interval=(-0.24, 0.66)`、`stop_nconv=5`、`seed=0`。包的默认值不同（gamma0=0.1、stop_nconv=1）。
  **注意**：官方实现的 γ 抽样 RNG 在同一个解码器对象的连续调用之间延续，所以结果依赖 shot 的处理顺序（同一 worker
  划分下可复现；不同 worker 数会差几个 shot）。
- 停止规则（holdout）：每个 sector ≥ 1000 次失败且 P_any ≥ 1000，或 max_shots = 5e6；batch 1000。search：BB72 20000 shot、
  BB90 10000 shot、mp 4000、自检 2000（`decoder.search`），调用方可以取更小的前缀。

### 12.2 候选接口

- **program**：完整程序，定义 `make_decoder(H, L, priors, info) -> decode`，`decode(syndrome) -> k 个 observable 比特`。
  H：`scipy.sparse.csc_matrix`（uint8，num_det × M），L：`csr_matrix`（k × M），priors：float64（M,），info：sector、轮数、p、
  detector 坐标（[校验行, 轮, 类型]）、码的校验支撑（**不含任何种子**）。输出必须是长度 k、元素为 0/1 或 True/False 的
  序列（numpy 数组会被转成列表）；其他一律格式错误、按失败计（`validate_output`）。“BP + 后处理”只是
  `search/llm_evolve/decoder_problem.py` 里给 LLM 的模板，评估器始终接收完整程序。
- **mp_rule**：候选只交 `SCHEDULE`、`check_rule(m, sgn)`、`var_rule(prior, inc, gamma, prev)`；AST 白名单只允许局部名字
  赋值、return、数字常量、算术与比较、`np.<白名单>`（逐元素函数；按行归约必须写 `axis=1, keepdims=True`）——没有下标、
  属性、循环、字符串、import（除 `import numpy as np`），所以每个输出行只依赖同一行输入（局部性由构造保证）。
  评估器把规则包进自己的引擎（`decoder_mp.ENGINE_TEMPLATE`）成为完整程序再进沙箱；引擎负责段（leg）、γ 抽样（种子由
  syndrome 派生）、收敛判定、选最低权重解，并**强制每 shot 总迭代 ≤ `mp.max_total_iters`**（测试：永不收敛的规则恰好
  跑 500 次）。规则在执行时看到的 `np` 是只含白名单函数的命名空间，`__builtins__` 为空。

### 12.3 评估流程与速度预算

1. 按任务生成电路与两个 sector 的问题；由密钥派生 split 的根种子（§12.4），第 b 批用 `SeedSequence([root, b])` 在父进程里采样。
2. 每轮取 W = `num_workers`（≤ 3）个批：先在这些批上跑**主参考**（与候选同一种沙箱会话、同一计时），再跑候选。
   每个 worker 每个 sector 一个子进程（会话跨批复用，崩溃 / 被杀后重启，重启 > 3 次则该 sector 判死）；**跑 Z sector 时所有
   X 子进程被 SIGSTOP 暂停，反之亦然**（测试 `test_sectors_never_run_concurrently...`），shot 逐个发送。
3. 计时：父进程用 psutil 读子进程累计 CPU（user+system，所有线程）；第 i 个 shot 记“上一个回复到这一个回复之间”的 CPU，
   后台线程在 shot 之间做的功也算进去（测试 `test_background_thread_work_is_charged`）。
4. 每个 sector 每个 shot 的上限：`cap_i = K × max(参考在 shot i 上的 CPU, 参考在该批上的平均 CPU, min_shot_cap_s)`；
   CPU 超过 cap_i 的 shot 记超时（失败）；墙钟超过 `min(shot_wall_s, 4·cap_i + 0.5 s)` 立即杀掉（失败、会话重启）。
   每批总预算 `K × 参考在该批上的总 CPU`：按 shot 顺序累计，超出后本批剩余 shot 不再运行、全部记失败。构建（make_decoder）
   CPU 超过 `build_cpu_s` 则该 sector 判死（status `rejected`）。BB 任务 K=2、min_shot_cap_s=2 ms、shot_wall_s=30 s、
   build_cpu_s=120 s；mp 任务 K=3。
5. 分数：P_any = 同一 shot X 或 Z 任一 sector 失败（错、超时、超预算、异常、格式错误、没运行）的比例，LR=1000 区间，另给每轮换算
   `1-(1-P)^(1/rounds)`；次级指标：平均 CPU / shot 及与参考之比。报告分解每类失败、参考在同一批 shot 上的计数与速度、
   与参考失败的重叠（双方都错 / 只有候选错 / 只有参考错），search 另给失败 shot 的特征（syndrome 权重分布、按轮次的
   detector 触发比例、按权重分箱的“只有候选错”）。
6. 上榜：只有 `split="holdout"`、`purpose="score"`、每个 sector ≥ 1000 次失败、候选在 OS 级沙箱下运行；正式成绩单还要求评估器
   已冻结（与 L2 任务相同的 `_append` 守卫，凭证仍是 pipeline 的）。记录 `kind="decoder"`，含程序源码与哈希（同一程序重复提交
   记 attempt，按第一次排名）、电路哈希、种子承诺（sha256 of 根种子，不是种子本身）、计数、分解、参考计数与速度。
   `entry_problems` 的解码器分支核对：任务参数、split=holdout、程序哈希、电路哈希（重新生成）、种子承诺（有密钥时）、计数
   自洽、≥1000、分数可由计数重算、参考名与参数、OS 沙箱。`table(task_id)` 按 P_any 升序、再按 CPU 排名。
   `reproduce_entry` 对解码器记录重跑同一留出集，只要求 P_any 落在记录的区间内（超时判定依赖负载，不能逐位复现）。

### 12.4 保密种子

密钥文件默认 `~/.config/qec-ai-search/decoder_secret.key`（`QEC_DECODER_SECRET_FILE` 可改；测试用临时文件），64 个十六进制字符，
必须 0600，且不能在 worktree 或主目录里（`SecretError`）。`root(split) = HMAC-SHA256(secret, "qec-decoder-shots|task|task_hash|split")`；
search 与 holdout 都需要密钥，搜索程序（LLM）永远只看到 search 的诊断；自检任务另有 `public` split（公开常量派生）。
报告与记录里只有种子承诺；测试检查报告 JSON / 文本里不出现根种子、批种子和密钥。

### 12.5 攻击与防护（每项都有测试，`tests/test_decoder_eval.py`）

| 攻击 | 防护 | 测试 |
|---|---|---|
| 沙箱里读评估器源码 / **主目录**（从 worktree 运行时）/ 家目录 / 密钥文件 | 两层：macOS `sandbox-exec`（SBPL：拒绝读家目录、所有项目根目录（`project_roots()` 由 `.git` 文件解析出主目录）、系统临时目录与密钥，只放行 venv、本会话工作目录和执行器脚本本身）+ audit hook（同样的路径规则） | `test_sandbox_attack_blocked[*-read_*]`，两层都开 / 只有 audit hook 各跑一遍；`test_os_sandbox_profile_blocks_independently_of_python`（`/bin/cat` 在同一配置下也读不到） |
| 跨 sector 信息泄露 | 每个 sector 一个子进程，只拿到本 sector 的 H/L/priors/info/syndrome；两个 sector 的进程**从不同时运行**（另一侧 SIGSTOP）；持久化信道全部堵住：工作目录外不可写（sandbox + hook）、不能列 / 读临时目录（看不到别的会话的工作目录）、POSIX/SysV 共享内存与信号量被 sandbox 禁止、`_posixshmem` / `multiprocessing` / `mmap` 不能 import、`os.mkfifo` / `mknod` 从 os 与 posix 模块里删除（没有 audit 事件）、不能发信号 / 查其他进程信息 | `list_temp_root_for_other_sector`、`write_outside_workdir`、`symlink_outside`、`mkfifo_channel`、`shared_memory`、`posixshmem`、`mmap`、`signal_parent`；`test_sectors_never_run_concurrently_and_see_only_their_own_data` |
| 从 syndrome 统计反推种子 / 预测噪声 | 种子 = HMAC(256 位密钥)，每批独立派生；候选只看到本 sector 的 syndrome，看不到任何 RNG 输出；stim 的采样在父进程。理论上从大量 syndrome 恢复某一批 stim 内部 PRNG 状态（非线性的 Bernoulli 跳跃采样，并且只有一半 detector）不可行，写为已知局限 | `test_candidate_randomness_cannot_guess_observables` |
| numpy 全局随机状态 | 父进程采样只用 `compile_detector_sampler(seed=…)`，与 numpy / random 的全局状态无关；候选进程里的全局状态与父进程无关 | `test_numpy_global_random_state_does_not_affect_sampling` |
| 缓存与侧信道（跨评估记住 holdout、读 /proc 类信息） | 每次评估全新 0700 工作目录、结束删除；不能写其他地方；psutil / ctypes / socket / subprocess 不能 import 或调用（预导入后从 sys.modules 删除名字，`import` 触发 audit 事件被拒；ctypes 的 dlopen / call 也被 audit 拒）；环境变量白名单 | `import_psutil`、`import_ctypes`、`ctypes_via_sys_modules`、`ctypes_dlopen_via_numpy`、`socket`、`subprocess`、`os_system`、`fork`、`import_evaluator`、`env_secret`、`raise_rlimit` |
| 对搜索集过拟合 | 排名只用留出集（另一个 HMAC 派生的根种子）；搜索集诊断只有聚合统计 | `test_search_set_memorisation_does_not_transfer_to_holdout`（内嵌搜索集全部答案的“解码器”：搜索集近乎满分，留出集远差于参考） |
| 输出格式攻击（长度、2、浮点、字符串、嵌套、dict、None、超长回复） | 父进程严格校验；超过 1 MiB 的回复是协议错误（会话被杀）；都按失败计 | `test_output_format_attacks_count_as_failures`（9 种）、`test_huge_output_is_protocol_error_and_fails`、`test_validate_output_strict` |
| 伪造协议行（往原始 stdout 的 fd 写“答案”） | 每个回复必须带父进程发的 shot id，且一次只发一个 shot：答案只能在看到 syndrome 之后给出；id 不符 = 协议错误、shot 失败 | `test_forged_reply_lines_on_raw_stdout_fail` |
| 超时操纵（睡眠、CPU 爆发、shot 之间偷算、构建期偷算、拖慢参考） | 见 §12.3：墙钟杀进程、CPU 上限、累计计时、批预算、构建预算；参考与候选分开运行，参考计的是 CPU 时间（对负载不敏感），候选进程在参考运行时不存在或处于暂停 | `test_wall_clock_timeout_kills_and_counts_as_failure`、`test_cpu_over_cap_counts_as_timeout`、`test_background_thread_work_is_charged`、`test_build_budget_enforced`、`test_exceptions_count_as_failures` |
| 伪造成绩单记录 | 解码器分支的语义核对（§12.3 第 6 条）；只有 holdout 能写；正式成绩单需冻结 | `test_decoder_record_semantic_checks`、`test_search_split_never_written`、`test_official_leaderboard_unchanged` |
| mp_rule 越权（属性逃逸、全局归约、下标、axis=0、import、循环、字符串、lambda、改绑 np）、超迭代 | AST 白名单 + 受限命名空间 + 引擎强制上限 | `test_mp_rule_whitelist_rejects`（13 种）、`test_mp_engine_enforces_iteration_cap`、`test_mp_task_rejects_full_programs_as_rules` |
| 参考用错 | Relay-BP 候选 = 直接调官方包（逐 shot 相同）；表面码上 pymatching 候选 = 直接 pymatching | `test_relay_candidate_matches_official_package_and_reference`、`test_pymatching_candidate_matches_direct_pymatching`、`test_mp_engine_relay_close_to_official_relay` |

### 12.6 已知局限

- **沙箱不是虚拟机**：sandbox-exec 已被 Apple 标为废弃，但 macOS 15 上可用；非 macOS 只有 audit hook（可被 C 扩展绕过）。
  候选可以加载 venv 里的任何已编译库（numpy、scipy、ldpc、relay_bp、pymatching、stim……）；一个有内存破坏漏洞的库调用可以
  绕过 audit hook，但仍在 sandbox-exec 的限制内。
- **计时**：CPU 时间受机器负载（缓存、频率）影响，个别临界 shot 的超时判定会抖动，所以分数不能逐位复现，只能统计复现。
  参考与候选在同一时间段、同一机器上测量，以减小偏差。多线程候选的 CPU 时间按总和计（不会因并行而占便宜）。
- **Relay-BP 的 RNG 顺序依赖**：官方包在同一解码器对象的连续调用之间延续 RNG，结果依赖 worker 划分（同一划分下可复现）。
- **速度预算以 Relay-BP 为基准**：BP-OSD 这类重尾解码器在预算内会损失很多 shot（见 §12.7），这是设计（目标是 FPGA 友好的
  解码器），不是 bug；报告里分开给出“错”和“超预算”。
- 留出集只有一个；同一程序的重复提交按第一次排名，但对程序做无关紧要的改动可以“重抽”（与 L2 任务相同的局限，每 sector
  ≥1000 次失败时收益有限）。
- 近最优参考是 MLE（不是对简并求和的 ML），只在小样本上用；CP-SAT 在时间上限内没证明最优时单独计数。
- mp_rule：引擎的 Relay 规则与官方包不是逐位相同（段间消息是否重置、γ 抽样方式不同），只是同量级；mp 任务的速度预算以
  引擎里的 Relay 为基准（Python/numpy，比 Rust 慢约 5 倍），迭代上限才是主要约束。

### 12.7 参考解码器实测（在评估器里、与候选同样的沙箱和计时）

__MEASUREMENTS__
