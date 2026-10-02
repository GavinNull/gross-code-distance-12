# Gross code [[144,12,12]] baseline：IBM 原文与公开代码提取
检索日期：2026-10-02；检索词：arXiv 2308.07915 全文（本地 pdftotext 读取 v2，21 Feb 2024）；GitHub sbravyi/BivariateBicycleCodes（只读，WebFetch 查看 raw 文件，未下载、未执行任何代码）。
编号约定：「论文」= arXiv:2308.07915v2；章节、表号用 v2 的。图号注意：v2 的逻辑错误率图是 Fig. 2；GitHub README 写"Figure 3"（Nature 版编号，Nature 版图号未核实）。
可信度说明：论文内容我直接读了全文文本。GitHub 代码是经 WebFetch 摘要工具转述的，我已把其中的 sX/sZ 调度与论文 Table 5 逐轮对照，一致（见 §3.3）；但摘要工具可能漏行，实现者请直接对照仓库 raw 文件 `decoder_setup.py`。

## 结论（3-5 行）
- IBM 调度是 7 层 CNOT（论文称 depth-7；含 init/meas 为 8 个 round，Table 5 标题叫 depth-8），电路级距离只有 d_circ ≤ 10（Table 1，论文推测 =10），不是 12；936 个深度-7 变体全部 ≤10（§5）。
- 论文报告的 [[144,12,12]]：p=1e-3 时 pL=2e-7，p=1e-4 时 8e-13（外推，非直接模拟），pseudo-threshold 0.0065（Table 1）。噪声为标准电路级去极化，BP-OSD min-sum、10000 次迭代、combination sweep OSD（§6、§8）。
- 官方仓库公开：github.com/sbravyi/BivariateBicycleCodes（Apache-2.0），电路构造在 `decoder_setup.py`，调度由 `sX=['idle',1,4,3,5,0,2]`、`sZ=[3,5,0,1,2,4,'idle']` 决定。
- 复现 baseline 时最容易错的点：口径（7 vs 8）、Z 辅助比特是 CNOT 目标/X 辅助比特是控制、最后加的无噪声 cycle 数（论文 1 个，仓库 2 个）、pL 用的是"每 cycle"定义且 N_c=d。

## 关键论文
| arXiv | 作者 · 年份 | 做了什么 | 与本项目关系 | 关键数字（附出处） |
|---|---|---|---|---|
| 2308.07915 | Bravyi, Cross, Gambetta, Maslov, Rall, Yoder · 2023（v2 2024-02）；Nature 627, 778-782 (2024) | BB 码、深度-7 单辅助比特调度、BP-OSD 电路级解码、Table 1 逻辑错误率 | 本项目 baseline 的唯一原始出处 | 见下各节 |
| 2603.05481 | Strikis, Browne, Beverland · 2026 | 证明非交错电路 d_circ≤11，给出 d_circ=11 猜想电路 | 直接影响 baseline 的"可超越空间"，详见 `novelty-schedule-search.md` | gross 码此前"没有 d_circ>10 的已知电路"（App. H 首句） |

## 1. 码的定义（论文 §4，Eq.(1)(2)，Table 3）
- 参数：ℓ=12, m=6，n = 2ℓm = 144 数据比特，k=12，d=12（Table 3）。k = 2·dim(ker A ∩ ker B)，n = 2ℓm（Lemma 1，Eq.(3)）。
- x = S_ℓ ⊗ I_m，y = I_ℓ ⊗ S_m。S_ℓ 的第 i 行在第 i+1 列（mod ℓ）为 1（§4）。x^ℓ = y^m = I，xy = yx。
- 多项式：A = x^3 + y + y^2，B = y^3 + x + x^2（Table 3，[[144,12,12]] 行）。
- A = A1+A2+A3，B = B1+B2+B3，每一项都是 x 或 y 的幂（Eq.(1)）。对 gross code：A1=x^3, A2=y, A3=y^2；B1=y^3, B2=x, B3=x^2。这一指派来自仓库 `decoder_setup.py`（`A1=x[a1]; A2=y[a2]; A3=y[a3]; B1=y[b1]; B2=x[b2]; B3=x[b3]`，a=(3,1,2)，b=(3,1,2)），论文 Table 5 的 A_i、B_j 与之一致。
- 校验矩阵：HX = [A | B]，HZ = [B^T | A^T]，均为 (n/2)×n = 72×144（Eq.(2)）。每个检查权重 6，每个数据比特参与 6 个检查（3 X + 3 Z），Tanner 图度 6、厚度 ≤2（§4，Lemma 2）。
- 索引约定（§4）：数据比特分左右两块 L、R，各 ℓm=72 个；比特和检查可用单项式 x^a y^b 标号，索引 i∈Z_{ℓm}，对应 x^{a_i} y^{i−m·a_i}，a_i=floor(i/m)。仓库实现等价：`x[i]=kron(roll(I_ell,i,axis=1), I_m)`，`y[i]=kron(I_ell, roll(I_m,i,axis=1))`。
- X 检查 i 作用在 q(L, A_p(i)) 和 q(R, B_p(i))，p=1,2,3；Z 检查 i 作用在 q(L, B_p^T(i)) 和 q(R, A_p^T(i))（§5）。其中 j=A1(i) 表示矩阵 A1 在第 i 行第 j 列为 1；j=A1^T(i) 表示 A1^T 在第 i 行第 j 列为 1（§5）。
- 其他码的 (ℓ,m,A,B) 见论文 Table 3；仓库 `decoder_setup.py` 注释里给出 (a1..a3, b1..b3) 形式：[[72,12,6]] ℓ,m=6,6 a=3,1,2 b=3,1,2；[[288,12,18]] 12,12 a=3,2,7 b=3,1,2 等。

## 2. 比特寄存器与总数（§3、§5）
- 4 个寄存器各 n/2=72 个比特：q(X)（X 检查辅助）、q(L)、q(R)（数据）、q(Z)（Z 检查辅助）。总物理比特 2n=288（144 数据 + 72 X 辅助 + 72 Z 辅助）。
- 每 cycle 的操作数（§6）：6nN_c 个 CNOT（即每 cycle 864 个），nN_c 个 init+meas 位置，2nN_c 个 idle 位置（即每 cycle 288 个）。M=98nN_c 个单故障电路，98=15·6+1+1+3·2。
- 仓库线性序：Xcheck 0-71，data_left 72-143，data_right 144-215，Zcheck 216-287（`decoder_setup.py` `lin_order`）。

## 3. Syndrome 提取电路（§5，Table 5，Fig. 5，Eq.(9)；仓库 sX/sZ）

### 3.1 Table 5 逐 round（i 遍历 1..n/2，同一 round 内所有 i 并行，彼此不重叠）
记 CNOT(控制, 目标)。

| Round | X 辅助比特 q(X,i) | Z 辅助比特 q(Z,i) | 数据 idle |
|---|---|---|---|
| 1 | InitX（|+>） | CNOT( q(R, A1^T(i)) → q(Z,i) ) | q(L,i) idle |
| 2 | CNOT( q(X,i) → q(L, A2(i)) ) | CNOT( q(R, A3^T(i)) → q(Z,i) ) | 无 |
| 3 | CNOT( q(X,i) → q(R, B2(i)) ) | CNOT( q(L, B1^T(i)) → q(Z,i) ) | 无 |
| 4 | CNOT( q(X,i) → q(R, B1(i)) ) | CNOT( q(L, B2^T(i)) → q(Z,i) ) | 无 |
| 5 | CNOT( q(X,i) → q(R, B3(i)) ) | CNOT( q(L, B3^T(i)) → q(Z,i) ) | 无 |
| 6 | CNOT( q(X,i) → q(L, A1(i)) ) | CNOT( q(R, A2^T(i)) → q(Z,i) ) | 无 |
| 7 | CNOT( q(X,i) → q(L, A3(i)) ) | MeasZ | q(R,i) idle |
| 8 | MeasX | InitZ（为下一 cycle 的 round 1 准备） | q(L,i)、q(R,i) idle |

出处：论文 Table 5（逐行），Eq.(9)（用 CNOT_M(a,b) 记法给出同一调度的 7 个酉 round）。
- Z 辅助比特永远是 CNOT 目标；X 辅助比特永远是控制（§5）。X 型错误传到 q(Z) 并在 round 7 以 Z 基测量；Z 型错误传到 q(X)，在 round 8 以 X 基测量（§5）。
- X 辅助比特：round 1 初始化，round 2–7 做 6 个 CNOT，round 8 测量。Z 辅助比特：round 1–6 做 6 个 CNOT，round 7 测量，round 8 初始化。
- 周期重复：Z 辅助比特在上一 cycle 的 round 8 已初始化，所以 round 1 就能用。"We were not able to find a depth-8 (or smaller depth) syndrome cycle in which X-check and Z-check qubits are initialized and measured synchronously."（§5）
- 脚注 2：第一个 cycle 前要额外 InitZ q(Z,i)，使第一段深度为 9；最后一个 cycle 不需要 Z 的初始化。N_c 个 cycle 的总深度为 8N_c+1。
- 数据比特 idle 总数：每 i 有 L 在 round 1、R 在 round 7、L 和 R 在 round 8，共 4 次，72×4=288=2n，与 §6 的 2nN_c 吻合。辅助比特没有 idle 位置。

### 3.2 与 Eq.(9) 的对应（用来交叉校验）
Round 1: CNOT_A1(3,4)；Round 2: CNOT_A2(1,2), CNOT_A3(3,4)；Round 3: CNOT_B2(1,3), CNOT_B1(2,4)；Round 4: CNOT_B1(1,3), CNOT_B2(2,4)；Round 5: CNOT_B3(1,3), CNOT_B3(2,4)；Round 6: CNOT_A1(1,2), CNOT_A2(3,4)；Round 7: CNOT_A3(1,2)。寄存器编号 1=q(X)，2=q(L)，3=q(R)，4=q(Z)。（论文 Eq.(9)，§5）

### 3.3 仓库中的等价表示（`decoder_setup.py`）
- 邻居方向编号：X 检查 方向 0,1,2 = 左数据 A1,A2,A3；方向 3,4,5 = 右数据 B1,B2,B3。Z 检查 方向 0,1,2 = 左数据 B1^T,B2^T,B3^T（代码里 `nonzero(B1[:,i])`）；方向 3,4,5 = 右数据 A1^T,A2^T,A3^T。
- 调度：`sX = ['idle', 1, 4, 3, 5, 0, 2]`，`sZ = [3, 5, 0, 1, 2, 4, 'idle']`，下标 0..6 对应论文 round 1..7。
- 逐项核对：X 方向 1,4,3,5,0,2 = A2,B2,B1,B3,A1,A3，与 Table 5 的 round 2..7 一致；Z 方向 3,5,0,1,2,4 = A1^T,A3^T,B1^T,B2^T,B3^T,A2^T，与 Table 5 的 round 1..6 一致。
- 仓库 cycle 的元素：round 0（对应论文 round 1）：PrepX 全部 X 辅助 + Z 的 CNOT；未被 CNOT 的数据比特记 IDLE。rounds 1–5：X 的 CNOT 与 Z 的 CNOT 同时做。round 6：MeasZ + X 的 CNOT，空闲数据记 IDLE。round 7：全部数据 IDLE，MeasX（X 辅助），PrepZ（Z 辅助）。`num_cycles=12`。

### 3.4 调度的非唯一性与 d_circ（§5 末尾）
- "we found 935 depth-7 alternatives to the unitary part ... obtained ... by applying the gate layers CNOT_Ai and CNOT_Bj in a different order. In the special case of the [[144,12,12]] code, numerical simulations show that all 936 variants ... give rise to syndrome measurement circuits with distance d_circ ≤ 10"，所以论文选定 Eq.(9) 这一个并猜想它 d_circ=10。
- 这 936 个变体只是"重排 A_i、B_j 层顺序"的一个受限类，不等于整个调度空间。

## 4. 电路级距离（论文）
- 定义：产生不可检测逻辑错误所需的最少故障操作数（§2、§6）。d_circ ≤ d；=d 称 distance-preserving。
- 论文数字：Table 1，[[144,12,12]] 的 d_circ ≤ 10；[[72,12,6]] ≤6，[[90,8,10]] ≤8，[[108,8,10]] ≤8，[[288,12,18]] ≤18（288 码的上界论文称"unlikely to be tight"，§3）。论文只说 conjecture [[72,12,6]] 的电路是 distance-preserving，对 144 码是 conjecture 等于 10（§3、§5）。
- 计算方法（§6，Eq.(11)(12)）：对线性化噪声模型的译码矩阵 D^X（或 D^Z）和逻辑行，随机取逻辑组合向量 η，用 BP-OSD 解 min Σξ_j s.t. ξ∈ker(D^X), η^Tξ=1（Eq.(12)），取多次试验最小值，得到上界（不是精确值）。X、Z 型分别算，取 min。
- 仓库 `circuit_distance.py` 做同类上界估计（摘要工具转述：n=144，p=0.003，100000 次试验，BP-OSD osd_order=20，打印最小逻辑权重）。我没有看到完整源码，细节未核实。

## 5. 噪声模型（论文 §6）
- 标准电路级去极化噪声模型（引其 [22]）：每个操作以概率 p 出错，彼此独立。
- 故障 CNOT = 理想 CNOT 后接 15 种非恒等双比特 Pauli 之一，均匀随机（每种 p/15）。
- 故障初始化：制备与正确态正交的单比特态（概率 p）。
- 故障测量：理想测量后对结果做经典翻转（概率 p）。
- 故障 idle：X、Y、Z 之一均匀随机（每种 p/3）。
- 本笔记的约定：p 同时作用于 CNOT、init、meas、idle（仓库 `error_rate_init = error_rate_idle = error_rate_cnot = error_rate_meas`）。
- 仓库中的单故障概率：CNOT 的每类 X 型（对控制、对目标、双比特）各 p·4/15；idle 的 X 型/Z 型 p·2/3；init、meas 为 p（`decoder_setup.py`）。这是把 15 个 Pauli 按 X 分量/Z 分量分类后的结果，对 CSS 码 X、Z 分开译码。
- 其他噪声模型：论文没有用 SI1000。其 Open question 5 提到对测量偏置噪声的问题（§10）。

## 6. 解码器设置
- 论文 §6：BP-OSD（Panteleev–Kalachev；用 Roffe 的软件，§3）。把电路故障线性化：对每个单故障电路 U_j 求其全测量 syndrome、最终数据比特上的误差及其逻辑 syndrome，相同三元组的列合并并相加概率；对 syndrome 取相邻 cycle 差分使矩阵稀疏（§6）。X、Z 分开解码（§6）。
- 译码矩阵规模：论文称对任意 BB 码 D^X、D^Z 为 (6,35)-稀疏；[[144,12,12]]、N_c=12 时列数分别为 8857 和 8785（§6）。
- 论文 §8：使用 Roffe et al. 的 BP-OSD 软件，MIN-SUM BP，上限 10000 次迭代，combination sweep 版 OSD。除最小错误率点外，每个数据点累计至少 100 个逻辑错误，误差棒约 pL/10。
- 仓库 `decoder_run.py`（摘要转述）：`bp_method="ms"`，`max_iter=10000`，`osd_method="osd_cs"`，`osd_order=7`，`ms_scaling_factor=0`；`num_trials=50000`，无早停。逻辑失败 = X 或 Z 任一译码失败（要求 ec_resultZ and ec_resultX 同时成立才算成功）。论文 §8 没有写明 osd_order，7 只来自仓库。
- 仓库在译码前追加 2 个无噪声 cycle（`circ+cycle+cycle`），论文 §6 说"adding one noiseless cycle at the end"。两者不一致，复现时需选定一种并记录。
- 最终逻辑 syndrome 用 css_code 的 lx/lz（来自 `bposd.css`），仓库依赖 ldpc、bposd、numpy、scipy。

## 7. 逻辑错误率数字（论文）
定义（§3）：P_L(N_c) 为 N_c 个 cycle 后的逻辑错误概率，p_L = 1−(1−P_L(N_c))^{1/N_c} ≈ P_L(N_c)/N_c，每 cycle 的逻辑错误率（对全部 12 个逻辑比特）。取 N_c = d。

| 数字 | 值 | 出处 |
|---|---|---|
| pL(p=1e-3)，[[144,12,12]] | 2×10^-7 | Table 1（§3）；Fig. 2A 同一曲线 |
| pL(p=1e-4)，[[144,12,12]] | 8×10^-13 | Table 1。论文说明：pL 对 p≥1e-3 是数值计算，更低 p 为外推（Table 1 注释） |
| pseudo-threshold p0（pL(p)=kp 的解） | 0.0065 | Table 1。正文称 144 与 288 码的观测 pseudo-threshold 接近 0.007（§3） |
| 拟合公式 | pL(p) = p^{d'_circ/2} · exp(c0 + c1·p + c2·p²)，d'_circ=10 | §3、§8 |
| 144 码拟合系数 | c0=18.04，c1=1337，c2=−96007 | Table 6（§8） |
| 其他码 pL(1e-3) | [[72,12,6]] 7e-5；[[90,8,10]] 5e-6；[[108,8,10]] 3e-6；[[288,12,18]] 2e-12 | Table 1 |
| 与表面码对比 | 12 逻辑比特 [[144,12,12]] 共 288 物理比特；同等抑制（~1e-6）的表面码要近 3000 | 摘要、§3、Fig. 2B |
| 阈值 | 摘要称 0.8%（"error threshold of 0.8%"） | 摘要 |
| 一致性自检（我算的，非原文） | 用 Table 6 系数：p=1e-3 → 约 2.4e-7；p=1e-4 → 约 7.7e-13，与 Table 1 吻合 | 由 Table 6 公式算得 |

- 数据点说明：Fig. 2A 各点模拟 d 个 syndrome cycle，大多数点误差棒 ≈pL/10（Fig. 2 说明）。
- 论文没有给出 Table 1 中 p=1e-3 数字对应的原始"逻辑错误数 / 总 shots"。未找到。

## 8. 公开代码仓库
- 链接：https://github.com/sbravyi/BivariateBicycleCodes ，许可 Apache-2.0（WebFetch 读到的 repo 页）。
- 文件：`README.md`、`LICENSE`、`decoder_setup.py`、`decoder_run.py`、`distance_test.py`、`circuit_distance.py`。
- 电路构造：`decoder_setup.py`——文件顶部有 `sX`、`sZ`、`num_cycles` 和 [[144,12,12]] 等码的 (ℓ,m,a,b)，随后 `nbs` 邻居表、`cycle` 列表（PrepX/PrepZ/MeasX/MeasZ/CNOT/IDLE）、单故障电路枚举、译码矩阵构造并 pickle 存到 `./TMP/`。
- 解码与采样：`decoder_run.py`。码距：`distance_test.py`（ILP，README 称之）。电路距离上界：`circuit_distance.py`。
- README 说明：生成论文"Figure 3"数据的仿真软件（README 原文写 Figure 3，与 v2 的 Fig. 2 号不同）。目录需要预先建 `TMP/` 和 `CODE_n_k_d/`。依赖 Roffe 的 ldpc 包。
- 本仓库没有 stim 版本；论文与仓库都用自写的 Pauli 传播 + BP-OSD，不是 stim/sinter。若本项目用 stim 实现，数字可能因噪声通道分类（尤其 idle、CNOT 去极化）细节而不同，需单独对照。
- 关于其他实现：搜索结果中列出若干第三方仓库（nico-212/BivariateBicycleAnalysis、Anil077476/qldpc-bivariate-bicycle、noahberthusen/qecc_routing 等），我没有读其内容，不能当 baseline 依据。

## 新颖性判断
不适用于本笔记。关于 baseline 能否被超越见 `novelty-schedule-search.md`。

## 对本项目的建议（给正在实现 baseline 的 experimenter）
1. 先复现论文的 Table 5：用 §3.1 的表和 §3.3 的 sX/sZ 交叉验证；无噪声下所有 detector 应确定。
2. 报告口径要写明：CNOT 层数=7，含 init/meas 的 time step=8（第一个 cycle 为 9）。
3. 噪声模型按 §5 实现，idle 只作用在数据比特（辅助比特没有 idle 位置）。若用 stim，请把去极化通道、idle 位置、init/meas 翻转逐项对照 §5 和仓库。
4. 解码器用同一套 BP-OSD min-sum 参数；N_c=d=12；记录你用 1 个还是 2 个无噪声收尾 cycle。
5. 验收目标：p=1e-3 附近 pL 与 2e-7（Table 1）同量级（论文误差棒约 10%，且 p<1e-3 的数字是外推，直接模拟只适用 p≥1e-3）；d_circ 上界 ≤10。
6. 注意 Strikis et al.（2603.05481）认为 gross code 目前已知最好 d_circ=10，并给出一个 d_circ=11 的猜想电路；若 baseline 要和"IBM 公开调度"比，用本笔记的 Table 5 调度，不要混用。
