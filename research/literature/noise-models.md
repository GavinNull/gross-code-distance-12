# 电路级噪声模型：SI1000 / SD6 / gross code 论文 / stim 生成器，及表面码 MWPM 阈值
检索日期：2026-10-02；检索词：SI1000 noise model, standard depolarizing SD6, honeycomb code threshold, surface code circuit-level threshold, sparse blossom threshold, Stephens fault-tolerant thresholds, bivariate bicycle noise model。
所有论文均下载全文核对（pdftotext），不是只看摘要。标注“自测”的是我本人在草稿环境里的快速复核，不是文献，也不是项目实验记录。

## 结论（先看这里）
1. **E-001 的噪声口径在文献里有现成对应：Sparse Blossom（arXiv 2303.15933）图 10 题注描述的就是同一个模型，阈值“约 0.71%”。**
   所以负责人事先预测的 0.7% 并没有错，错的是 E-001 的“阈值”读法，不是噪声口径。原先“口径不同”的归因应当撤回。
2. E-001 报的 1.2% 是**每轮（per-round）逻辑错误率**在 d=3,5,7 之间的交叉点。文献的 0.5%~0.7% 类数字是**每 d 轮（per-d-rounds / 每 shot）**口径。
   Stephens（arXiv 1311.5003）第 VI 节明确说明：按每轮口径读阈值会高估，大 d 时才收敛。自测见下，d 增大后每轮交叉点从约 1.2% 往下漂到约 1.0%，每 shot 交叉点约 0.7%~0.8%。
3. E-001 的原始数据本身没有问题：把 E-001 表里的每轮值换回每 shot 值，d=3/5 交叉在约 0.5%~0.6%，d=5/7 约 0.85%，与 0.71% 相容（见第 4 节）。
4. 需要写进评估器的噪声模型至少要区分：`STIM_UNIFORM_4P`（E-001 模型，无空闲噪声）、`SD6`、`SI1000`、`GROSS_SD6`（IBM gross 论文的模型，与 SD6 近似但空闲噪声只加在显式 Idle 门上）。四者互不等价，不可混比。
5. 署名更正：arXiv 2108.10457 是 Gidney, Newman, **Fowler, Broughton**（A Fault-Tolerant Honeycomb Memory）；SI1000/SD6/EM3 表在这篇首次给出。Gidney, Newman, **McEwen** 是 arXiv 2202.11845（Benchmarking the Planar Honeycomb Code），沿用并略改了同一组表。

## 1. SI1000 的精确定义

### 1.1 出处
- 首次定义：arXiv 2108.10457（Gidney, Newman, Fowler, Broughton, 2021），第 2 节，**表 1**（噪声通道与规则定义）和**表 2**（三套噪声门集：SD6 / SI1000 / EM3）。
- 沿用并修改：arXiv 2202.11845（Gidney, Newman, McEwen, Quantum 2022），附录 A，**表 2、表 3**。
- 参考实现（作者仓库 strilanc/honeycomb_threshold，`src/noise.py`）：我只通过网页摘要读到，未逐行核对，仅作旁证。内容与表 2 一致：SI1000 = `any_clifford_1=p/10, idle=p/10, measure_reset_idle=2p, CZ=p, R=2p, M=5p`；SD6 = `any_clifford_1=p, idle=p, measure_reset_idle=0, CX=p, R=p, M=p`。

### 1.2 表 1 的通道定义（2108.10457 第 2 节表 1，逐字意译）
| 名称 | 定义 |
|---|---|
| AnyClifford2(p) | 任意双比特 Clifford 门，之后接强度 p 的双比特去极化通道 |
| AnyClifford1(p) | 任意单比特 Clifford 门，之后接强度 p 的单比特去极化通道 |
| InitZ(p) | 初始化为 \|0>，之后接强度 p 的比特翻转通道 |
| MZ(p) | 先接强度 p 的比特翻转通道，再做 Z 基测量（即错误加在测量**之前**） |
| Idle(p) | 若该比特在该时间步**没有被任何操作使用**，加强度 p 的单比特去极化 |
| ResonatorIdle(p) | 若该比特在某个时间步**没有被测量或复位**，而此时**其他比特正在被测量或复位**，加强度 p 的单比特去极化 |
| MPP(p) | 双体 Pauli 乘积测量（仅 EM3 用，不涉及表面码） |

表 1 脚注原文要点：“Noisy rules stack with each other”，即 Idle(p) 与 ResonatorIdle(p) 可以在同一时间步同时作用（两个独立去极化通道叠加）。
“强度 p 的去极化”的具体含义（单比特：以概率 p 随机施加 X/Y/Z 之一；双比特：以概率 p 随机施加 15 个非恒等 Pauli 之一）论文没有在表里单独写，我取 Stim 的 DEPOLARIZE1/2 约定，与 Stephens（1311.5003 第 V.C 节标准噪声模型的文字描述）一致。**该约定为我的推断，论文表 1 未显式说明。**

### 1.3 表 2：SI1000 逐项（2108.10457 表 2；2202.11845 表 3 同）
| 操作 | SI1000 的噪声 | 系数（p 的倍数） | 对照 SD6 |
|---|---|---|---|
| 双比特门 | CZ，后接 AnyClifford2 去极化 | **p**（15 个 Pauli 各 p/15） | CX，p |
| 单比特 Clifford 门 | AnyClifford1 去极化 | **p/10** | p |
| 复位 | InitZ：复位后比特翻转 | **2p** | p |
| 测量 | MZ：测量前比特翻转 | **5p** | p |
| 空闲（该步未被任何操作使用） | Idle 单比特去极化 | **p/10** | p |
| 测量期间空闲（resonator idle） | ResonatorIdle 单比特去极化 | **2p** | 无（0） |
| 测量/复位本身是否额外去极化 | 表里未列 | 未找到，按表字面理解为无 | 无 |

要点：
- 表 2 中 SI1000 的 CZ 对应超导门集（CZ 为原生双比特门），SD6 用 CX。对表面码电路，门集不同意味着电路本身要换：SI1000 用 CZ + H 搭，SD6 用 CX。**不能只改噪声系数而沿用同一条 CX 电路。**
- SI1000 的“p”是**最大的那个误差率之一**：测量实际翻转率是 5p，复位 2p。把 p 当作“物理错误率”做横轴时，要在文中说明 p 的定义。
- 表 2 底部的周期长度：2108.10457 写蜂窝码一个周期 7 个时间步（约 1000 ns）；2202.11845 的表 3 写 9 个时间步。**两篇不一致，且这是蜂窝码周期，不是表面码。**表面码在 SI1000 下一个周期有多少时间步，论文表里**未找到**；表 2 脚注只说明“SD6 下表面码一个周期是 8 个时间步，不是 6”。
- ResonatorIdle 的实现细节（它加在哪些比特、哪些时间步）论文只给了文字规则，没有给表面码电路的逐步布局。需要实现者按表 1 的规则“逐时间步（TICK 层）扫描”：某层只要有任何比特在被测量/复位，则该层内**没有被测量/复位的所有比特**（包括正在做门的比特？）都受 ResonatorIdle。表 1 字面是“not measured or reset”，没有排除“正在做门的比特”，但物理上谐振腔共享只对不在门中的比特有意义。**这一点论文未明确，属于需要向负责人确认的歧义（见“对本项目的建议”）。**

### 1.4 SD6（standard depolarizing）的定义
- 术语出处：arXiv 2108.10457 表 2，SD6 = “Standard Depolarizing”，6 = 蜂窝码周期的 6 个时间步。2202.11845 第 4 节写作“standard depolarizing 6-step cycle”。
- 噪声门集（表 2 SD6 列）：CX(p)；AnyClifford1(p)；InitZ(p)；MZ(p)；Idle(p)；**无** ResonatorIdle。
- 即：每个 CX 后 DEPOLARIZE2(p)，每个单比特门后 DEPOLARIZE1(p)，每个复位后 X_ERROR(p)，每个测量前 X_ERROR(p)，每个未被使用的比特每个时间步 DEPOLARIZE1(p)。
- 表面码上沿用名字 SD6：2108.10457 表 2 脚注。

### 1.5 “standard noise model”（Stephens）与 Fowler 的模型
- Stephens，arXiv 1311.5003，第 V.C 节：单比特门以 p 作用后跟 {X,Y,Z} 之一；双比特门以 p 作用后跟 15 个双比特 Pauli 之一；初始化和测量各以 p 制备/报告错误的正交本征态。
  **该节没有单独写“空闲比特”的规则**；第 V.D 节“balanced noise model”明确说明它是在 standard 基础上让空闲比特与门内比特同等不可靠。读者不要把 Stephens 的 standard 等同 SD6。
- Fowler, Mariantoni, Martinis, Cleland，arXiv 1208.0928，第 VI 节图 4 前的错误列表：数据比特恒等操作以 p/3 做 X/Y/Z，初始化以 p 制备错误态，测量比特的 H 门后以 p/3 做 X/Y/Z，测量以 p 报错……（列表后半我只读到 4 项，CNOT 的错误项未读到，**未核实**）。

## 2. E-001 使用的 stim 生成器模型（STIM_UNIFORM_4P）
在 stim 1.16.0 上用 `stim.Circuit.generated("surface_code:rotated_memory_z", ...)` 生成并读电路，逐指令确认（自测，d=3 的电路文本；不同 stim 版本是否一致**未核实**）：
| 参数 | 生成电路里的位置 |
|---|---|
| `after_reset_flip_probability` | 每次 R 之后对被复位比特 `X_ERROR(p)`（含首轮数据比特复位、每轮 MR 的复位部分） |
| `before_measure_flip_probability` | 每次 M/MR 之前对被测比特 `X_ERROR(p)` |
| `before_round_data_depolarization` | 每轮开始时仅对**数据比特**一次 `DEPOLARIZE1(p)`，辅助比特没有 |
| `after_clifford_depolarization` | 每个 CX 之后 `DEPOLARIZE2(p)`；每层 H 之后对做 H 的 4 个 X 辅助比特 `DEPOLARIZE1(p)`；其他比特没有 |
实测几个要点：
- 没有任何“空闲”噪声：在 CX 层里没参与门的比特、在测量/复位层里数据比特，都不受噪声。数据比特每轮只受一次 DEPOLARIZE1(p)。这比 SD6 轻（SD6 的数据比特在一个 8 步周期里有多个空闲步，每步 p）。
- MR 同时带“测量前翻转”和“复位后翻转”两个 p。
- 这个模型是 **stim 的生成器自带，不是 SD6、也不是 SI1000**。

## 3. IBM gross code 论文（Bravyi et al., arXiv 2308.07915）的噪声模型
出处：第 6 节“Decoder for the circuit-based noise model”（电路噪声定义段）；第 1 节（“each operation fails with probability p”）；第 5 节表 4、表 5（电路及其 Idle 位置）；第 6 节 98nNc 计数段。
| 操作 | 噪声 | 概率 |
|---|---|---|
| CNOT | 理想 CNOT 后接 15 个非恒等双比特 Pauli 之一，均匀 | p（每个 Pauli p/15） |
| 复位（InitX/InitZ） | 制备**与正确态正交**的单比特态（InitZ 等价于 \|1>，即 X 错误；InitX 等价于 \|->，即 Z 错误） | p |
| 测量（MeasX/MeasZ） | 对**测量结果**做经典比特翻转 | p |
| Idle 门 | X、Y、Z 之一，均匀 | p（每种 p/3） |
| 单比特 Clifford 门 | 论文电路里没有单独的单比特 Clifford（表 4 只有 CNOT、Init、Meas、Idle） | 不适用 |
| 测量期间空闲 | 无单独规则 | 未找到 |
关键细节（容易写错）：
- **空闲噪声只加在显式写出的 Idle 门上**，不是“每个没被使用的比特每一步”。每个综合征周期共 **2n 个 Idle 位置**（第 6 节：“2nNc idle qubit locations”）。表 5 里 Idle 的位置：第 1 轮 `Idle q(L,i)`；第 7 轮 `Idle q(R,i)`；第 8 轮 `Idle q(L,i)` 和 `Idle q(R,i)`；每个 i 取 1..n/2，合计 (1+1+2)·n/2 = 2n。
  因此它不是 SD6：SD6 对每个空闲（未被使用）比特每步加 p，而这里显式 Idle 数量固定为 2n/周期。凡是论文表 5 没写 Idle 的位置，即使比特在该轮没有被门作用，也不加噪声（论文规则按显式 Idle 门计）。要复现，必须用论文表 5 的电路与 Idle 位置，不能换成别的 gross 电路或 SD6 式的逐层空闲噪声。
- 第 6 节 98 = 15·6 + 1 + 1 + 3·2 的计数：每个 (n·周期) 含 6 个 CNOT、1 个 init、1 个 measure、2 个 idle，印证上表。
- 每个周期共 6n 个 CNOT、n 次 init、n 次 measure、2n 个 idle（第 6 节原文）。
- 逻辑错误率定义：p_L = 1 − (1 − P_L(Nc))^(1/Nc)，取 Nc = d（第 1 节，“Following common practice, we choose Nc = d”）。这是**每周期**错误率，且 k 个逻辑比特合并（任一逻辑比特出错算错）。
- 译码：BP-OSD（min-sum，10000 次迭代，组合扫描 OSD），每个数据点除最低 p 外至少 100 个逻辑错误（第 8 节）。
- 度量：论文报告的是 **pseudo-threshold p0**（解 p_L(p) = k·p，表 1），[[144,12,12]] 为 0.0065，[[288,12,18]] 为 0.0069（表 1）；摘要写“error threshold of 0.8%”，第 1 节正文写“pseudo-threshold ... close to 0.007”。**这是 break-even 点，不是跨码距的交叉阈值，不能与表面码 MWPM 的交叉阈值直接比较。**
- 论文与表面码的对比（图 2B）：表面码数据来自 Bravyi-Vargo 软件（Phys. Rev. A 88, 062308，arXiv 号**未核实**），d∈{9,11,13,15}，“standard SM circuit [22]”，[22] = Fowler, Stephens, Groszkowski（Phys. Rev. A 80, 052312 = arXiv 0803.0272，题名与标题已核对），12 个表面码补丁并联后换算每周期错误率（第 8 节）。图 2B 用的具体表面码噪声参数（空闲怎么加）论文**没有写**，**未找到**。
- 后续 IBM 论文 Tour de gross（arXiv 2506.03094，Yoder et al.）第 2.6 节“Circuit noise”沿用同一套：制备/测量以 p 失败；Idle 门 X/Y/Z 各 p/3；CNOT 15 种各 p/15（该节原文）。

## 4. 文献中旋转表面码 + MWPM 阈值（及 E-001 是否合理）

### 4.1 与 E-001 口径相同的模型
- **Sparse Blossom（Higgott & Gidney, arXiv 2303.15933）图 10 题注**：“circuit-level depolarising noise model where the probability p ... sets the strength of two-qubit depolarising noise after each CNOT gate, the probability that each reset or measurement fails, as well as the strength of single-qubit depolarising noise applied before each round. The threshold for this noise model is around 0.71%.” 译：与 stim 生成器 `after_clifford_depolarization / after_reset_flip / before_measure_flip / before_round_data_depolarization` 全取 p 吻合。
  局限：题注没提 H 门后的单比特去极化（生成器会加），没说明阈值按每 shot 还是每轮读取，没给不确定度。**阈值口径未明**。  **结论：文献阈值 ≈ 0.71%。**

### 4.2 其他模型（同一量纲：每 d 轮 / 交叉点）
- SD6 表面码：0.5%~0.7%；SI1000 表面码：0.3%~0.5%。出处：2108.10457 第 4 节正文及图 5；2202.11845 第 4/5 节也引用（“surface code thresholds ... 0.5% − 0.7% for SD6 [9], 0.3% − 0.5% for SI1000 [9]”）。逻辑错误率按“每 d 轮一个码单元”报告（2108.10457 图 5 题注），模拟 3d 轮但换算回 d 轮。区间宽度是论文自己给的，不是误差棒。
- Stephens（arXiv 1311.5003，表 I，**每 d 轮口径**），用 MWPM，深度八线路 = 标准旋转表面码线路：
  - standard 模型：深度八 0.502(1)%（X 阈值 0.541(1)%，Z 阈值较低，取 0.502%）；深度六 0.672(1)%；深度五 0.846(1)%（式 10、12、14）。
  - balanced 模型：深度八 0.576(1)%；深度六 0.749(1)%；深度五 0.905(1)%（表 I）。
  - 完美单比特门：1.140(1)%；摘要：阈值范围“0.502(1)% and 1.140(1)% per gate”。
  - 非 d 轮口径的旧文献（每轮口径，表 I 脚注 b）：0.57%（Stephens 表 I 的 [15]，即 Fowler, Mariantoni, Martinis, Cleland 2012）、0.009、0.011、0.0125、0.014 等明显偏高，Stephens 说明是口径所致。
- Fowler, Mariantoni, Martinis, Cleland，arXiv 1208.0928：图 4 题注，pth = 0.57%（每步、含空闲数据比特 p/3 等所列各类错误）；同文提到“4% error rate for the entire surface code measurement cycle”。
- Fowler, Stephens, Groszkowski，arXiv 0803.0272：摘要“threshold error rate approaching 1%”（它的口径是更乐观的旧模型，不要拿来对标）。
- Raussendorf & Harrington，arXiv quant-ph/0610082：摘要“threshold is 0.75% for each source in an error model with preparation, gate, storage and measurement errors”（拓扑簇态方案，不是旋转表面码，仅作背景）。

### 4.3 E-001 的 1.2% 是否合理（判断依据）
**判断：作为“每轮口径、d=3,5,7 的交叉点”合理且与文献相容；作为“阈值”引用则不合理，应改成 0.7% 量级。**

依据：
1. 口径相同的模型文献阈值是 0.71%（4.1）。
2. Stephens 第 VI 节指出：每轮口径会高估阈值，且 n→∞ 时才收敛（他的深度五线路：每轮交叉点“约 0.0095”，每 d 轮口径 0.846%）。E-001 的 d 只有 3,5,7，偏差更大。
3. 把 E-001 表（每轮）换回每 shot（`P = 0.5·(1−(1−2q)^d)`，自算）：
   | p | d=3 | d=5 | d=7 |
   |---|---|---|---|
   | 0.005 | 0.0162 | 0.0144 | 0.0101 |
   | 0.008 | 0.0411 | 0.0517 | 0.0445 |
   | 0.010 | 0.0607 | 0.0850 | 0.1018 |
   d=3/5 交叉在 0.5%~0.8% 之间（线性内插约 0.55%），d=5/7 交叉在 0.8%~1.0% 之间（约 0.86%），与 0.71% 相容。
4. 自测复核（scratchpad 环境，stim 1.16.0 / sinter / pymatching 2.4.0；E-001 同一生成器与四个参数全取 p；每点 ≥1000~1500 个逻辑错误；rounds = d；**这不是项目实验记录**）：
   - 每 shot 口径，d=9 与 d=11：p=0.007 时 0.0313 vs 0.0300，p=0.008 时 0.0568 vs 0.0542，p=0.009 时 0.0859 vs 0.0936，交叉在 ≈0.8%~0.85%（读数粗，p 网格间隔 0.1%）；d=7 与 d=9 交叉 ≈0.75%；d=3 与 d=5 交叉 ≈0.6%。随 d 增大趋近 0.7%~0.8%。
   - 每轮口径（与 E-001 同一换算式）：d=3,5,7 的曲线在 1.0%~1.25% 一带几乎重合（相邻 d 的差在统计误差内，交叉点读数落在这一段）；d=9 与 d=11 在 p=0.010 时 0.01551 vs 0.01543，几乎相等，交叉 ≈1.0%。小 d 与大 d 的交叉点都明显高于每 shot 口径的 0.7%~0.85%，方向与 Stephens 的论述一致。
   - 自测中小 d 的交叉点有明显有限尺寸漂移，所以我不给出一个点估计，只说“收敛到 0.7%~0.8% 一带”；严格的阈值需要更大的 d 和有限尺寸标度拟合，这不是本笔记的任务。
5. E-001 的 Λ≈10（p=1e-3）也自洽：Λ ≈ p_th(每轮口径) / p，若用 0.71% 则 Λ≈7，与实测 10 的差异同样来自每轮口径的偏高。

**E-001 是流水线对的，错的是对“阈值”的读法**。建议在 E-001 日志里把预测对比一节改写：预测 0.7% 的参照系（模型）是对的，实测需用“每 shot 或大 d”重读；“预测的参照系错误”这一句应撤销。

## 5. 对照表
阈值列统一标注口径：A = 每 d 轮（每 shot / 码单元）；B = 每轮；P = pseudo-threshold（p_L = k·p）。

| 模型名 | 各操作噪声 | 表面码 MWPM 阈值 | 出处 |
|---|---|---|---|
| STIM_UNIFORM_4P（E-001；stim 生成器全取 p） | CX 后 DEPOLARIZE2(p)；H 后 DEPOLARIZE1(p)（仅 X 辅助比特）；每轮开始数据比特 DEPOLARIZE1(p)；复位后 X_ERROR(p)；测量前 X_ERROR(p)；**无空闲噪声** | ≈0.71%（口径 A 未明，题注未给不确定度）；E-001 实测每轮口径 1.2%（B，小 d），自测每 shot 约 0.6%~0.85% | 阈值：2303.15933 图 10 题注；E-001 日志；自测见 4.3 |
| SD6 | CX p；单比特 Clifford p；复位翻转 p；测量前翻转 p；空闲去极化 p；无 resonator idle | 0.5%~0.7%（A） | 2108.10457 表 1、表 2、第 4 节、图 5；2202.11845 表 3 |
| SI1000 | CZ p；单比特 Clifford p/10；复位翻转 2p；测量前翻转 5p；空闲 p/10；resonator idle 2p | 0.3%~0.5%（A） | 同上 |
| EM3（背景，非表面码） | MPP(p)、单比特 Clifford p、复位 p、测量 p、空闲 p（2202.11845 里复位/测量改 p/2） | 表面码 0.237%（并查集译码，别人的工作 [9]）；蜂窝码 1.5%~2.0% | 2108.10457 第 4 节、表 2；2202.11845 表 3 |
| Stephens standard（深度八线路） | 单比特门 p；双比特门 p；初始化 p；测量 p；空闲未单列 | 0.502(1)%（A） | 1311.5003 第 V.C 节式 (10)，表 I |
| Stephens standard（深度六/深度五线路） | 同上，不同线路 | 0.672(1)% / 0.846(1)%（A） | 1311.5003 式 (12)、(14) |
| Stephens balanced（深度八） | standard 基础上空闲比特与门内比特同等错误；测量只对一个基敏感 | 0.576(1)%（A） | 1311.5003 第 V.D 节，表 I |
| Stephens 完美单比特门 | 只有双比特门、初始化、测量有噪声 | 1.140(1)%（A） | 1311.5003 第 V.E 节，表 I |
| Fowler 2012 | 数据比特恒等 p/3（X/Y/Z）；初始化 p；测量比特 H 后 p/3；测量 p；CNOT 项未读 | 0.57%（每步） | 1208.0928 图 4 及前文列表 |
| GROSS_SD6（IBM gross 论文） | CNOT p（15 种各 p/15）；复位 p（正交态）；测量 p（经典翻转）；**仅显式 Idle 门**（每周期 2n 个）X/Y/Z 各 p/3；无单比特门 | 论文只给 pseudo-threshold：[[144,12,12]] 0.0065，[[288,12,18]] 0.0069（P）；论文摘要“0.8%”口径未在正文给出；其表面码对比数据的噪声空闲细节未找到 | 2308.07915 表 1、第 5 节、第 6 节、图 2B |

## 关键论文
| arXiv | 作者 · 年份 | 做了什么 | 与本项目关系 | 关键数字（附出处） |
|---|---|---|---|---|
| 2108.10457 | Gidney, Newman, Fowler, Broughton · 2021 | 蜂窝码 + 定义 SD6/SI1000/EM3；同模型下模拟表面码 | SI1000/SD6 的权威定义 | 表 2 系数；表面码阈值 SD6 0.5%~0.7%，SI1000 0.3%~0.5%（第 4 节） |
| 2202.11845 | Gidney, Newman, McEwen · 2022 | 平面蜂窝码基准，沿用并修改同一噪声表 | 表 3 是 SI1000 的第二个出处；注意与上篇的周期长度不一致 | 表 2、表 3；表面码阈值引用同上 |
| 2303.15933 | Higgott, Gidney · 2023 | Sparse Blossom（PyMatching v2） | E-001 同口径模型的文献阈值 | 图 10 题注：阈值约 0.71% |
| 1311.5003 | Stephens · 2014 | 多种电路噪声模型下表面码阈值，MWPM | 阈值口径（每轮 vs 每 d 轮）的最清楚论述 | 表 I：0.502%~1.140%；第 VI 节 |
| 1208.0928 | Fowler, Mariantoni, Martinis, Cleland · 2012 | 表面码综述 | 经典的 0.57% | 图 4 题注 |
| 2308.07915 | Bravyi et al. · 2024 | gross code | gross 噪声模型的定义 | 第 6 节、表 1、表 5 |
| 2506.03094 | Yoder et al. · 2025 | Tour de gross | 同一噪声模型的后续使用 | 第 2.6 节 |
| 0803.0272 | Fowler, Stephens, Groszkowski · 2009 | gross 论文引用的“标准电路噪声模型”出处 [22] | 查证用 | 摘要：阈值“approaching 1%” |

## 新颖性判断
本笔记是定义核对，不涉及新结果。有人做过完全相同的事吗？“同一生成器、同一噪声、同一 MWPM 的阈值”已有（Sparse Blossom 图 10，0.71%）；“按每轮和每 d 轮两种口径读阈值并比较”已有（Stephens 第 VI 节）。差别：E-001 用 d=3,5,7 的小码，文献口径与我读法不同，二者不冲突。

## 对本项目的建议
1. **评估器里把噪声模型显式命名并冻结口径**，至少四个：`STIM_UNIFORM_4P`、`SD6`、`SI1000`、`GROSS_SD6`。每个写出每种操作的错误通道与系数（用上面的表），并且线路也要对应（SD6 用 CX；SI1000 用 CZ+H；GROSS_SD6 用论文表 5 的线路与显式 Idle 位置）。stim 的 `generated(...)` 参数不能表达 SD6/SI1000 的空闲噪声，要在 TICK 层逐层补 DEPOLARIZE1。
2. 与 IBM gross 数字对比，必须用 `GROSS_SD6`，不是 stim 生成器模型。两者的空闲噪声差别可以让逻辑错误率差几倍，不要冒险。
3. **阈值读法写进评估器**：交叉点用每 shot（d 轮）口径，或明确标注每轮并说明大 d 才收敛。表面码 baseline 的 G0 判据建议“同模型阈值 ≈0.7%（0.71%，2303.15933 图 10）”，而不是 E-001 的 1.2%。
4. 需要负责人确认的歧义：(a) SI1000 ResonatorIdle 是否施加于正在做门的比特（表 1 字面未排除，物理上不应）；(b) SI1000 表面码一个周期的时间步划分与测量/复位是否同层（论文表没给）；(c) E-001 日志的归因段需改写。
5. 如需严格阈值：再跑 d=7,9,11,13 + 有限尺寸标度拟合，每 shot 口径；这不是 lit-scout 的活。

## 未核实 / 未找到清单
- Sparse Blossom 0.71% 的读取口径与不确定度：题注未给（只读了题注与全文关键词检索，未找到正文再述）。
- stim 不同版本 `generated` 电路是否一致：只核了 1.16.0。
- Fowler 1208.0928 中 CNOT 噪声项：未读到。
- Bravyi–Vargo（Phys. Rev. A 88, 062308）的 arXiv 号：未核实。
- gross 论文图 2B 表面码噪声的空闲细节：未找到。
- SI1000 表面码周期时间步划分：未找到。
