# 评估器 v2 红队审计（auditor，新会话，2026-10-02）

对象：合并进 main 的评估器 v2（commit `ccd082a`）：`evaluators/`（新增 `candidate.py`、`pipeline.py`、`tasks.py`）、
`scripts/freeze_evaluator.py`、`.claude/hooks/guard_frozen.py`、`tests/test_{g1_attacks,pipeline,freeze}.py`。
脚本与原始输出：`research/audits/2026-10-02-evaluator-v2-scripts/`（在该目录下 `uv run python <脚本>`）。
没有修改 `evaluators/`、`tests/`；`research/leaderboard.jsonl` 前后都是 0 字节（sha256 e3b0c442…）；冻结与正式成绩单相关的攻击都在临时项目副本里做；没有 git commit。
CPU 约 0.9 CPU 小时，并行 ≤4。v2 的相关测试先跑了一遍：`test_g1_attacks/pipeline/freeze/candidate/leaderboard` 112 passed（`pytest_v2_stdout.txt`）。

## 结论：**NOT READY**

核心设计是对的：候选只交调度 JSON、电路由评估器生成，G1 的全部成功攻击都被拒绝或在结构上被排除（§1）。
但有 6 个问题必须在冻结前改 `evaluators/` 才能修好，冻结之后就改不了：

1. **S4 批文件注入（严重）**：另一个进程不 import 评估器、也不拿凭证，只改写 L2 的批结果文件，就能让 pipeline 用自己的凭证
   写进一个低 260 倍的分数，`verify_leaderboard` 也通过。
2. **S8 误拒合法调度（严重，可用性）**：BB 码有冗余行。只要各校验的测量时间不同步，L0 就会把冗余组合多数成额外的窗口
   （“测了 6 次，要求 3 次”）。BB72 上 10/12 个合法变体、gross 上 1/3 被拒。逐检查自由的调度大部分会撞上这一条。
3. **S1 规范化哈希和电路不是函数关系**：全局平移会改变生成的电路（unroll 在并列时取最小 σ）。提交非规范的平移代表时，
   L2 照常跑完，写榜时才因为电路哈希不一致抛 `ValueError`。随机自由调度里 36% 有这个问题，Strikis Fig.12 本身也有。
4. **S10 正式成绩单的守卫用字符串比较路径**：`leaderboard_path="research/leaderboard.jsonl"`（相对路径）就能绕过
   “只收已冻结评估器 + purpose=score”。selftest 记录写进正式榜，`verify_leaderboard()` 返回 `[]`。verify 也不检查记录的
   evaluator 哈希、是否冻结、库版本（W2）。
5. **S5 种子可以挑**：seed 由调用方给，`submit=False` 不留痕迹。在 12 个种子里挑最好的一个，相对中位数便宜 5%，
   相对最差便宜 9%。之后这次就是“第一次提交”，attempt 规则挡不住。
6. **F7 `PYTHONPYCACHEPREFIX` 绕过 pyc 校验**：字节码缓存放在 evaluators/ 之外，那里的伪造 pyc 会被加载。
   `freeze verify` 和 `pipeline.environment_check()` 都报完整（verified/matches_frozen/ok = True），实际行为已经变了。

这几项都是局部修改（修复建议见 §4）。修完后只需要复审 §4 这几项，并把对应脚本加进回归测试。

---

## 1. 回归：G1 的成功攻击

| G1 # | 复现（v2） | 结果 |
|---|---|---|
| A1 伪轮次 | 原脚本 `a1_fake_rounds.py 3 3`、`5 10`（直接用 check_l0）→ `regress_a1_*` | **被拒**：两个基底都在 `stabilizer_coverage` 失败（“fake … do not re-extract”，d=5 时 216 个窗口）。诚实电路仍然 PASS，d_circ=d。走 pipeline 时结构上不可能：调度 JSON 不能表达重测，多余字段、多出来的校验、重复列都被拒（`s2`） |
| A1b 读出后再测 | `a1b_… 5 10` → `regress_a1b_*` | **被拒**（`data_layout`：最终读出之后还有 216 次测量）。模板里读出单独放在最后一层，结构上不可能 |
| L0-2 冗余行不测 | `a_l0_redundant_rows.py` | 原始电路上 L0 **仍然接受**（README §5 已写明）。pipeline 里结构上排除：少列一行就 `rejected_schedule`（`s2`、test） |
| N1 si1000 的 `I` 门 | `a_si1000_identity.py --direct 5` | **已修**：Σ先验 3.6369 = 3.6369，逻辑错误率 6.13e-3 对 6.18e-3（原来是 6.00e-3 对 3.15e-3）。si1000 也不再是打分模型 |
| N2 | — | si1000 已移出打分模型，`Task.validate` 拒绝 |
| L2-1 `I` 门伪装成制备 | `a_l2_identity_prep.py 5 5` | **已修**：paper 和 flat 的 Σ先验比值都是 1.0000。模板里没有 `I` |
| L2-2 diff | `a_l2_diff.py 25`（底层 `sample_l2`） | 底层仍可算出负值，但现在带 `valid=False`，区间是 [0, 0]，不再倒置。pipeline 里两个轮数的电路都由评估器从同一调度生成，σ 与轮数无关，所以边界相同，结构上排除 |
| L2-3 可复现性 | `a_l2_repro.py` | 1 个和 3 个 worker 的计数逐位相同 |
| L2-4 小样本 / 挑种子 | `s5` | 小样本已修（不足 1000 次失败的结果不上榜）。**挑种子仍然可行**，见 S5 |
| LB1–LB4、LB7 | `s3_leaderboard.py` | `submit` 和 `build_entry` 报 PermissionError；假凭证被拒；即使在同进程里拿到真凭证，rounds=30、gross_sd6、schedule_hash=deadbeef、p=1e-3、篡改 per_round 都被 `entry_problems` 拒绝 |
| LB5/LB6 | `s3` | 没有锚点时仍然发现不了（与文档一致）。有锚点时两者都能发现。注意：pipeline 不会自动写锚点，锚点要等人提交 commit 时才有 |
| F1 hook 大小写 | `s6` | **已修**：`EVALUATORS/L0.PY`、`Scripts/…`、`tests/TEST_L0.py` 都被拒。Unicode 变体（`scrİpts`、全角 `ｅ`）在 APFS 上不是同一个文件，hook 放行它们没有危害 |
| F3 伪造 pyc（树内） | `s6` | **已修**，verify 失败。但换个位置就能绕过，见 F7 |
| F4 .so，隐藏文件，`l0/` 包遮蔽 | `s6` | **已修**，verify 都失败 |
| F5 改冻结脚本 | `s6` | 脚本被改后自报“完整”（这是设计如此）。独立的 `shasum -a 256 -c research/evaluator_freeze.sha256` 能发现，列出 stats.py 和 freeze_evaluator.py 都是 FAILED |
| F6 库版本 | 读代码 | 已固定到 `==`，pipeline 写榜前核对 `md.version`。只核对元数据，没有核对已安装文件本身（§5） |
| F2 Bash 绕过 hook | — | 未改（只能靠 chmod/chflags）。另外 `.claude/settings.json` 不在冻结清单里，hook 自己的 Edit 规则也放行它（`s6` F9） |
| D1/D2 | — | 结构上排除：detector 由模板生成，每个 basis 型校验每轮一个 |

## 2. 新攻击（扮演只能提交调度 JSON 的搜索程序）

| # | 攻击 | 结果 |
|---|---|---|
| S1 | 全局平移规范化：同一个哈希能否对应不同电路 | **成功**（完整性 / 可用性）。`s1`：200 个随机自由调度中 73 个（确定的有 8 个）在 D 个平移下生成不止一种电路。`s1c`：Strikis Fig.12 的 8 个平移给出 2 种电路，IBM 只有 1 种。`s1b`：提交非规范平移后，L2 跑完才抛 `ValueError: refusing to append an inconsistent record: circuit hash …`。原因：pipeline 用**提交的** spec 生成电路，但存的是 `spec.canonical()`；unroll 在层数并列时取最小 σ，这个选择不是平移不变的。反方向（同一电路得到不同哈希）只能通过改动调度本身做到，那会得到真正不同的电路（README §11 已写） |
| S2 | 规范边界：period 0/1/65/True/6.0/"6"/1e400，时间步越界，CNOT 在 prep 或 meas 时刻，空 cnots，重复列，超出支撑的列，列号 10⁹ 或 −1，少一个或多一个校验，X/Z 列表互换，未知字段，两个校验同一步用同一数据比特，format v2 | **全部被拒**，诊断可读（`s2`）。合法边界被接受：跨周期窗口、JSON 重复键（取最后一个，无害）。小问题：(a) 用 numpy 整数构造的 dict 被拒，提示 “got np.int64(0)”；(b) 同进程直接传 `ScheduleSpec` 对象时不经过 JSON 解析，period 上限 64 不生效（period=200 也能打分，20000 也能展开），时间步越界会被取模 |
| S3 | sd6 噪声躲避：用时间步布局减少噪声位置 | **失败**（`s9`）。120 个随机模板电路加 sd6 后，每一层的每个比特都**恰好**有一个概率为 p 的噪声位置。模板还强制 D ≥ 行重+2、数据比特每步至多一个 CNOT，空闲位置压不到物理下限以下。唯一的“非物理”之处是 SD6 本身的口径：所有层等长，测量按 1 步计，所以测量时间错开的调度没有被惩罚（§5） |
| S4 | 篡改 L2 批文件 | **成功，严重**（`s4`）。攻击进程只知道目录位置，轮询并 `os.replace` 第 0 批，写入 `{shots: 10^7, fail_Z: 1000, fail_X: 1000, fail_any: 1999}`。(A) 调用方给了 `work_dir`；(B) 默认 `$TMPDIR/l2_*`，扫描新出现的目录即可。两种情况结果都是 `scored`，每轮 P_any 6.66e-5（诚实值 1.74e-2），由 pipeline 自己写进成绩单，`verify_leaderboard` 返回 `[]`，排名第一。原因：`_load_batches` 原样信任文件，shots ≠ batch_size、index 与文件名不符、失败数与 bits 不符都不检查；`entry_problems` 也不检查 shots = batches_used × batch_size。只有 `reproduce_entry` 能发现 |
| S5 | 挑种子 | **成功，中**（`s5`）。同一调度 12 个种子，`submit=False`：每轮 P_any 从 1.7185e-2 到 1.8815e-2（最好/最差 0.913，最好/中位数 0.951）。用最好的种子提交，记录 attempt=0，单独排名 |
| S6 | 漏斗与停止规则 | gross 的漏斗是空的，无从利用。停止规则判定作用于批前缀，结果确定。`promote_if … low < thr` 只会过滤，拿不到分。种子方面见 S5 |
| S7 | diff 口径 | 失败：只有 selftest 任务用 diff；σ 与轮数无关，r1 和 r2 的边界逐层相同 |
| W1 | 不拿凭证直接写成绩单 | **成功**（已知局限的实证，`s3`）。计数自洽的伪造记录（失败数不变，shots ×3，分数 1.74e-2 → 5.74e-3）自己算好哈希链后追加到文件，`verify_leaderboard` 返回 `[]`。只有 `reproduce_entry` 能发现（R1：计数不一致） |
| W2 | 记录的 evaluator 字段写成“未冻结、另一个哈希”，versions 写成 stim 0.0.0 | **成功**：verify 返回 `[]`，`entry_problems` 不看这些字段 |
| R2 | 骗 `reproduce_entry`（diff 任务） | **成功，低**（只有 selftest 用 diff）。只改 `l2.components[r1].counts` 和 per_round，顶层 `l2.counts` 不动：`entry_problems` 返回 `[]`，`reproduce_entry` 返回 `[]`，分数 2.455e-2 → 2.225e-2。原因：reproduce 只比较顶层 counts，entry_problems 只用 components 里的计数 |
| S10 | 用相对路径写正式成绩单 | **成功，高**（临时副本里，`s10`）：见结论第 4 条 |
| F7 | `PYTHONPYCACHEPREFIX` 伪造 pyc | **成功，高**（临时副本里，`s6`）：`likelihood_factor_to_sigma(1000)` 从 3.717 变成 42.0，verify 和 environment_check 都报完整 |
| F8 | evaluators/ 下的隐藏文件、子包遮蔽模块 | 失败（verify 能发现） |
| F9 | hook 的 Unicode 路径变体，`.claude/settings.json` | Unicode 变体无害；settings.json 可以被编辑，相当于把 hook 关掉（建议纳入清单） |
| — | code_spec | 固定码的任务拒绝其他规范写法（例如 `x^15` ≡ `x^3`），偏保守，无害。`table()` 和 attempt 只按 schedule_hash 区分；将来做多码任务时应该把码哈希也加进键 |

## 3. 可用性

**耗时**（本机，3 worker，`s7_usability_timing_stdout.txt`）：

| | L0 不含距离 | L0 + 距离（3 轮） | 备注 |
|---|---|---|---|
| 表面码 d=3（自检预算 100/8） | 0.07 s | 4.3 s | 完整 `evaluate`（含 L2，每个 sector ≥1000 次失败，38000 shot）6.0 s |
| BB72 [[72,12,6]] IBM 调度 | 6 轮 2.2 s；3 轮 0.9 s | 默认预算 1500/96：**42.8 s**（d=6）；200/8：10.3 s（d=6） | |
| gross（任务预算） | 12 轮 8.3 s | **133 s**（d=10） | 正式 L2（每个 sector ≥1000 次失败）在漏斗为空时每个候选要数十 CPU 小时量级 |

**诊断**：调度不合法时逐条列出（校验编号、数据列、时间步，可以直接修）；但数据比特冲突的检查只在其他问题都修完后才报，修起来要来回好几轮。
L0 的 to_text 足够详细。距离失败时，见证用**电路比特编号和 tick** 表示（`tick 3: DEPOLARIZE2 on [10, 5] -> Z5`），而候选只认识
“校验 #i、数据列、周期内时间步”。建议在诊断里把见证翻译回调度坐标：哪个校验、第几轮、哪一步 CNOT、哪个数据列。

**误拒**：
- 表面码 d=3：150 个确定的随机逐检查自由调度（含跨周期窗口），L0（不含距离）150/150 通过，中位耗时 0.11 s。
- **BB72：10/12 个合法的“自由窗口”IBM 变体被误拒；gross：1/3 被误拒**（S8，`s8`、`s8b`）。原因已确认：被多计的行（例如
  gross 的 X 行 5，测量时刻 t=10）等于在其他时刻测量的若干行的 GF(2) 和，flow 覆盖检查把这个组合算成一个与它自己的测量
  时间上不重叠的额外窗口，于是计数 = 2R ≠ R。表面码没有冗余行，所以不受影响。

**缺口**：没有公开的“只跑 L0 / 便宜代理”入口。`evaluate(submit=False)` 在 L0 通过后一定会跑完整 L2，gross 上不可承受。
搜索程序要么直接 import `check_l0`（违反 CLAUDE.md 的分离规则），要么每个候选都付完整 L2 的代价。建议加 `evaluate(..., stage="l0")`
或者公开一个 `precheck`。另外 gross 任务的漏斗是空的（等 E-004）。

## 4. 冻结前必须修（按严重程度）

1. **S4 批文件**（l2.py）：(a) 每个批文件都要核对 shots == batch_size、index == 文件名、fail_Z/X/any/both == bits 的 popcount
   （以及按位或 / 与的结果）。(b) 主进程按同一种子重算若干个随机抽取的前缀批，逐位比较，或者用每次运行随机生成的 HMAC 密钥
   给批文件签名（密钥经 sinter 的 pickle 传给 worker，不落盘）。(c) `pipeline.evaluate` 去掉公开参数 `work_dir`，目录由评估器
   以 0700 创建。(d) `entry_problems` 核对 shots == batches_used × batch_size。回归测试用 `s4`。
2. **S8 误拒**（l0.py / pipeline）：计数时冗余组合不应算作额外窗口。可以按每个生成元“自己的测量”计数；或者在模板路径上要求
   计数 ≥ R，因为模板已经保证每行每轮恰好一次，L0 的计数只是第二道防线；或者把窗口内由其他行组合确定的值从 A_s 里排除。
   回归测试用 `s8`、`s8b` 生成的 BB72 和 gross 调度。
3. **S1**（pipeline.py）：用 `spec.canonical()` 生成电路（一行修改），或者把 unroll 的并列规则改成平移不变的。
   加测试：Strikis 的每个平移都能打分，并且能写榜。
4. **S10 / W2**（pipeline.py、leaderboard.py）：判断是否是正式成绩单时，用 `Path(p).resolve() == DEFAULT_PATH.resolve()`
   （或 samefile）。`verify_leaderboard()` 核对默认路径时，要求 `purpose == "score"`、`evaluator.verified is True`、
   `evaluator.hash` 等于 `research/evaluator_freeze.json` 里的哈希、`versions` 等于 PINNED_VERSIONS。
5. **S5**（pipeline.py）：正式任务的种子由评估器派生，例如 `seed = H(task_hash, schedule_hash)`，或者调用方给的种子必须等于它。
   这样只能靠改动调度来“重抽”，而那会得到真正不同的电路（已知局限）。
6. **F7**（freeze_evaluator.py / pipeline.py）：评估入口断言 `sys.pycache_prefix is None`（或连同 prefix 下的 pyc 一起校验）。
   更稳的做法是在 environment_check 里检查每个已加载的 `evaluators.*` 模块：`__spec__.origin` 在 evaluators/ 内；
   `__cached__` 如果存在就做同样的代码对象比较。
7. （低）**R2**：`reproduce_entry` 应该比较 components 的计数（或者整个 l2 计数字典）；`entry_problems` 应该核对
   `counts["rounds_r"] == components[r].counts`。
8. （可用性，建议同时修）公开一个只跑 L0 的入口；距离见证翻译回调度坐标；numpy 整数在解析时接受或给出明确提示；
   `.claude/settings.json` 纳入冻结清单。

## 5. 可以接受的局限（写进文档即可）

- 同进程恶意代码，以及同一用户对文件的写权限：能伪造计数自洽的记录（W1），只有 `reproduce_entry` 能发现。
  要靠沙箱、冻结后 chmod/chflags、抽查榜首记录（建议每个新的榜首都跑一次 `reproduce_entry`）。修完 S4 后，至少“不读写
  评估器内存的并发进程”就伪造不了 pipeline 自己写的分数了。
- 改动调度来“重抽”：每个 sector ≥1000 次失败时收益约 ±3–6%（README §11）。
- SD6 的口径是所有层等长、测量算 1 步：测量时间错开（流水）的调度在这个模型下不受惩罚，在测量较慢的硬件上会显得偏好。
  这是模型选择，不是实现 bug（每层每个比特恰好一个噪声位置已验证，S3）。
- 距离只是上界；gross 的距离在 3 轮电路上算；门槛 10 是暂定值。
- `.venv` 里的库文件被改动发现不了（只核对版本元数据）。建议冻结时把关键分发包的 RECORD 文件哈希纳入清单；在此之前靠目录锁和 `uv sync --locked`。
- hook 只能拦 Edit/Write（F2）；Unicode 路径变体无害。
- 锚点要靠人提交 commit；最后一个锚点之后的尾部可以被删而不被发现。
- 原始电路上的 L0 仍然接受“冗余行不测”（L0-2）。pipeline 在结构上排除了它，PI 已决定不允许省略。

## 6. 复现命令

```
cd research/audits/2026-10-02-evaluator-v2-scripts
uv run python s1_canonical_hash.py 200            # S1 平移依赖统计（约 1 分钟）
uv run python s1b_canonical_hash_pipeline.py      # S1 → pipeline 写榜时抛 ValueError
uv run python s1c_canonical_real_schedules.py     # Strikis 平移依赖
uv run python s2_schedule_edge_cases.py           # 规范边界
uv run python s3_leaderboard.py                   # LB 回归、W1/W2、LB5/6、R1/R2（临时文件）
uv run python s4_batch_file_injection.py          # S4（临时成绩单）
uv run python s5_seed_shopping.py 12              # S5
uv run python s6_freeze.py                        # F1–F10（临时项目副本）
uv run python s7_usability_timing.py --gross      # 耗时与诊断样例（约 3.5 分钟）
uv run python s8_free_schedules_false_reject.py 150 12   # 误拒统计
uv run python s8b_gross_free_windows.py 3         # gross 误拒与原因
uv run python s9_noise_coverage.py 60             # sd6 噪声位置不变量
uv run python s10_official_path_bypass.py         # 正式成绩单路径守卫（临时项目副本）
# G1 原脚本回归（在 ../2026-10-02-evaluator-G1-scripts/ 下运行，输出在本目录 regress_*.txt）：
#   a1_fake_rounds.py 3 3 / 5 10；a1b_fake_rounds_early_readout.py 5 10；a_l0_redundant_rows.py；
#   a_l2_identity_prep.py 5 5；a_si1000_identity.py --direct 5；a_l2_diff.py 25；a_l2_repro.py
```
