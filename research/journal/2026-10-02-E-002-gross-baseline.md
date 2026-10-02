# E-002-gross-baseline
- 日期：2026-10-02
- git commit：bd12d82（代码 `baselines/{bb_code,schedule,circuit,gross,circuit_distance}.py` 尚未提交，由 lead 统一提交）
- 评估器哈希：不适用（`evaluators/FROZEN` 不存在，评估器未冻结；本实验不经评估器）
- 假设：H-001（对照基线）
- 问题：复现 IBM gross code [[144,12,12]] 的标准 syndrome 提取电路（Bravyi et al., arXiv:2308.07915, Table 5），得到电路级距离和逻辑错误率，作为调度搜索的对照基线。
- 事先预测（yaml，跑前写）：码参数 [[144,12,12]]；d_circ ≤ 10；无噪声下 detector 全部确定；p=3e-3~6e-3 的逻辑错误率可测，量级与原论文一致。
- 复现命令：
  - 全流程：`uv run python -m baselines.gross --config experiments/E-002-gross-baseline.yaml`（stage 依次为 verify / smoke / distance / sample / analyze）
  - 本次实际是分 stage 跑的，p=0.003 因预算用了 `--stage sample --p 0.003 --max-shots 16000`（见“异常与疑点”）
  - 距离见证：`uv run python -m baselines.circuit_distance --config experiments/E-002-gross-baseline.yaml --rounds 3 --basis X --witness-weight 10`

## 实现要点
- 码：x = S_ℓ⊗I_m，y = I_ℓ⊗S_m；A1..A3 = x³, y, y²；B1..B3 = y³, x, x²；HX=[A|B]，HZ=[Bᵀ|Aᵀ]。
- 调度是数据结构 `Schedule`（每层：CNOT 对列表 + prep_x/prep_z/meas_x/meas_z），和电路生成器 `memory_circuit` 分开。`Schedule.validate` 检查：同层比特不重复、X 辅助只当控制、Z 辅助只当目标、每个检查每 cycle 恰好一次 prep 和一次 meas、prep→meas 窗口内的 CNOT 正好覆盖该检查的支撑。X/Z 交错是否对易不在这里查，交给电路级的 determinism 检查（负对照能抓住，见下）。
- IBM 调度：`bb_term_schedule(code, sX, sZ)`，sX = [–, A2, B2, B1, B3, A1, A3]，sZ = [A1ᵀ, A3ᵀ, B1ᵀ, B2ᵀ, B3ᵀ, A2ᵀ, –]，和论文 Table 5 逐 round 一致，也和 IBM 仓库 `decoder_setup.py` 的 `sX=['idle',1,4,3,5,0,2]`、`sZ=[3,5,0,1,2,4,'idle']` 一致。注意：仓库里 Z 检查方向的编号是 [B1,B2,B3,A1,A2,A3]，本实现两类检查统一用 [A1,A2,A3,B1,B2,B3] 编号，所以 sZ 的数字写成了 [0,2,3,4,5,1,None]。第一次实现时我按统一编号直接抄了仓库的 sZ 数字，`validate` 立刻报出“同层比特重复”，修正后通过。
- **命名**：yaml 里的 `ibm_depth8` 和论文是同一个电路。论文的叫法是 7 层 CNOT（“depth-7”），算上 init/meas 共 8 个 round（Table 5 标题是 “Depth-8”）；第一个 cycle 前另加一层 Z 辅助初始化，所以总深度为 8N_c+1。本实现 12 cycle 电路有 97 个 TICK，与此相符。
- 位置：X 辅助 0–71，L 数据 72–143，R 数据 144–215，Z 辅助 216–287（和仓库的 lin_order 相同）。
- 记忆实验：**Z 基底和 X 基底两个都跑了**。Z 基底：数据初始化在 |0⟩，末尾 Z 测量，detector 只放 Z 检查（每 cycle 一个，加上末尾由数据读出构成的一组），observable 是 12 个逻辑 Z。X 基底对称。只放同基底的 detector，对应论文“X、Z 分开译码”的做法。12 cycle 的 DEM 有 936 个 detector、8784 个错误机制；论文 §6 报告的 D_X/D_Z 列数是 8857/8785，基本吻合。
- 噪声（`uniform_depolarizing`，日志原文）：每个 CX 后 DEPOLARIZE2(p)；R 后 X_ERROR(p)，RX 后 Z_ERROR(p)；测量结果以概率 p 翻转（stim 的 `M(p)`/`MX(p)`）；每层中没被操作的比特加 DEPOLARIZE1(p)。在 IBM 调度里只有数据比特会 idle，每 cycle 288 个 idle 位置（= 2n，和论文 §6 一致），辅助比特没有 idle 位置。初始数据制备和末尾数据读出同样带噪声。**收尾不加无噪声 cycle**（论文写 1 个、仓库实际 2 个，本实现两者都不用），末尾用带噪声的直接数据测量，再加上数据读出构成的 detector。
- 解码：stimbposd + ldpc 2.4.1，设置照 IBM 仓库 `decoder_run.py`：`bp_method=min_sum, max_bp_iters=10000, ms_scaling_factor=0, osd_method=osd_cs, osd_order=7`。sinter 的 num_workers 为 5。
- 每轮换算：pL = 1 − (1 − PL(N_c))^(1/N_c)，N_c = 12（论文 §3 的定义）。X、Z 合并：PL_comb = 1 − (1 − PL_Z)(1 − PL_X)，即任一基底失败就算失败，并假设两者独立。这对应仓库“X、Z 都译对才算成功”的口径。合并后的置信区间用两侧端点直接组合（保守）。单基底 CI 为 Clopper–Pearson 95%。

## 结果

### 码参数与合法性（`results/E-002-gross-baseline/verify.json`）
| 项 | 结果 |
|---|---|
| n | 144 |
| rank_GF2(HX), rank_GF2(HZ) | 66, 66 |
| k = n − rank HX − rank HZ | **12** |
| HX·HZᵀ = 0 | 是 |
| 行重 / 列重 | 6 / 3（每个数据比特 3 X + 3 Z） |
| 逻辑算符配对矩阵 LX·LZᵀ 的秩 | 12 |
| 码距上界（BP-OSD，论文 Eq.(11)，200 次随机） | **12**（200 次中 117 次取到 12，未出现 <12） |
| 调度 validate | 通过；8 层，其中 7 层有 CNOT；每 cycle 864 个 CNOT（=6n） |
| 无噪声 determinism（Z/X 基底，1/2/3/12 轮，两类 detector 全开） | detector 与 observable 翻转数均为 0；`detector_error_model()` 没有报非确定 |
| 负对照（X 顺序中 A1、A2 对调，其余不变） | stim 报 “non-deterministic detectors”，说明检查能抓住非法交错 |

### 电路级距离（`circuit_distance.json`、`circuit_distance_witness_X_r3.json`）
| 方法 | 设置 | Z 基底（X 型逻辑错误） | X 基底（Z 型逻辑错误） |
|---|---|---|---|
| stim `search_for_undetectable_logical_errors` | 1/2/3 轮，(degree≤3, set≤4) 与 (degree≤4, set≤4) | 12 | 12 |
| BP-OSD 随机 η（论文 Eq.(12)），单位权重 | 1 轮，2000 次 | 11 | 12 |
| 同上 | 2 轮，2000 次 | 11 | 11 |
| 同上 | 3 轮，2000 次 | 11 | **10** |
| 同上 | 12 轮，500 次 | 11 | 11 |
| HiGHS MILP（精确法，带时限） | Z 基底，1 轮，observable 0，120 s | 上界 12，下界 4（没解出来） | – |

**d_circ ≤ 10**（全部方法取最小）。见证文件给出一组 10 个故障：8 个数据比特初始化 Z 错误，加 2 个 CNOT 故障。后者是 tick 2 时 Z 辅助比特（目标）上的 Z 分量，会沿后续 CNOT 反向扩散到数据比特。`D·ξ=0` 和 `L·ξ≠0` 已断言通过，翻转的逻辑算符是 {1,3,6,8,11}。8 个初始化错误在体内等价于上一 cycle round 8 的 idle Z 错误，所以我认为它不是边界造出来的假象，但没有专门验证。stim 的受限搜索只给出 12，是因为剪枝太强。(degree≤4, set≤6) 在 1 轮上 1 分钟内 RSS 就超过 4.5 GB，被我终止（`distance_attempt1_killed_oom.log`）。

### 逻辑错误率（12 cycles，`stats.csv`、`summary.json`，图 `pL_vs_p.png`）
| p | 基底 | 错误 / shots | PL(12) [95% CI] | 每轮 pL [95% CI] |
|---|---|---|---|---|
| 0.003 | Z | 36 / 16000 | 2.25e-3 [1.58e-3, 3.11e-3] | 1.88e-4 [1.31e-4, 2.60e-4] |
| 0.003 | X | 28 / 16000 | 1.75e-3 [1.16e-3, 2.53e-3] | 1.46e-4 [9.7e-5, 2.11e-4] |
| 0.004 | Z | 117 / 6157 | 1.90e-2 [1.57e-2, 2.27e-2] | 1.60e-3 [1.32e-3, 1.91e-3] |
| 0.004 | X | 116 / 5592 | 2.07e-2 [1.72e-2, 2.48e-2] | 1.75e-3 [1.44e-3, 2.09e-3] |
| 0.005 | Z | 113 / 997 | 0.113 [0.094, 0.135] | 9.97e-3 [8.22e-3, 1.20e-2] |
| 0.005 | X | 108 / 1125 | 0.096 [0.079, 0.115] | 8.38e-3 [6.87e-3, 1.01e-2] |
| 0.006 | Z | 118 / 324 | 0.364 [0.312, 0.419] | 3.70e-2 [3.06e-2, 4.43e-2] |
| 0.006 | X | 108 / 316 | 0.342 [0.290, 0.397] | 3.43e-2 [2.81e-2, 4.13e-2] |

X+Z 合并，并和论文对比。论文值用 Table 6 的拟合 pL = p⁵·exp(18.04 + 1337p − 96007p²) 计算，arXiv:2308.07915：
| p | 合并 PL(12) | 合并每轮 pL [保守 95% CI] | 论文拟合 pL | 本实验 / 论文 |
|---|---|---|---|---|
| 0.003 | 4.0e-3 | 3.34e-4 [2.28e-4, 4.71e-4] | 3.86e-4 | 0.86 |
| 0.004 | 3.94e-2 | 3.34e-3 [2.76e-3, 4.00e-3] | 3.17e-3 | 1.06 |
| 0.005 | 0.198 | 1.83e-2 [1.50e-2, 2.20e-2] | 1.55e-2 | 1.18 |
| 0.006 | 0.581 | 7.00e-2 [5.79e-2, 8.37e-2] | 5.11e-2 | 1.37 |

伪阈值顺带核对：p=0.006 时 12p = 0.072，本实验 pL = 0.070，所以伪阈值约 0.006；论文 Table 1 为 0.0065。

### CPU 用量（预算 4 CPU 小时 = 14400 s）
解码 10750 s（sinter 记录，含第一次挂起前采到的点）。其余约 2500 s，均为估计：解码器参数基准约 900 s、距离搜索约 1300 s、HiGHS 120 s、见证 133 s、verify/smoke 约 60 s。**合计约 13250 s ≈ 3.7 CPU 小时**，在预算内。

## 与预测对比
- 码参数 [[144,12,12]]：**符合**（n、k 精确；d 只有 BP-OSD 给出的上界 12，没有证明下界）。
- d_circ ≤ 10：**符合**，找到了 10 个故障的不可检测逻辑错误。只能说是上界；论文猜想恰好为 10，本实验没有给出下界。
- 无噪声下 detector 确定：**符合**。
- 量级与论文一致：**符合**。p=0.003–0.005 时合并每轮 pL 是论文拟合值的 0.86–1.18 倍，论文值都落在或贴近本实验的 95% CI 内。p=0.006 时偏高 1.37 倍，论文值 5.11e-2 在本实验 CI [5.79e-2, 8.37e-2] 之外。

## 异常与疑点
1. **p=0.006 比论文高约 37%，并且显著。** 可能原因：(a) 这个点 PL(12)=0.58，已接近饱和（多逻辑比特随机化时 PL 趋于 1），换算到每轮对 PL 很敏感，独立假设下的合并也在这里误差最大；(b) 噪声口径细节不同：本实现初始数据制备和末尾读出都带噪声，论文/仓库收尾加了 1–2 个无噪声 cycle，仓库的采样还是在线性化（X/Z 分开）噪声模型上做的，而本实现在 stim 里做完整的 Pauli 传播，Y 关联保留在采样里、只在译码时丢掉；(c) 论文拟合在高 p 端本身也有偏差（c2 很大）。我没有逐项拆分这些原因。
2. **p=0.003 没有达到停止规则（≥100 错误或 1e5 shots）**：每个基底只有 16000 shots，Z 36 次、X 28 次错误，相对误差约 ±17–19%。原因是预算：按论文解码器设置（10000 次 BP 迭代）跑到 100 个错误，大约要再花 2 × 2000 CPU 秒，会超出 4 CPU 小时。这个点作为基线用时，误差棒比其它点大。
3. **采样第一次挂起**：第一次 sample 的 X p=0.006 任务中，5 个 sinter worker 变成僵尸进程，主进程空等了约 20 分钟（`sample_attempt1_hung.log`）。时间上和我用 `pkill -f "uv run python -$"` 终止解码器基准脚本的时刻重合，我怀疑是这次 pkill 误伤。之后用 sinter 的 resume 续跑，已采数据没有丢。**另外，在停 p=0.004→0.003 时我执行过一次 `pkill -f "multiprocessing.spawn"`，这会杀掉本机所有 multiprocessing spawn 子进程，可能误伤了同时在跑的其它任务的 worker（例如别的 experimenter/auditor 的 sinter 进程）。请 lead 检查并行任务是否有异常中断。**
4. `sample.log`（attempt2）里每个点打印的 shots/errors 都错误地重复了第一个点的数字：sinter.collect 会把 CSV 里其它任务的 resume 数据一并返回，我取了 `st[0]`。这只是日志 bug，CSV 里的原始数据是对的；`summary.json` 直接读 CSV，不受影响。已修复（按 json_metadata 选取）。同一个 bug 让预算守卫算多了，没有触发误停。
5. 解码器参数基准（各 300 shots，p=0.005，12 轮，Z 基底）：仓库设置（ms，10000 次迭代，scaling 0）34 次失败、512 ms/shot；scaling 0.625 时 41 次、1517 ms/shot；1000 次迭代时 37 次、138 ms/shot；product-sum 100 次迭代时 35 次、166 ms/shot。几种设置在统计上分不出差别，正式运行用仓库设置。`ms_scaling_factor=0` 在 ldpc 2.x 里的确切语义（v1 里是自适应缩放）我没在源码中核实；从结果看它不比 0.625 差。这个基准没有保存为文件，数字只在这里。
6. ILP 精确距离没跑出来（1 轮 120 s 内下界只有 4），对 d_circ 没有贡献，记在这里以免以后重复。
7. 距离见证依赖时间边界上的初始化错误（见上节），在体内是否同样可达未单独验证。12 轮的 BP-OSD 只试了 500 次，最小 11。

## 结论
IBM [[144,12,12]] 调度复现成功：码参数精确，d_circ ≤ 10 与论文一致，p=0.003–0.005 的每轮逻辑错误率与论文拟合相差在 ±20% 内，p=0.006 偏高 37%，原因未拆分。可以作为 G0 的 gross code baseline 候选。建议 auditor 复核：p=0.006 的偏差，以及 p=0.003 点的统计量。
