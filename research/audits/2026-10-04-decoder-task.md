# Auditor red-team: decoder evaluation task (H-005), 2026-10-04

**对象**：刚合并进 main 的解码器评估任务（commit 9756441，H-005）。评估器给 LLM 写出的可执行解码程序打分。
**审计员**：auditor 子 agent（独立于实现者）。
**立场**：默认评估器可被钻漏洞，直到推不翻。
**结论**：**READY-WITH-CONDITIONS**（见下方"冻结前必须处理"；均为低危/文档类，非安全漏洞）。

脚本：`research/audits/2026-10-04-decoder-task-scripts/`（`drive.py` = 候选程序驱动器；`atk_*.py` = 攻击候选；`cand_pymatching.py` = 合法基准）。
临时测试密钥：`$SCRATCH/decoder_test_secret.key`（repo 外，0600，审计结束时删除，**不是** PI 的正式密钥）。
预算：约 1.4 CPU 小时（≤3 workers）。未改动 `evaluators/`、`tests/`；未 git commit；`research/leaderboard.jsonl` 全程为空（sha `da39a3e…`，0 行）未变；未干扰 E-007（其解码评估子进程 pid 全程独立运行）。

---

## 1. 总体判断

**评估器在根本上是稳健的**，核心结论：

- **答案与种子没有泄露面**。候选每个 shot 只拿到本 sector 的 syndrome；truth（observable）与 stim 种子只在父进程，从不发给子进程；候选无法读父进程内存（无 ptrace、`process-info others` 拒绝、无法发信号）。因此**要拿高分只能真正解码**，没有信息论捷径。这是最重要的结论。
- 两层沙箱（macOS `sandbox-exec` + Python audit hook）挡住了实现者列出的全部 23 类攻击，我另跑了若干新攻击也都被挡。
- 速度预算（per-shot cap + 每批总预算，以 Relay-BP 为基准）正确计入候选的所有 CPU（含 BLAS、子线程、内核时间），"把慢而准的解码器混进来"会被预算判失败。
- mp_rule 白名单很紧，跨行取数据在构造上和运行时都不可能。
- Relay-BP 用法与官方包 relay-bp 0.2.2 **逐 shot 相同**，参数符合论文；CP-SAT MLE 是**正确的精确最小权重解码器**（与暴力穷举一致、全部证明最优）。

没有发现任何能让候选作弊拿分或伪造成绩单记录的攻击。所列"条件"都是低危信息泄露 / 健壮性 / 文档问题。

---

## 2. 攻击清单

### 2.1 失败的攻击（防护成立）—— 均亲自写候选程序跑过

| 攻击 | 结果 | 证据 |
|---|---|---|
| 读密钥 / 评估器源码 / 家目录 / 主 checkout（内容） | **BLOCKED**（两层） | `tests/test_decoder_eval.py::test_sandbox_attack_blocked` 46 项全过；`atk_metadata.py` 内容读全部 PermissionError |
| 跨 sector 信道：写工作目录外、symlink、mkfifo、POSIX/SysV 共享内存、`_posixshmem`、mmap、列临时根目录 | **BLOCKED** | 测试 11 项全过 |
| SIGSTOP 绕过：自己装 SIGCONT handler + 给兄弟/父进程发信号 | **无效**：handler 能装但没用（SIGSTOP 不可捕获、被暂停时冻结），`os.kill` 被拒，发不出信号 | `atk_sigcont.py` → `['handler_installed', 'kill_blocked:PermissionError']` |
| 藏 CPU：每 shot 做 900×900 BLAS 矩阵乘，指望 psutil 不计 | **全额计入**：4 ms/shot vs 参考 0.3 ms，ratio 13×，per-shot cap + 批预算把它判成 **P_any=1.0**（195 超上限 + 303 超批预算 / sector） | `atk_blas_hide.py` |
| 后台线程"偷算" | 计入下一个 shot | `test_background_thread_work_is_charged` 过 |
| mp_rule 越权：axis=0、cumsum 无 axis、take_along_axis axis=0、下标、属性、改绑 np、循环、lambda、字符串、walrus、变量 k 的 rowkth / full_like | 全部 **reject** | 我另写 14 个新 bypass，`validate_rules` 全拒；合法 min-sum 规则通过 |
| import psutil/ctypes/socket/subprocess、os.system、fork、改 rlimit、ctypes via numpy | **BLOCKED** | 测试全过 |
| 输出格式攻击、>1MiB 回复、往 raw stdout 伪造协议行 | 失败 / 协议错误 | 测试全过 |
| 背诵搜索集 | 不迁移到留出集 | `test_search_set_memorisation_does_not_transfer_to_holdout` 过 |

跨 sector 泄露即便成功也只是让 X 解码器看到同一 shot 的 Z syndrome（sd6 下 Y 错误使两基相关，理论上能略微提升精度，是对参考不公平的增益）——但 SIGSTOP + 无 IPC + 独立工作目录把它彻底堵死，两 sector 进程从不同时运行（`test_sectors_never_run_concurrently` 过）。

### 2.2 发现的问题（都不是拿分 / 伪造记录的漏洞）

1. **`(allow file-read-metadata)` 全局放行** —— 候选可以 `os.stat` 密钥文件（得到 size=65、mode=0600）、`evaluators/tasks.py`（size、mode）、家目录（mode 0700）；**内容读全部被拒**。危害低：密钥长度固定、无内容泄露；但这是一个真实的元数据侧信道（文件存在性、大小、mtime 对所有项目文件可见）。根因是 SBPL 用了 `(allow default)` 再逐条 deny，stat/realpath 需要路径元数据。复现：`atk_metadata.py`。

2. **`CpSatMLE._prep` 用 `id(problem)` 做缓存键** —— 若调用方传入**临时** problem 对象，Python 的 id 回收会让缓存返回**上一个问题的** H/w/L，于是 CP-SAT 在错误的约束上求解并**照样报 OPTIMAL**（静默给错 MLE）。我第一版暴力穷举对比就因此出现 3 个假"mismatch"，保持对象存活后归零。评估器现用法安全（`near_optimal_gap` 持有 `inst.sectors[*]` 稳定），但这是给未来接入方（E-006 的 `search/decoders` MLE 适配器）埋的静默错误。复现：见 §3.2。

---

## 3. 用法与数据核查

### 3.1 Relay-BP 用法：**正确**

- 安装版本 relay-bp **0.2.2**（与 README 一致）。官方签名：
  `RelayDecoderF64(check_matrix, error_priors, alpha=None, alpha_iteration_scaling_factor=1.0, gamma0=0.1, …, pre_iter=80, num_sets=300, set_max_iter=60, gamma_dist_interval=…, stop_nconv=1, …, seed=0)`。
- 参考程序（`decoder_refs.RELAY_TEMPLATE`）传 `alpha=None`（= min-sum 无缩放，符合论文）、`gamma0=0.125`、`pre_iter=80`、`num_sets=300`、`set_max_iter=60`、`gamma_dist_interval=(-0.24,0.66)`、`stop_nconv=5`、`seed=0`，与包默认（0.1 / 1）不同处正是论文取值。`ObservableDecoderRunner(dec, L.tocsc(), include_decode_result=False)` + `decode_observables` 用法与包 README 一致。
- **候选 = 参考（同一 relay 程序）在表面码上与官方包逐 shot 相同**：`test_relay_candidate_matches_official_package_and_reference` 通过。mp 引擎里的 Relay 规则与官方包同量级（`test_mp_engine_relay_close_to_official_relay` 通过）。
- 已知局限（官方包 γ 的 RNG 在同一对象连续调用间延续 → 结果依赖 worker 划分）属实且已写入 §12.6。

### 3.2 MLE 结论：建模**正确**，量级结论**可信**（具体倍数未在预算内全量重跑）

- CP-SAT 建模：`min Σ round(1000·w_j)·x_j s.t. Σ_{j∈row i} x_j − 2 t_i = s_i, x_j∈{0,1}, t_i∈[0,⌊deg/2⌋]`，`w_j=log((1−p_j)/p_j)`。这是**精确整数**求解（不是线性松弛——所有算例均 `OPTIMAL` 证明），奇偶约束与变量定义正确。
- **与暴力穷举对比**（60 个随机小问题，nd∈[4,8), M∈[6,14)，逐个枚举 2^M 验证最小权重）：**权重 mismatch = 0，60/60 证明最优**。确认 CP-SAT 给出真实最小权重错误。（实现者自己的 `test_cpsat_mle_finds_minimum_weight_solution_on_tiny_problem` 与 `test_near_optimal_gap_on_surface_code` 也通过。）
- 口径正确：这是"最可能**错误**"（MLE），不对简并求和，与 Tesseract/IP 同口径，§12 已写明。
- "BB72 上 BP-OSD 离 MLE 约 1.8 倍（Z：84 vs 47）"这个**具体数字**我没在预算内全量重跑（CP-SAT 约 0.2–1 s/shot × 数千 shot 太贵）；但**方法学正确、实现无误**，且定性结论（d=6 下 headroom 小、Relay 优势随距离增大）与表 (a)/(b) 自洽。建议：若要把该结论写进论文，需用正式密钥、更大样本重算一次（见条件 5）。

---

## 4. 其他核查点（实现者重点 4 / 6）

- **种子反推**：种子 = HMAC-SHA256(≥256 位密钥)，每批独立派生；候选只见本 sector 半数 detector 的 syndrome，见不到任何 RNG 输出；stim 采样在父进程。从 syndrome 反推 stim 内部 PRNG 不可行——已写为局限，接受。
- **留出集选择性停止**：停止规则按**候选失败数**（每 sector ≥1000）停。这是定失败数的负二项/可选停止：点估计对候选**略偏高**（高估失败率，不利于候选），R=1000 时偏差 ~0.1% 相对，且 `binomial_interval` 按二项处理有轻微失配。**不可被候选用来显得更好**。建议文档补一句（条件 4）。
- **成绩单（实现者重点 6）**：
  - `schedule_hash = program_hash`，重复提交按 (task_id, program_hash) 计 attempt、按**第一次**排名。对程序做无关改动可换 hash 重算——**但留出集的 shot 序列只由 task+密钥+split 决定，与程序无关**，所以"重抽"跑的是**同一批 shot**，确定性解码器的 P_any 完全确定，唯一可"重抽"的只有计时抖动（76000 shot 里约 1 个）。§12.6 把这条限制说得比实际更严重，其实对解码任务几乎是优点（建议澄清，条件 3）。
  - 没有密钥时 `_decoder_entry_problems` 会追加"seed commitment cannot be checked" → `_append` 拒写。留出集评估本身就需要密钥，官方榜还需冻结 + verified，层层 fail-closed。候选无法调 `_append`（沙箱内不能 import evaluators、无 `_CREDENTIAL`）。核对无误。

---

## 5. 冻结前需处理（条件）

1. **（低危）** `file-read-metadata` 全局放行使沙箱内可 stat 密钥与所有项目文件（内容仍被拒）。要么收窄，要么在 §12.6 明确记录"文件大小/权限/存在性可见、仅内容受保护"，确认可接受。并说明为何 `(allow default)` + 逐条 deny（而非 deny-default 白名单）是 macOS 上的现实选择。
2. **（低危健壮性）** `CpSatMLE._prep` 的 `id(problem)` 缓存键改为稳定键（problem.fingerprint 或 WeakKeyDictionary），或直接去掉缓存，避免未来接入方拿到静默错误的 MLE。
3. **（文档）** 澄清 §12.6："重抽"对解码任务只影响计时抖动——留出集 shot 序列与程序无关，精度确定。
4. **（文档）** 记一句留出集停止规则是定失败数停止（可选停止），估计保守、R=1000 时偏差可忽略。

## 6. 可接受的局限（已记录或应记录）

- 沙箱非 VM：编译库的内存破坏可绕过 audit hook，但仍困在 `sandbox-exec` 内——已记。
- per-shot CPU 归属**量化**（psutil 读数常见 0，均值准确、p99 真实）：个别临界 shot 的超上限判定会抖动，但**每批总预算**才是真正的闸门（§2.1 BLAS 实测 303/batch 超预算），已由 §12.6 覆盖。
- bb90 在 p=3e-3 下正式排名约 14–21 CPU 小时/候选，很贵——需 PI 决策（提高 p / 降门槛 / 只用 bb72 排名），§12.7 已提。

---

## 7. 复现要点

```bash
export QEC_DECODER_SECRET_FILE=<repo 外的临时 0600 密钥>
export PYTHONPATH=/Users/ephemeral/Desktop/qec-ai-search
cd /Users/ephemeral/Desktop/qec-ai-search
D=research/audits/2026-10-04-decoder-task-scripts
# 合法基准 / 各攻击候选（自检任务 public split，不需正式密钥）
uv run python $D/drive.py selftest-surface-d5-dec public 500 $D/cand_pymatching.py 1
uv run python $D/drive.py selftest-surface-d5-dec public 500 $D/atk_blas_hide.py 1   # -> P_any=1.0（预算判死）
uv run python $D/drive.py selftest-surface-d5-dec public 100 $D/atk_metadata.py 1    # 内容读全 PermissionError
uv run python $D/drive.py selftest-surface-d5-dec public 50  $D/atk_sigcont.py 1     # kill_blocked
# 实现者测试（本次全过）
uv run python -m pytest tests/test_decoder_eval.py -k "sandbox_attack_blocked or os_sandbox_profile or sectors_never_run or forged_reply or huge_output or output_format_attacks or candidate_randomness or numpy_global_random or search_set_memorisation or holdout_seed_not_leaked" -q   # 65 passed
uv run python -m pytest tests/test_decoder_eval.py -k "cpsat_mle_finds or near_optimal_gap_on_surface or pymatching_candidate or relay_candidate_matches or mp_engine_relay or mp_rules_end_to_end or mp_task_rejects" -q                                           # 7 passed
```
mp_rule 新 bypass 与 CP-SAT vs 暴力穷举对比的脚本见本目录（内嵌在复现命令/报告 §2.1、§3.2 的说明中）。
