# E-017 · gross 码 morphing 电路 d_circ = 12 的可行性调研

- 日期：2026-10-08 / 执行者：experimenter / 代码基线：git 870d5a0（未提交改动只有他人的 `search/experiments/e011/six_anatomy.py`）/ 评估器未冻结（无 `evaluators/FROZEN`），只读使用 `evaluators/distance.py`、`evaluators/noise.py`
- 假设：H-004
- 问题：见 `experiments/E-017-gross-morphing-scoping.yaml`
- 事先预测（yaml，未改）：1) 能复现该电路，启发式上界 12（约六成）或 ≤11（约四成）；2) Strikis 扩展码 + Prop. 3 不能直接用于 morphing 电路，需要新的下界论证；E-015 的映射 + 精确枚举思路可能可推广，但 d=12 可能超出本机能力。
- 代码：`search/experiments/e017/`；原始结果：`results/E-017-gross-morphing-scoping/`

## 进行中（阶段记录，按时间）

- [阶段 0，文献] 已读 2605.21898v2 App. B/C（HTML 全文）、2407.16336v3 正文与 App. A/D、2604.09797v2 Sec. 2（Prop. 1）、2603.05481v2 App. H.2 末段；读了 Shaw 的公开仓库 `Mac-Shaw/morphing_qec_circuits` 的源码（只读，未运行）。CPU 预算用量约 0。
- [阶段 1，构造] `morph.py`：按 2407.16336 Table 2/4 独立实现 [[288,12,18]]（l=m=12，A=x³+y⁷+y²，B=y³+x+x²）的两轮 morphing 电路，三种同态 f_x/f_y/f_xy × 两种层序；探测器与可观测量由 Pauli 传播推导并断言（每个收缩稳定子恰在一个 F_j 收缩到正确基底的测量比特上；扩张算符的右侧支撑只落在同基底测量上）。**全部 6 种变体 × 两个基底 × R=1..4：无噪声下 detector 与 observable 全部确定**（64 shots 全 0，stim DEM 可生成）。
- [阶段 1，码] `endcycle.py`（CP-SAT，4 线程，约 25 分钟，≈1.7 CPU h）：end-cycle 码 n=144、k=12、两种校验权重均为 9；最小稳定子权重：找到 9，**证明下界 X ≥ 8、Z ≥ 7**；gross 码最小稳定子权重 = 6（OPTIMAL）。⇒ **morphing 的 [[144,12,12]] 与 gross 码不等价**（比特置换 / 局部 Clifford 保持稳定子权重）。end-cycle 码距离：找到 12（300 s 内未证明，界 10/9；2407.16336 用 Gurobi 报 12）。
- [阶段 2，单轮实例] `oneround.py`/`project.py`：1 个含噪轮（sd6 只放在该轮 8 层）夹在无噪声轮之间（2604.09797 Prop. 1：两轮 morphing 电路 d_circ(T)=d_circ(1)）。DEM 6336 列、432 探测器；投影到记忆基底探测器 + 可观测量后**合并为 864 列（列权重 3–5）；有效行（度 > 0）144 行**。
- 累计 CPU 约 1.8 h。
- [阶段 3，评估器上界] `ub.py --oneround --basis Z --seed 0`（默认 1500 次 BP-OSD + LNS，4 进程，803 s，≈0.87 CPU h）：只找到 **17**（注入验证通过）。评估器的启发式在这个实例上很弱，不能用来回答“12 还是更小”。
- [阶段 4，精确 DFS] `dfs_inst.py` + `dfsw.c`（E-014 `dfs128.c` 的多字移植，算法不变）：单轮投影实例（记忆基底探测器 + 12 个可观测量，CSS 松弛）144 行 × 864 列，平移群 |K| = 72（逐列验证，含可观测量的线性变换 M 可逆），12 个轨道各 72 列。
  **W = 11：两个基底 × 12 个情形共 24 个任务全部完成，0 解**（Z：约 3.4×10¹⁰ 节点；X：约 3.3×10¹⁰ 节点；合计约 1400 CPU s）。输出 `results/.../dfs/out_x_{X,Z}_W11_c*.txt`。
- [阶段 4，见证] end-cycle 码用同一 DFS（72 行 × 144 列，2 个轨道）：**两种 end-cycle 码、两种类型，W=11 无解、W=12 有解 ⇒ end-cycle 码距离精确为 12**（`dfs/ec_dfs.txt`）。把 W=12 的解作为“复位层空闲故障”注入无噪声记忆电路：**R = 1..6 × 每个轮次位置 × 两个基底，42/42 个注入全部“0 个 detector、翻转 observable”** → d_circ ≤ 12（`witness_endcycle.json`）。这些见证映射到单轮投影实例的 12 列，异或为 0、可观测量非零（另行核对）。
- （一次浪费：用 CP-SAT 找 end-cycle 码权重 12 逻辑算子两次超时，约 0.7 CPU h。）
- 累计 CPU 约 3.9 h。
- [阶段 4，阳性对照] 单轮实例 W=12：X 基底情形 1 在 308 s 内找到权重 12 的解（`dfs/posctl_X_W12_c1.txt`）；Z 基底情形 0 在 20 分钟限时内未找到（`posctl_Z_W12_c0.txt`，exit 142 = 限时到；不是反例，Z 的见证列已单独核对）。移植核对：`dfsw` 在 E-014 的 X 实例上 W=10 情形 10、情形 5 的节点数与 E-014 原输出逐个相同（1907656、578463265）。
- [阶段 5，真实边界] 全噪声记忆电路（初始化与末端读出都含噪声，即评估器口径）R=1：144 行 × 864 列；R=2：216 行 × 1584 列、22 个轨道。**W = 11 全部情形完成，0 解**（R=1：24 个任务约 5.7×10¹⁰ 节点；R=2：44 个任务约 2.0×10¹¹ 节点，5637 CPU s）。
- f_y、f_xy 两种同态的单轮实例已生成（`dfs/inst_{y,xy}_{X,Z}.txt`，同样 144×864、12 个轨道），**未运行**（预算）。
- 累计 CPU 约 6.0 h（75%），停止计算，写日志。

## 复现命令

```
uv run python -m search.experiments.e017.endcycle                          # end-cycle 码参数、最小稳定子权重（CP-SAT）
uv run python -m search.experiments.e017.ub --oneround --basis Z --seed 0 --out results/E-017-gross-morphing-scoping/ub/one_x_Z_s0.json
D=results/E-017-gross-morphing-scoping/dfs; cc -O3 -march=native -o $D/dfsw search/experiments/e017/dfsw.c
uv run python -m search.experiments.e017.dfs_inst --basis {Z,X} [--full_rounds {1,2}] --out $D/inst_<tag>_{Z,X}.txt
NPAR=4 $D/run_jobs.sh $D/jobs_<tag>_W11.txt <tag> 11                     # tag = x（单轮夹心）| full1 | full2
uv run python -m search.experiments.e017.code_inst --j {0,1} --P {X,Z} --out $D/ec_j<j>_<P>.txt   # end-cycle 码 DFS
uv run python -m search.experiments.e017.witness --out results/E-017-gross-morphing-scoping/witness_endcycle.json
uv run python -m search.experiments.e017.posctl {Z,X}
```

## 1. 那个电路到底是什么（文献精读）

**IBM 2605.21898 v2（Wills, Beverland, Bishop, Gambetta 等）App. C 的全部信息**：只有一段文字和 Table 5。原话大意：考虑一个“用于空闲 gross 码的新电路”，“由 Shaw–Terhal morphing [68] 构造”，“被认为（believed）电路距离为 12，与码距离一致”，而常规电路是 10。证据**只有直接 Monte Carlo**：12 轮、按轮归一，p = 10⁻³（噪声沿用 [86] = Tour de gross 2506.03094 的均匀电路噪声），Relay-BP（S = 20，γ = (−0.09, 0.76)，按“平均解码时间最快”选参），逻辑错误率每轮 4.4×10⁻¹¹（95% 区间 9.2×10⁻¹²–1.3×10⁻¹⁰）。**没有给出电路、码的多项式、比特数、深度，也没有任何距离搜索或证明**；还说现有辅助系统（LPU 等）“容纳不了这个新空闲电路，需要重新设计”。引用的 morphing 文献只有 [68] = 2407.16336。

**唯一公开的具体构造（Shaw–Terhal 2407.16336 v3 Table I、Table 2/4、App. D）**：
- mid-cycle 码 C = two-gross BB 码 [[288,12,18]]（l = m = 12，A = x³ + y⁷ + y²，B = y³ + x + x²），288 个比特全部是“数据”，**没有额外辅助比特**；
- 同态 f（f_x、f_y、f_xy 三种都满足 Criterion 1），K = ker f（|K| = 72）；两个收缩电路 F₁、F₂ 各 3 层 CNOT（具体见 `morph.py` 文档串与 Table 4）；
- 一个测量轮 = 复位上一轮测过的 144 个右比特（X 或 Z 基）→ F_{j'}† 的 3 层 → F_j 的 3 层 → 测量全部 144 个右比特（偶 X、奇 Z，按陪集）。**CNOT 深度 6，每轮 864 个 CNOT，每轮测量全部 144 个右比特**；
- 每轮测量的稳定子：S_j = 一半 X 稳定子（一个陪集）+ 一半 Z 稳定子（另一个陪集）被收缩到单比特上测量；另一半在下一轮测。end-cycle 视角：左 144 比特是 end-cycle 码的数据，右 144 比特相当于辅助比特；每轮 144 次测量 = 72 个 X 型 + 72 个 Z 型收缩稳定子，两轮合起来覆盖全部 288 个 mid-cycle 稳定子；end-cycle 码有 72 + 72 个权重 9 的生成元（各秩 66）；
- end-cycle 码是 [[144,12,12]]，校验权重 9（2BGA，Ã 权重 4、B̃ 权重 5，App. D.2），连接度 5（双平面）。Shaw–Terhal 称之为“第二个 gross 码”。C̃₁ 与 C̃₂ 相差一个平移；
- 他们的 d_circ 只是**上界**：Table I 写 ≤ 12，方法是两轮记忆实验 + BP-OSD（App. A）。
- Strikis 2603.05481 v2 App. H.2 末段也把它描述为“比特数、逻辑比特数与 gross 相同，电路距离 12”的另一种电路。

**与 gross 码本身的关系（本实验计算）**：end-cycle 码的最小稳定子权重：X ≥ 8、Z ≥ 7（CP-SAT 证明；找到 9，与 2407.16336 App. D.1 的 9 一致）；gross 码有权重 6 的稳定子（OPTIMAL）。比特置换或局部 Clifford 等价保持稳定子权重分布，所以 **morphing 的 [[144,12,12]] 与 gross 码不等价**。两者的共同点只是参数 [[144,12,12]]、总比特数 288、每轮 864 个 CNOT。
**IBM 文中“gross 码的新空闲电路”到底是哪一个，原文无法判定**：唯一已发表的同参数 morphing 电路作用在这个不等价的码上；如果 IBM 另有一个以 gross 码本身为 end-cycle 码的 morphing 构造，它没有公开。我倾向于认为 IBM 说的就是 Shaw–Terhal 这个电路、措辞不严（证据：只引 [68]；“需要重新设计辅助系统”），但这是推断，**未核实**，建议 lit-scout 向作者或后续版本确认。

## 2. 构造

- `morph.py` 从论文 Table 2/4 独立实现，并与公开仓库 `bb_params.get_standard_morphing_specification` 的门序逐行对照（只读未运行）：仓库在第 0 层用 b₂/a₂、第 1 层用 b₃/a₃，与论文表的顺序相反，两者都是合法的“列表顺序”约定；默认采用仓库顺序，`swap23=True` 为论文表顺序。
- 评估器模板（每校验一个辅助比特）装不下，所以直接写 stim；噪声用评估器 `add_noise(..., "sd6", p)`（CNOT 后 DEPOLARIZE2、复位后翻转、测量前翻转、每层空闲 DEPOLARIZE1）。论文 2407.16336 的 Fig. 3/4 也是均匀电路去极化（其仓库的 setup 含空闲噪声），IBM 用 [86] 的均匀噪声；数值不同但故障位置集合相同，距离不受 p 影响。
- 无噪声检查：6 种变体 × 2 基底 × R = 1..4，detector 与 observable 全部确定。连接度 5（3 种同态都是）。
- 复现论文数字：end-cycle 码 [[144,12,12]]（距离由 DFS **精确**定为 12，两种 end-cycle 码、两种类型）、校验权重 9、最小稳定子权重 9（我们给出 ≥7/≥8 的下界）、连接度 5、Table I 的 d̃_circ ≤ 12。**逻辑错误率没有复现**（IBM 4.4×10⁻¹¹/轮需要远超预算的采样；评估器的 BP-OSD 在 gross 规模约 5 CPU s/shot）。

## 3. 上界

| 方法 | 实例 | 结果 |
|---|---|---|
| 评估器 `upper_bound`（graphlike + 1500 次 BP-OSD + LNS 96 起点，seed 0，4 进程） | 单轮夹心，Z | **17**（注入验证通过；803 s）。只跑了这一个种子 / 基底：太贵且太弱，没有继续 |
| end-cycle 逻辑算子注入（复位层空闲故障 12 个） | 全噪声记忆，R = 1..6，每个轮位置，两个基底 | **12**，42/42 注入验证通过（`witness_endcycle.json`） |
| 精确 DFS，W = 11（找任何 ≤ 11 的不可检测逻辑错误） | 单轮夹心（投影），X/Z | 0 解（24 个任务全部完成） |
| 同上 | 全噪声 R = 1（投影），X/Z | 0 解（24/24） |
| 同上 | 全噪声 R = 2（投影），X/Z | 0 解（44/44） |

**上界是 12，不是 ≤ 11**：在上表的实例里，穷举（不是启发式）证明不存在权重 ≤ 11 的不可检测逻辑错误。注意投影实例只保留记忆基底的探测器（CSS 松弛），所以“投影上无解”严格蕴含“原电路无解”；阳性对照（W = 12 找到解；已知见证的 12 列异或为 0）说明不是程序空转。

## 4. 下界路线

- **Strikis 扩展码 + Prop. 3 不适用**：Prop. 3 要求每个校验有自己的辅助比特、辅助比特只当 CNOT 目标/控制的一侧；morphing 电路没有独立辅助比特，右比特既是 mid-cycle 码的数据又被测量，CNOT 双向（第 3 层右→左与左→右并存）。
- **可行的替代（本实验已基本走通）**：Shaw–Terhal 2604.09797 v2 Prop. 1：两轮 morphing 电路在理想初态/读出的记忆实验中 d_circ(T) = d_circ(1)（证明：时间反演“折叠”，App. B）。它需要故障集合在时间反演下对称；sd6 下逐项核对：CNOT 后的两比特 Pauli ↔ 镜像 CNOT 前的两比特 Pauli（经 CNOT 共轭仍是该门上的两比特 Pauli）、复位翻转 ↔ 测量翻转、两轮的空闲位置相同（复位层与测量层都只有左比特空闲）——对称成立（论证，未另行计算）。于是只需在**一个**含噪轮上精确求最小逻辑错误，这就是一个“morphing 扩展码”（投影后 144 行 × 864 列，比 E-014 的 72 × 360 大一倍），用 E-014 的 DFS + 72 元平移群，**W = 11 每个基底约 700 CPU s**。
- 结论（待复核）：在“理想初态/读出 + Prop. 1”的口径下，f_x、仓库层序的 Shaw–Terhal 电路 **d_circ = 12（任意 T）**；在评估器口径（含噪初态/读出）下 R = 1、2 已穷举确认 ≥ 12，任意 R 还需要一个 E-015 B7 式的边界论证（中间轮用 Prop. 1 的折叠，边界轮要单独处理），或继续算 R = 3（Z 侧 288 行，在 `dfsw` 的 320 位以内；按 R=1→2 的增长约 3–5 CPU h）。
- 其它路线的粗估（没有必要再走）：E-015 `ibm_lift` 式“映射到 mid-cycle 码低权逻辑再枚举”——要求先枚举 mid-cycle 码 [[288,12,18]] 或 end-cycle 码的一批低权逻辑算子再做受限搜索；这里扩展码本身已小到可以直接穷举，这条路没有优势（未估算）；直接对 12 轮 DEM 用 CP-SAT/MaxSAT——评估器文档已记 gross 规模下界证明不可行，本实验 CP-SAT 连 144 比特 end-cycle 码的距离都 300 s 证不出来。

## 与预测对比

1. 预测“能复现，评估器启发式上界 12（约六成）或 ≤ 11（约四成）”：**电路复现成功；上界 12，符合较高的那一支**。但“评估器启发式上界”这一半不符合：评估器只给出 17，12 来自构造的见证，≤ 11 的排除来自穷举 DFS。
2. 预测“Prop. 3 不能直接用（符合）；需要新的下界论证（符合）；E-015 思路可能可推广但 d = 12 可能超出本机能力”：**后半不符合**。可推广的不是 `ibm_lift`，而是“Prop. 1 + 单轮扩展码 + E-014 DFS”；计算量很小（每个变体、每个基底约 0.1–0.2 CPU h；R = 2 全噪声约 1.6 CPU h）。

## 异常与疑点

- 评估器 `upper_bound` 在这个电路上很弱（17 vs 12）。可能原因：DEM 6336 列、mid-cycle 码 d = 18、BP-OSD 低阶。这对评估器在 morphing / 非模板电路上的可用性是个提醒（不是 bug）。
- R=1 的全噪声实例与单轮夹心实例行列数完全相同、DFS 节点数只差约 0.3%，说明边界的影响很小，符合预期。
- 只验证了 f_x + 仓库层序一种变体；f_y、f_xy、论文层序（swap23）四个实例已生成但未运行（每个约 0.4 CPU h 两基底）。IBM 用的是哪一个未知。
- 阳性对照 Z 侧 20 分钟没找到解（X 侧找到）；Z 的见证已通过“12 列异或为 0、可观测量非零”和注入两种方式核对。
- 所有“0 解”都依赖 DFS 算法本身（E-013/E-014 已经 auditor 复核）和本实验的多字移植（与 E-014 节点数逐个相同）。

## 结论

IBM 说的“d_circ 可能为 12 的 morphing 电路”唯一公开的具体形式是 Shaw–Terhal 由 [[288,12,18]] 得到的电路，它作用在**另一个、与 gross 不等价**的 [[144,12,12]] 上；本实验构造了它，上界 12（注入验证），并用“Prop. 1 + 单轮扩展码 + 穷举 DFS”在本机约 1 CPU h 内排除了权重 ≤ 11 的逻辑错误（单轮、R=1、R=2 三种实例，两个基底）——**下界路线可行，接近定理**。值得做下去，但要先由 auditor 独立复核，并补齐：其它同态 / 层序变体、任意 R 的边界论证、IBM 电路身份的确认。**需要 auditor 复核**。

## 复核后更正（lead，2026-10-08，依据 research/audits/2026-10-08-E-017.md）

- auditor 结论：四项主张全部 CONFIRMED；E-017 已移入 STATE“已确认结果”第 6 条。
- 更正 1（中）：上文“对称成立（论证，未另行计算）”只是论证；原文逐故障的“同探测器、同可观测量”在一般探测器基底下不成立。正确的、无基底依赖的折叠条件已由 auditor 计算核对（T=2..5、两基底、含噪末轮）。写作时引用该核对。
- 更正 2（低）：单轮 W=11 节点数应为 Z 2.82e10 / X 2.87e10（输出文件之和），不是约 3.4e10 / 3.3e10。
- 更正 3（低）：lead 的 Z 基底 W=12 阳性对照只搜了 case 0 并超时；auditor 在 case 1 找到见证（150 s），Z 侧对照由 auditor 补齐。
