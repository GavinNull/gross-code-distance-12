# G1 评估器红队审计（auditor，2026-10-02）

对象：`evaluators/`（codes, noise, l0, distance, l2, stats, leaderboard）+ `scripts/freeze_evaluator.py` + `.claude/hooks/guard_frozen.py`。
立场：扮演“不惜代价拿高分”的搜索程序，构造不合法或不该得高分、却能骗过评估器的输入。
脚本与原始输出：`research/audits/2026-10-02-evaluator-G1-scripts/`（所有命令在该目录下执行，`uv run python <脚本>`）。
没有修改 `evaluators/`、`tests/`；真实的 `research/leaderboard.jsonl` 前后都是 0 字节；冻结机制的攻击全部在临时目录的项目副本里做。
CPU 用量约 1 CPU 小时，并行 ≤3 worker。

## 结论：**NOT READY**

评估器有一个致命的 L0 漏洞（“假轮次”）：1 轮真正的 syndrome 提取 + 反复重测同一批辅助比特，就能通过全部 L0 检查
（含距离 d_circ = d），L2 每轮逻辑错误率比诚实电路低 4.5 倍；再配合“数据比特提前读出”，低约 70 倍。
任何进化搜索都会很快找到这条路。另外，`leaderboard.submit` 完全信任调用方给的字典，`sample_l2` 的 `rounds` 不与电路核对，
SI1000 的空闲噪声可用 `I` 门躲开（逻辑错误率减半），`diff` 口径可被压成负数，冻结机制有多处可绕过。
这些修完、并把下面的攻击电路加进回归测试后，需要再审一次。

---

## 1. 攻击清单

| # | 类别 | 攻击 | 结果 |
|---|---|---|---|
| A1 | L0 覆盖 | 假轮次：1 轮真提取 + R−1 层“只重测辅助比特”（M 不复位） | **成功**，严重 |
| A1b | L0 覆盖 + L2 paper | A1 + 数据比特在唯一一轮后立刻最终读出，重测放在读出之后 | **成功**，严重 |
| L0-2 | L0 覆盖 | 冗余校验行每轮都不测 | **成功**（口径问题，需 PI 裁决） |
| L0-3 | L0 observable | 空 / 重复 / 编号缺口 / 抵消成空的 observable | 失败（已被拒；与现有测试一致，未另写脚本） |
| N1 | 噪声 si1000 | 在含测量/复位的层给空闲比特写 `I`，躲开 ResonatorIdle 2p | **成功**，高 |
| N2 | 噪声 si1000（误拒） | SI1000 原生 CZ 电路（数据比特在 CZ 两侧有 H）进不了 L0 / L2 | 发现 bug（误拒，不是骗分） |
| N3 | 噪声 sd6 | 用“作用平凡”的 CX（新复位的辅助比特）替代数据空闲，借 DEP2 的单比特边缘 0.8p < p | 失败（复位翻转 p 经 CX 传给数据，净噪声更大） |
| N4 | 噪声 sd6 | `I` / H·H 替代空闲；把操作塞进同一层；空层；REPEAT | 失败（I = 空闲 = DEP1(p)；同层冲突被 tick_structure 拒；空层同样加噪声；REPEAT 展开） |
| L2-1 | L2 paper | 在每个数据比特第一个双比特门前插一个 `I`，把复位后的空闲层变成“制备”被 paper 整段去掉 | **成功**，中（同一逻辑电路 Σ先验 −2.4%，每轮 P_any −6%） |
| L2-2 | L2 diff | 候选的 callable 给 r1 一个边界更差的电路（读出前多等 K 层） | **成功**，高（K=6：−21%；K=25：点估计为负、区间倒置） |
| L2-3 | L2 可复现性 | 同 seed、1 vs 3 worker、按错误数停止（有丢弃批） | 失败（逐位相同，README 的声明成立） |
| L2-4 | L2 选择性报告 | 换种子挑最好；小样本 | **成功**（榜单照收，只有 warning） |
| LB1 | L2 + 榜单 | `sample_l2(rounds=30)` 用在 3 轮电路上 | **成功**，严重（每轮错误率缩小 10 倍，照收） |
| LB2 | 榜单 | 伪造 `l0_report={"passed": True}`、伪造 L2 字典 | **成功**，严重 |
| LB3 | 榜单 | 非打分噪声模型（gross_sd6）上榜 | **成功** |
| LB4 | 榜单 | `schedule_hash` 与 L2 实际采样的电路不同 | **成功** |
| LB5 | 榜单 | 删掉末尾若干行 | **成功**（verify 不报错） |
| LB6 | 榜单 | 改一行后重算整条哈希链 | **成功**（README 已承认） |
| LB7 | 榜单 | 不同 p / 解码器参数 / code 混在同一个榜 | **成功**（submit 不检查） |
| D1 | 距离 | 冗余 detector（已有 detector 的组合）把症状加粗，藏住距离 3 的错误 | 部分：graphlike 与 stim_search 都失明（none），**BP-OSD 仍找到 3**，L0 正确拒绝 |
| D2 | 距离 | seed / worker 数是否改变 L0 判定 | 失败（D1 电路上 8 个 seed、1/3 worker 判定相同） |
| D3 | 距离 | 伪造能通过注入验证的见证 | 不构成攻击：见证只会**降低**上界，候选没有动机；也没找到让真见证被误判为“未验证”的路径 |
| F1 | 冻结 | hook 路径比较区分大小写：`Evaluators/l0.py` 在 macOS 上放行 | **成功** |
| F2 | 冻结 | hook 只挂在 Edit/Write/NotebookEdit 上，Bash 写文件不经过 | **成功**（设计如此，CLAUDE.md 靠自律） |
| F3 | 冻结 | 在 `__pycache__` 里放伪造 .pyc（头部写源文件的 mtime/size） | **成功**：行为改变，verify 通过，榜单 `matches_frozen: True` |
| F4 | 冻结 | 哈希只覆盖 `evaluators/**/*.py`；同目录 `.so` 优先于 `.py` 导入 | **成功**（覆盖面缺口） |
| F5 | 冻结 | 改 `scripts/freeze_evaluator.py`（不在哈希里）让 verify 与榜单都报“完整” | **成功** |
| F6 | 冻结 | 依赖库版本（pyproject 无版本约束）不在哈希里 | **成功**（覆盖面缺口） |

---

## 2. 成功的攻击（含最小复现）

### A1 假轮次（严重）

`common.fake_rounds`：取 stim 的 1 轮旋转表面码电路，辅助比特 MR 改成 M；之后插 R−1 层 `M <全部辅助比特>`，
每层 detector = 本次 ⊕ 上一次。数据比特只与辅助比特相互作用一次。

```
uv run python a1_fake_rounds.py 3 3          # L0 两个基底全部 PASS，d_circ=3
uv run python a1_fake_rounds.py 5 10 --l2    # 输出 a1_d5_r10_stdout.txt
```

| d=5，10 轮，sd6 p=0.005，paper，pymatching | L0 | 每轮 P_any [LR=1000] |
|---|---|---|
| 诚实电路（stim 10 轮） | PASS，d_circ=5 | 1.98e-2 [1.81e-2, 2.16e-2] |
| 假轮次 | **PASS，d_circ=5**（含 `require_opposite_type_detectors=True`） | **4.39e-3** [3.92e-3, 4.91e-3] |

原因：flow 覆盖检查（README §3.2）数的是“时间上不重叠、其测量奇偶等于 **body 输入时刻** s 值的窗口”。
无噪声时重测辅助比特 a 的结果恒等于第一次测量 = s_in，所以每一次重测都是 A_s 的一个元素，被算成一轮。
检查的是“值被确定”，不是“这一轮重新从数据比特里提取了 s”。README 把“一轮测两次、另一轮不测”列为可接受，
理由是“测量次数和噪声都没有减少”——A1 正是把这一语义推到极端，噪声大幅减少。

### A1b 假轮次 + 提前读出（严重）

`common.fake_rounds_early_readout`：数据比特在唯一一轮后立刻最终读出（与 stim 原电路相同的位置），R−1 层重测放在读出之后。
paper 口径去掉数据比特读出层之后的所有噪声，所以“假轮次”期间数据完全无噪声。

```
uv run python a1b_fake_rounds_early_readout.py 5 10 --l2   # a1b_d5_r10_stdout.txt
```
L0 PASS，d_circ=5；每轮 P_any = **2.81e-4** [2.49e-4, 3.15e-4]，比诚实电路低约 70 倍。
`diff` 口径也挡不住：P(r) 几乎不随 r 增长，差分只会更接近 0。

**修复建议**（L0）：每个窗口必须真正从数据比特重新提取 s。可操作的判据：对相邻代表元的比较 c_{j−1} ⊕ c_j，
用 `detecting_regions` 求其敏感区域，要求在 (窗口 j−1 结束, 窗口 j 结束] 之间的某个 tick，它在数据比特上的限制恰好是 s
（即 s 支撑上的数据错误在这段时间里会被它看见）。A1 中这个区域只在辅助比特 a 上，会被拒。
另外建议 L0 / L2 要求最终数据读出是电路最后一个含测量的层（不允许读出后还有辅助比特测量），直接封掉 A1b 的“读出后”部分。
两个电路都应加进 `tests/test_l0.py` 作为回归攻击。

### LB1 + LB2..LB7 榜单信任调用方（严重）

```
uv run python a_leaderboard.py     # 全部写临时文件；a_leaderboard_stdout.txt
```
- LB1：同一个 3 轮电路，`sample_l2(rounds=30)` 得到每轮 P_any 2.43e-3（真值 2.40e-2），失败计数完全相同；`submit` 照收，记录 `rounds=30`。
  `sample_l2` 的 docstring 写着“必须与电路一致”，但没有任何检查；diff 的 r1/r2 同样。
- LB2：`build_entry(l0_report={"passed": True, "d_circ": 99}, l2=<改过 rates/per_round 的字典>, schedule_hash="deadbeef")` → `submit` 照收。
- LB3：`noise_model="gross_sd6"`（候选不写 I 就没有空闲噪声）的结果上榜，只有 warning。
- LB4：`schedule_hash`（来自 build_entry 的 circuits 参数）与 `l2.circuit.candidate_hash` 不同，照收；L0 报告与电路也没有绑定。
- LB5：删掉最后 3 行，`verify_leaderboard` 返回 `[]`（没有记录“应有多少行”或外部锚点）。
- LB6：改第 1 行并重算整条链，`verify_leaderboard` 返回 `[]`。
- LB7：p、解码器参数、code（`checks_sha256` 只记录不核对）都由调用方决定，不同口径混在同一个榜上。

**修复建议**：榜单只能由一个评估器自己的入口写，例如 `evaluate_and_submit(task_id, circuits, seed)`：
任务（code、data_qubits、rounds、约束、噪声模型、p、解码器参数、StopRule、boundary）从冻结的任务注册表读，
评估器自己跑 L0 与 L2（`rounds` 取 L0 覆盖检查实际数出的轮数并断言等于任务值），`schedule_hash` 与 L2 / L0 用同一份电路计算；
拒绝非 SCORING_MODELS、拒绝任一 sector < 1000 次失败的结果。哈希链的末端哈希定期写进 git 提交或 `decisions.md`（外部锚点），
防删尾和整链重算。

### N1 SI1000：`I` 门躲开 ResonatorIdle（高）

`noise.add_noise` 只对“本层没被任何操作作用”的比特加 ResonatorIdle（默认 `si1000_resonator_on_gate_qubits=False`），
而 `I` 算作“操作”，只付 DEP1(p/10)。在每个含测量/复位的层给空闲比特写一个 `I`，2p 的空闲噪声就变成 p/10。

```
uv run python a_si1000_identity.py --direct 5    # a_si1000_identity_stdout.txt
```
d=5 表面码（CX 改写成 H·CZ·H），5 轮 Z memory，si1000 p=0.002：Σ先验 3.637 → 3.239；
逻辑错误率 **6.00e-3 → 3.15e-3**（pymatching，各 >1500 次失败）。同一个逻辑电路，分数接近减半。
（这里直接用 `add_noise` + sinter，因为 L0/L2 都会误拒这个 CZ 电路，见 N2；漏洞在 noise.py，与 L0/L2 无关。
sd6 下 `I` 与空闲同为 DEP1(p)，不受影响。）

**修复**：`I` 一律按空闲处理（所有模型都加 idle 与 resonator 噪声），或在 si1000 下禁止 `I`；更一般地，
ResonatorIdle 是否作用于做单比特门的比特，PI 裁决前至少不能让“恒等门”成为免噪声通道。

### L2-2 diff 口径（高）

```
uv run python a_l2_diff.py 6     # a_l2_diff_stdout.txt
uv run python a_l2_diff.py 25    # a_l2_diff_K25_stdout.txt
```
d=3，diff(3, 9)，sd6 p=0.005，pymatching。r1=3 的电路在读出前多 K 个空层（r2 电路不变）：

| | diff 每轮 P_any |
|---|---|
| 诚实 | 3.49e-2 [3.19e-2, 3.80e-2] |
| K=6 | 2.74e-2 [2.42e-2, 3.08e-2]（区间不重叠） |
| K=25 | **−5.95e-3**，区间 **[0, −9.9e-4]**（low 截断到 0 后大于 high），warning 写的是“statistical fluctuation” |

原因：`circuits` 是候选的 callable，评估器不对 r1 电路做 L0，也不检查两种轮数的电路是“同一调度、只差体内轮数”。
**修复**：diff 只接受评估器自己从调度生成的两种轮数电路；两种轮数都跑 L0；检查 r2 电路 = r1 电路在体内重复插入
(r2−r1) 个周期（边界层逐层相同）；点估计为负时不给分（返回失败而不是负数），并修正 low > high 的区间。

### L2-1 paper 口径的 `I` 门制备（中）

```
uv run python a_l2_identity_prep.py 5 5 --l2    # a_l2_identity_prep_stdout.txt
```
`_parse_memory` 把“第一个双比特门之前的复位 + 单比特门”整段算作制备，paper 去掉 `layer <= prep_end[q]` 的数据噪声。
在每个数据比特第一个 CX 的前一层放一个 `I`，复位与第一个 CX 之间的空闲噪声就被去掉。d=5、5 轮：L0 PASS，d_circ=5；
paper 的联合 DEM Σ先验 6.380 → 6.225（flat 不变），每轮 P_any 3.77e-2 → 3.54e-2。对首轮数据等待更长的调度（例如 qLDPC 的
深调度）收益更大。**修复**：paper 只去掉到**复位**为止的数据噪声（复位后的单比特门与空闲照常加噪声），或对所有数据比特用同一个
“全局首个数据双比特门层”。

### L0-2 冗余校验行可以永远不测（中，需 PI 裁决）

```
uv run python a_l0_redundant_rows.py    # a_l0_redundant_rows_stdout.txt
```
表面码 d=3 加一个冗余 Z 行、一个冗余 X 行，冗余行的辅助比特每一轮都不用：覆盖检查仍给出每行 3 次，CX 数 108 → 72，Z 基底 L0 PASS。
对 gross code（HX、HZ 各 6 个冗余行）意味着候选可以少 12 个辅助比特、每轮少 72 个 CNOT，却与每轮测 144 行的 IBM 电路同榜比较。
这可能是合法的设计选择，但必须由 PI 明确：“每个生成元被测 rounds 次”是否要求每一行都由自己的测量得到。
若要求，判据可以是：A_s 的代表元不能完全落在其他生成元代表元的张成里（同一窗口内）。

### N2 SI1000 原生电路被 L0 / L2 误拒（中，可用性）

`a_si1000_identity.py`（不带 `--direct`）报的错：L0 把“第一个数据双比特门之前”作用在数据比特上的 H 当作制备从 flow body 里删掉，
于是 X 基底测量的 H·CZ·H 结构被破坏，所有生成元“测了 0 次”；L2 要求数据比特最后一个双比特门之后只能是读出，CZ 改写产生的尾部 H 被拒。
结果是 SCORING_MODELS 里的 si1000 实际上无法给自然的 CZ 电路打分。修 N1 时一并修。

### L2-4 选择性报告（中）

```
uv run python a_l2_repro.py    # a_l2_repro_stdout.txt
```
同一电路 8 个种子、每个 2000 shot：每轮 P_any 从 0.0213 到 0.0308（最好/最差 0.69）。榜单不限制种子、不要求最少失败数（只有 warning），
也不记录一个候选被评过几次。由“评估器入口 + 任务固定 StopRule（每 sector ≥1000 次失败）+ 记录全部提交”解决。

### F1–F6 冻结机制

```
uv run python a_freeze.py    # 在临时目录的项目副本里做；a_freeze_stdout.txt
```
- F1：`guard_frozen.py` 用 `rel.startswith("evaluators/")` 与精确集合比较；macOS APFS 不区分大小写，`Evaluators/l0.py`、
  `EVALUATORS/noise.py`、`Evaluators/FROZEN`、`research/Leaderboard.jsonl` 都被放行，写入的是真文件。修复：比较前 `casefold()`，
  或用 `os.path.samefile` / inode 比较。
- F2：hook 只匹配 `Edit|Write|NotebookEdit`；`Bash(uv run *)` 全放行，任何 `uv run python -c "open('evaluators/l0.py','w')..."` 都不经过 hook。
  `settings.json` 的 deny 规则 `Bash(uv run python scripts/freeze_evaluator.py freeze*)` 用 `./scripts/...`、`-c` 或 `runpy` 即可绕过；
  `Bash(rm *evaluators/FROZEN*)` 用 `unlink` / `mv` / python 绕过。建议冻结时由人执行 `chflags uchg`（或 chmod a-w）锁住 evaluators/，
  并加一个 Bash 的 PreToolUse hook 拒绝提到 `evaluators/`、`leaderboard.jsonl` 的写命令（只能减少误操作，挡不住故意绕过）。
- F3：在 `evaluators/__pycache__/stats.cpython-312.pyc` 放一个伪造的 .pyc（头部写源文件的 mtime 与 size），
  `likelihood_factor_to_sigma(1000)` 从 3.717 变成 42.0；`freeze_evaluator.py verify` 报“评估器完整”，
  `leaderboard.evaluator_hash()` 报 `matches_frozen: True`。修复：哈希 evaluators/ 下的**全部文件**并拒绝清单外的任何文件（含 `__pycache__`、`.so`），
  或评估入口用 `python -B` / `PYTHONDONTWRITEBYTECODE=1` 并在启动时断言没有 `__pycache__`。
- F4：只哈希 `*.py`；导入时扩展模块（`.cpython-312-darwin.so`、`.abi3.so`）优先于 `.py`，放一个同名 `.so` 即可替换模块且不改哈希。修复同 F3。
- F5：`scripts/freeze_evaluator.py` 本身不在哈希里，而 leaderboard 动态加载它的 `combined_hash`。改它（例如让 `combined_hash` 返回 FROZEN 里的值、让 verify 不报错）后，
  篡改过的 stats.py 也显示“完整”、`matches_frozen: True`。FROZEN / MANIFEST 本身也在 evaluators/ 里，能改评估器的人就能一起改。
  修复：把 freeze 脚本、hook、`pyproject.toml`、`uv.lock` 纳入清单；冻结哈希另外记在 git tag 或 `decisions.md`（人写）里作为外部锚点。
- F6：stim / sinter / ldpc / pymatching / ortools 的版本直接决定采样、DEM、BP-OSD 与 CP-SAT 结果（本机 stim 1.16.0、ldpc 2.4.1、
  pymatching 2.4.0、ortools 9.15.6755），但 `pyproject.toml` 没有版本约束，评估器哈希也不含 `uv.lock`。一次 `uv sync` / `uv lock --upgrade`
  就会悄悄改变裁判。L2 结果里记录了版本，但 submit 不检查。修复：把 `uv.lock` 的哈希并入评估器哈希，`submit` 拒绝与冻结时版本不同的环境。
- `tests/`、`baselines/`：评估器代码不 import 它们（已 grep 确认），改动它们不改变评估器行为；但 tests 不在冻结范围，删掉回归测试不会被发现。
  建议把 `tests/test_{l0,noise,l2,distance,leaderboard,stats,codes}.py` 与 `tests/memory_builder.py` 一起纳入清单。

---

## 3. 失败的攻击（评估器挡住了）

- **N3 平凡 CX 替代空闲（sd6）**：DEP2(p) 在单个比特上的边缘是 0.8p，看似比空闲 DEP1(p) 小；但“平凡”需要辅助比特处于新复位的本征态，
  复位后翻转 p（X 或 Z）经 CX 传到数据比特，数据噪声净增加。用控制 / 目标、R / RX 四种组合推算都不划算，没有写脚本。
- **N4**：sd6 下 I、H 与空闲同为 DEP1(p)；同层塞两个操作被 `tick_structure` 与 `add_noise` 拒绝；空层所有比特照样有空闲噪声；REPEAT 先展开。
- **D1/D2 距离**：在 README 的“坏调度”（X 基底 d=5 → 3）上加 576 个冗余 detector：`graphlike` 与 `stim_search` 都返回 none，
  但 BP-OSD（默认预算，以及只给 25 次试验、0 个 LNS 起点的 8 个种子）每次都找到权重 3，CP-SAT 精确确认 3。1 与 3 个 worker 结果相同。
  `a_dist_redundant_detectors.py`、`a_dist_seed.py`。结论：距离闸门在这类电路上实际只靠 BP-OSD 一条路径；在更大电路上能否同样稳健未验证。
- **D3 伪造见证**：见证只会降低上界，候选没有动机；`verify_faults` 按指令名核对位置、注入后要求确定性、0 个 detector、翻转 observable，
  没找到让真实短见证被误判为“未验证”的输入。
- **L2-3 可复现性**：同 seed，1 worker 与 3 worker（后者丢弃了 15–19 号批）计数逐位相同。
- **L0 observable 边界情况**：现有测试已覆盖（空、重复、编号、Pauli 目标、补辅助比特记录、稳定子）；`OBSERVABLE_INCLUDE` 对同一记录引用两次会抵消，
  L0（集合异或）与 L2（计数奇偶）处理一致。
- **L2 noisy 口径**：对 `R + I` 这样的制备直接报错，L2-1 的 `I` 技巧在 noisy 下不可用。

---

## 4. 冻结前必须修的问题（按严重程度）

1. **A1 / A1b 假轮次**（l0.py 覆盖检查）：要求每个窗口真正从数据比特重新提取 s（见 §2 判据）；要求最终数据读出之后不再有辅助比特测量；两个攻击电路加进回归测试。
2. **榜单入口**（leaderboard.py + l2.py）：L0、L2 与写榜由评估器一个入口完成，参数来自冻结的任务注册表；`rounds` 由 L0 实测轮数核对；
   拒绝伪造字典、非打分噪声模型、schedule_hash 不一致、任一 sector < 1000 次失败；哈希链加外部锚点（LB1–LB7、L2-4）。
3. **N1 SI1000 的 `I` 门**（noise.py）：`I` 按空闲处理或在 si1000 禁用。同时修 N2（否则 si1000 不能真正用于打分；或者在修好之前把 si1000 移出 SCORING_MODELS）。
4. **diff 口径**（l2.py）：短轮数电路由评估器生成并过 L0，校验两种轮数是同一调度，负估计判失败，修正倒置区间（L2-2）。
5. **冻结机制**：hook 大小写（F1）；哈希覆盖 evaluators/ 全部文件并拒绝清单外文件、禁用 / 检查字节码（F3、F4）；freeze 脚本、hook、`uv.lock`、
   `pyproject.toml`、评估器测试纳入清单（F5、F6）；冻结哈希外部锚定；冻结后由人用文件系统权限锁定。
6. **L2-1 paper 制备边界**：只把复位算作制备（或统一用全局首个数据双比特门层）。

## 5. 可以接受、写进文档的局限

- 电路级距离只是上界（已写）；补充：冗余 / 复合 detector 会让 graphlike 与 stim_search 失明，此时只剩 BP-OSD（D1）。
  可考虑 L0 拒绝“在 detector 张成里多余”的 detector，或在算距离前把 detector 约化成一组基。
- 冗余校验行可以不测（L0-2）——**前提是 PI 明确接受这一口径**并写进任务定义；否则按 §2 修。
- 距离判定与 seed / 预算有关、与 worker 数无关；L2 逐位复现只在同一 stim 版本与同类 CPU 上成立（已写）。
- `paper` 与 `diff`、`flat`、`noisy` 的分数不是同一个量，不能混排（已写）；修完 L2-1 后 paper 仍对流水电路不完全公平（已写）。
- L2 的批结果文件（`$TMPDIR/l2_*`）在运行期间可被同一用户的其他进程写入、没有完整性校验：评估器自身不需要改，但搜索程序必须在沙箱里运行
  （README §6.2 已列为缺失部分）。
- 哈希链挡不住整链重算（已写），需要外部锚点。

## 6. 复现命令汇总

```
cd research/audits/2026-10-02-evaluator-G1-scripts
uv run python a1_fake_rounds.py 3 3                 # A1，L0 全 PASS（约 20 s）
uv run python a1_fake_rounds.py 5 10 --l2           # A1，L0 + L2（约 10 min，3 worker）
uv run python a1b_fake_rounds_early_readout.py 5 10 --l2   # A1b
uv run python a_leaderboard.py                       # LB1–LB7（临时文件）
uv run python a_si1000_identity.py --direct 5        # N1
uv run python a_si1000_identity.py 5 5               # N2（报错即为复现）
uv run python a_l2_diff.py 25                        # L2-2
uv run python a_l2_identity_prep.py 5 5 --l2         # L2-1
uv run python a_l0_redundant_rows.py                 # L0-2
uv run python a_l2_repro.py                          # L2-3 / L2-4
uv run python a_freeze.py                            # F1–F6（临时项目副本）
uv run python a_dist_redundant_detectors.py 8 0      # D1（失败的攻击）
uv run python a_dist_seed.py                         # D2（失败的攻击）
```
