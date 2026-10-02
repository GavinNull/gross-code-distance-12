# 资源开销指标：怎么把"码 + 电路"的结果换算成省了多少比特
检索日期：2026-10-02；检索词：Tour de gross resource estimate、bicycle architecture physical qubits per logical qubit、teraquop footprint、Gidney yoked surface codes、failure spectrum ansatz extrapolation、qLDPC logical operations LPU extractor universal adapter、concatenated gross code footprint、directional codes qubits ratio extrapolation。

## 读取方式与局限（先看）
- PDF 从 arxiv.org/pdf/<编号> 下载后用 pdftotext 转文本阅读（会话临时目录）。"精读"= 读了相关章节，不是逐页通读。
- 精读：2506.03094 v1（Sec. 1、2.1–2.7、4、App. A.7、A.10 的相关段）；2108.10457（Sec. 2.1、Fig. 2/6/7 说明、结果段）；2605.21898 v2（摘要、Sec. 4、App. C，以及 Table 5 与参考文献）；2507.19430 v3 的 App. A–C.1；2308.07915 v2 的 Table 1 与 Sec. 3–6；2511.15177 v1 的摘要、Sec. 1、3.2、6。
- 只读摘要 + 定向检索：2312.04522（yoked surface codes）、2407.18393、2503.10390、2410.03628、2410.02213、2607.28795、2606.06062、2607.27153。
- 逻辑门 / LPU 在新码上的资源数字：除 gross / two-gross 外，我没有在读过的论文里找到任何一个现成的 BB 码（或其它权重 6 码）的 LPU 大小。
- 图里的数值（例如 Fig. 10a 的表）因为 pdftotext 排版错乱，我没引用。

## 结论（3-5 行）
- IBM 整机口径：q = M(c+u+a) − a + a′ + f（2506.03094 Sec. 4 式 (25)），gross 模块的 c:u:a = 288:90:22（Table 1），逻辑数据比特数 n=11M（只有 11 个可用，第 12 个作 pivot 辅助）。按这个口径，一个 gross 模块每可用逻辑比特约 36.4 个物理比特（我用 Table 1 算的），不是 memory-only 的 24；再加一个 T 工厂（454 或 810，Table 3）。memory 只占整机的约 65%（M=11、p=1e-3 时我算得 3168/4861）。
- **memory 的 LER 和整机能力是脱钩的**：gross 码在 p=1e-3 下 idle 为 10^-8.8（8 个 timestep），但 in-module 测量为 10^-5.0（120 个 timestep）、inter-module 测量为 10^-2.7（Table 2）。折到每 timestep，测量比 idle 高约 400 倍（我的算术）。所以"memory LER 提升 N 倍"不能直接换算成"整机省 N 倍比特"。
- 文献里比较不同码常用的指标有四种：（a）每逻辑比特总物理比特（含辅助）；（b）每逻辑比特每轮 LER（或每块每轮 LER，并说明 k）；（c）达到目标 LER 所需物理比特 / "等 LER 比特比"（directional codes 的做法）；（d）teraquop 比特数（Gidney 等，LER≈10⁻¹³–10⁻¹⁴/轮）。IBM 原文还用伪阈值（pL(p)=kp）。
- **建议 H-003 用两个指标**：A = Q = 总物理比特/k（精确，不抽样）；B = 每逻辑比特每轮 LER（SD6，p=1e-3 外推 + p=3–6e-3 直接采样）；对外报告的"省了多少比特"= 在同一 LER 处，新码相对于 gross–two-gross 参考包络线的 Q 之比。teraquop 不适合当主指标：p=1e-3 下 gross 码到不了该区间（2605.21898 摘要），本机也测不到 10⁻¹³。
- 外推方法在文献里差别极大：对同一个 gross code、同一噪声模型，p=1e-3 的每周期块 LER，IBM 原文 Table 1 为 2×10⁻⁷（拟合外推，BP-OSD），Tour de gross Table 2 为 10^-8.8≈1.6×10⁻⁹（失败谱 ansatz + Relay-BP）。**差约 125 倍，我没有核实两处口径是否完全一致**，但足以说明：只能在同一管线内比相对值。

## 关键论文
| arXiv | 作者 · 年份 | 做了什么 | 与本项目关系 | 关键数字（附出处） |
|---|---|---|---|---|
| 2506.03094 | Yoder 等（IBM）· 2025 | gross / two-gross 的指令集、逻辑错误率与端到端资源估计 | 整机物理比特数的计算口径 | Table 1（c,u,a,f,a′）、Table 2（各指令 LER）、Table 3（工厂）、式 (25)、Sec. 4 |
| 2308.07915 | Bravyi 等 · 2023 | BB 码 memory 的 pL、伪阈值、与表面码比较 | "每逻辑比特比特数 + LER"的最早口径与外推公式 | Table 1；Sec. 3 的拟合式；与表面码对比（Sec. 3 末） |
| 2511.15177 | Beverland, Carroll, Cross, Yoder（IBM）· 2025-11 | 失败谱 ansatz、最小权重失败计数、多种子 splitting | 低 LER 外推的 IBM 标准方法 | Sec. 3.2（ansatz）、Sec. 6（BB 码结果） |
| 2108.10457 | Gidney, Newman, Fowler, Broughton · 2021 | 蜂窝码 memory；提出 teraquop 比特数 | teraquop 的原始定义 | Sec. 2.1；Fig. 2 |
| 2312.04522 | Gidney, Newman, Brooks, Jones · 2023（Nat. Commun. 16, 4498） | yoked surface codes；teraquop footprint 外推 | 给 teraquop 区间 | Sec. 5.3：teraquop 区间约 10⁻¹³–10⁻¹⁴ 每轮 |
| 2605.21898 | Wills, Beverland, Bishop, Gambetta, Rall, Siddhu, Cross（IBM）· 2026 | gross 码之上的 Reed–Solomon 串联；按"目标 LER 下最小空间开销"画包络线 | Tour de gross 之后的 IBM 资源口径；含 morphing idle 对照 | 摘要；Sec. 4（Fig. 8）；App. C Table 5 |
| 2507.19430 | Gehér, Byfield, Ruban · 2025 | directional codes；"等 LER 比特比"的外推法 | 在本机算力下最可复制的比较口径 | App. C.1 式 (55)–(57)；Table 1 |
| 2407.18393 / 2503.10390 / 2410.03628 / 2410.02213 | Cross 等 / He 等 / Swaroop 等 / Williamson–Yoder | QLDPC 手术（LPU）、extractor、通用 adapter、gauging | 新码逻辑操作的通用构造 | 见第 4 节 |
| 2607.28795 | Bhardwaj, Ma 等 · 2026 | mitten codes；以"processing capacity / throughput / cycle time"刻画 processor | 另一套整机指标（quop） | Sec. II（Def. 3） |

## 1. Tour de gross（2506.03094）：从 gross code 的 LER 到整机比特数

**公式与分项**（Sec. 4，Table 1，Table 3）
- 整机：q = M(c+u+a) − a + a′ + f，可用逻辑数据比特 n = 11M（式 (25) 及其下一句）。M = 代码模块数；c = 码模块（数据+校验）；u = LPU（做模块内测量的辅助系统）；a = 模块间 adapter；a′ = 码-工厂 adapter；f = T 工厂。
- Table 1：gross：c=288，u=90，a=22；two-gross：c=576，u=158，a=34。f 与 a′：gross 在 p=1e-3 为 454 / 29（培育），p=1e-4 为 810 / 13（蒸馏）；two-gross 在 p=1e-3 为 463 / 29，p=1e-4 为 18,600 / 49（Table 1 与 Table 3）。
- 我的算术（从上述数字推出，论文没有直接印出）：gross 模块一个 c+u+a = 400，除以 11 个可用逻辑比特 = 36.4 物理比特/逻辑比特；two-gross 为 768/11 = 69.8。取 M=11、p=1e-3 的 gross 系统（对应论文 Fig. 10a 的 "5k, n=121" 一行，n=121=11×11）：q = 11×400 − 22 + 29 + 454 = 4861；其中码 3168（65.2%）、LPU 990（20.4%）、adapter 249（5.1%）、T 工厂 454（9.3%）；4861/121 = 40.2 物理比特/可用逻辑比特。**这个 4861 是我按式 (25) 代入算的，不是论文给的数字；M=11 来自 n=121。**
- 论文给出的两个整机数字（Sec. 4）：10×10 TFIM 模拟，gross + 1e-4 蒸馏工厂 q=4817，要求 p≤2.1×10⁻⁵；two-gross + 1e-3 培育工厂 q=8138，要求 p≤7.3×10⁻⁴；对照表面码 d=17 需 58,263、d=19 需 72,663 物理比特。

**memory、逻辑操作、magic state 各占多少**
- memory：c，约占 65%（上面的算术）。
- 逻辑操作：LPU（u）+ adapter（a）约占 25%（同上）。LPU 是为"模块内任意逻辑 Pauli 测量"加的辅助系统，需要把 q1、q7 的逻辑算符支撑与 LPU 相连（Sec. 2.3，Fig. 5）。
- magic state：单个 T 工厂 f（+ a′），在 M=11 时约占 9%；M 越大占比越低。论文的所有 capability 估计只用一个工厂（Sec. 4 "Approach"）。
- 论文自己提示：LPU 构造是为 gross / two-gross 手工做的；框架（He 等 extractor [He+25]）是通用的，但"present work focuses on explicit and practical scheme for a specific set of example codes"（Sec. 1.2）。

**logical error 口径**（Table 2，p=1e-3 / 1e-4）
- gross：idle 10^-8.8±0.2 / 10^-14.8±0.4（τ=8）；shift automorphism 10^-6.4 / 10^-12.2（τ=14）；in-module 测量 10^-5.0 / 10^-9.0（τ=120）；inter-module 测量 10^-2.7 / 10^-7.3（τ=120）；T 注入 10^-5.5 + P_C（p=1e-3，351+120 timestep）。
- two-gross：idle 10^-20.1 / 10^-38.3；shift 10^-14.5 / 10^-37；in-module、inter-module 的 [10^-11]、[10^-9]（p=1e-3）与 [10^-20]、[10^-18]（p=1e-4）是**"assumed without data"**（Table 2 脚注）。
- 整机失败概率按 P = Σ N_j P_j 相加（式 (26)），任何一个 logical error 都算失败。

**后续工作怎么用同一口径**
- 2605.21898（Wills 等）：目标是"在 ≤50 万物理比特内，达到给定每逻辑比特每轮 LER 的最小空间开销"（Sec. 4，Fig. 8）。物理比特数用同一批 Tour de gross 的 ancilla 系统：memory 系统的物理比特数为 378nm + 44(n−1)(m−1) + 22(n−1) + 22(m−1)，逻辑比特数 11(m−2)[n−2(d−1)]（Sec. 4）。结论：串联后的 gross 码在 p=1e-3 下可以进入 teraquop 区间（4.10×10⁻¹⁵ 每逻辑比特每轮时仍优于 288 比特的 two-gross 的空间开销）。这里"round"=8 个物理 timestep（Sec. 4）。
- 2511.15177：为同一套系统提供低 LER 的外推与验证方法（见第 3 节）。
- 未找到：Tour de gross 之外的、对非 gross/two-gross 的 BB 码给出完整整机比特数分解的论文（我只在 2607.28795 里看到 mitten 码给出了配套的逻辑工具箱，但那是权重 9）。

## 2. 比较不同 qLDPC 码 + 电路时的常用指标

| 指标 | 定义 | 出处 | 优点 | 在本项目的问题 |
|---|---|---|---|---|
| 总物理比特/k（Q） | (数据 + 校验辅助)/逻辑比特数；标准电路下 2n/k；BB 的"净编码率 r=k/2n" | 2308.07915 Table 1 题注（"requires 2n physical qubits… net encoding rate r = k/2n"） | 精确，零抽样成本 | 不含 LPU、工厂；k 小时 Q 大但"每块 LER"小，需配合 B |
| 每块每周期 LER pL | pL = 1 − (1 − P_L(N_c))^{1/N_c} ≈ P_L(N_c)/N_c，N_c=d；P_L 为 k 个逻辑比特中任一个出错；伪阈值 pL(p)=kp | 2308.07915 Sec. 3、Table 1 | IBM 原文口径，与大量后续论文可比 | 与"每逻辑比特"差一个 k；需要写明 |
| 每逻辑比特每轮 LER | OmniQEC 的 pLER；Wills 的"per logical qubit-round" | 2607.25865 Fig. 2 / Sec. III.A；2605.21898 Sec. 4 | 便于与表面码比较 | OmniQEC 的横轴是总 N，没除 k（见 `codesign-landscape.md`） |
| 等 LER 比特比 | 对两族码在固定 p 下拟合 log pL = s·√n_ph + c，取 (s_ref/s_dir)² 为同 LER 所需比特比 | 2507.19430 App. C.1 式 (55)–(57)，置信区间用 10 万次自助法 | 直接回答"省多少比特"；本机能算 | 需要同一族多个尺寸；对离散码族要做插值（见第 5 节） |
| Λ 因子 | Λ(p) = p_L^d(p)/p_L^{d+2}(p)，码距加 2 带来的抑制 | 2108.10457 Sec. 2.1 | 与阈值联系紧 | BB 码的距离不连续，难定义 |
| teraquop 比特数 T(p) | 在物理错误率 p 下，"in expectation 成功完成 10¹² 次逻辑 idle 门所需的物理比特"（idle=d 轮），也画成每逻辑比特物理比特数 | 2108.10457 Sec. 2.1、Fig. 2；2312.04522 Sec. 5.3 | 单一数字、可跨架构比较 | 要 10⁻¹³ 量级的 LER，只能外推；gross 码在 p=1e-3 到不了（2605.21898 摘要） |
| teraquop 区间阈值 | 每逻辑比特每轮 LER 约 10⁻¹⁴–10⁻¹³ | 2312.04522 Sec. 5.3；2605.21898 脚注 2 | — | — |
| 整机指标 | 给定 (q, p) 下能跑的随机 Pauli 旋转电路的最大 T 数与逻辑比特数（失败概率≤1/3）；或达到目标 ε 的总 q | 2506.03094 Sec. 4、Fig. 10 | 含全部开销 | 要求 LPU/工厂，新码没有 |
| quop 指标 | processing capacity = 1/p_L（每 quop），throughput，cycle time | 2607.28795 Sec. II（Def. 3） | 面向 processor | 权重 9 码专用，不适用 |

## 3. 文献里怎么外推到低物理错误率（本机只能采 p=3e-3–6e-3）

1. **IBM 原文**（2308.07915 Sec. 3，Table 1 题注）：pL 在 p≥10⁻³ 处直接模拟，再用 pL = p^{d′_circ/2} · exp(c0 + c1·p + c2·p²) 拟合外推到更低 p；d′_circ 是 BP-OSD 得到的 d_circ 上界；c0,c1,c2 为拟合参数。Table 1 的 pL(1e-4) 与 pL(1e-3) 里 two-gross 的 2×10⁻¹² 都来自这种外推或其延伸。
2. **失败谱 ansatz**（2511.15177 Sec. 3.2；2506.03094 Sec. 2.6、App. A.7）：对"权重 w 的故障集合里导致失败的比例 f(w)"做低参数拟合，f(w)=0（w<w0=⌈d_circ/2⌉），P(p) 由 Σ_w f(w)·C(N,w)·q^w(1−q)^{N−w} 给出。用 d_circ 的整数规划上界（gross 取 10，two-gross 取 18）固定 w0，拟合另外两个参数；用 Relay-BP 解码；Tour de gross 的全部指令模拟用了约 22,700 核时（Fig. 15 说明）。2511.15177 Sec. 6 的结论是：BB 码在 Relay 下的外推与分裂法大体一致，但 BB(12)、BB(18) 实测起始权重远高于理论下界，**外推结果依赖解码器**。
3. **分裂 / MCMC**：多种子 splitting（2511.15177 Sec. 5）；2607.27153（Northrop Grumman）提出剪枝 + 子区域 MCMC，我只读了摘要。
4. **teraquop 外推**（2108.10457 Sec. 2.1、Fig. 6–7）：对各码距在多个 p 下做直线拟合，用 Λ 外推到 10⁻¹² 量级。
5. **等 LER 比特比**（2507.19430 App. C.1）：固定 p=1e-3，直接采样到 10⁶ 次或 10⁴ 次失败；用每族 3 个点拟合 log pL 对 √n_ph 的直线，换算比特比；全部模拟约 45 CPU-core-years（App. A 末）。
6. 其它：OmniQEC 在 p=0.005 直接采样，并用 pLER ∝ p^Γ 拟合 p∈[0.002,0.01] 上的指数 Γ（2607.25865 Sec. III.C）；Wills 2605.21898 的 morphing idle 数字是"直接蒙特卡洛，不外推"，区间很宽（Table 5：9.2×10⁻¹²–1.3×10⁻¹⁰）。

**我的算术**：本机从 p=4e-3 外推到 1e-3，p 比值 4；若 d_circ=10，LER 差 4⁵≈1000 倍；有效指数偏差 1，外推结果就差约 4 倍。另外，同一 gross 码在不同口径下的 1e-3 数字差约 125 倍（上面结论）。所以"绝对 LER"的置信度很低，"相对于 gross 码的比值"才可能稳。算力对比：Tour de gross 用了 22,700 核时；本机 8 个 worker 连续跑 14 天约 2,700 核时（约其 12%），够做少数几个码的外推，不够搜索时逐个候选做。

## 4. 逻辑操作的可实现性：文献怎么处理

**问题本身**：memory LER 好不代表整机好。Tour de gross 的数据显示，gross 码在 p=1e-3 下 in-module 测量（10^-5.0）比 idle（10^-8.8）差 3.8 个数量级，每 timestep 差约 400 倍（我的算术）。同一份文献在 Outlook 里承认：in-/inter-module 测量 d_circ 也只有 ≤10（Table 4），并把"提升 inter-module 测量 LER 一个数量级"列为整机能力提升的关键（Sec. 4 末）。2605.21898 App. C 也说：新的 morphing idle 电路"would not be accommodated by the ancilla systems constructed thus far"，需要重新设计，手术电路也要达到码距离才能完整受益。

**gross 码的逻辑操作怎么来的**
- 平移自同构（shift automorphism）：BB 码的 Z_ℓ×Z_m 平移对称给出逻辑 CNOT 电路，12 条指令，论文说 gross / two-gross 中任何非平凡乘积最多两个生成元（Sec. 2.2、App. A.2；自同构群引自 Eberhardt–Steffan，2407.03973 [ES24]）。平移对称对所有 BB 码都成立；"最多两个生成元够用"是 gross/two-gross 的具体性质。
- LPU（手术）：在 q1、q7 上测量任意逻辑 Pauli，与平移自同构交错可得到 11/12 个逻辑比特上的完整 Clifford（Sec. 2.3 与脚注 5，引 Cross 等 2407.18393）。gross LPU = 90 个比特（Sec. 2.3，Fig. 5b），two-gross 158（Fig. 5c）。Cross 等的原始构造为 103 个辅助比特（2407.18393 摘要）；Tour de gross 的构造"更小、更强"。
- T 注入：工厂 + adapter，经 inter-module 测量注入（Sec. 2.5）。

**新码怎么办？文献里的几种做法**
1. **通用构造**：extractor（He 等 2503.10390）声称"可以把任何 QLDPC memory 变成计算块"，任意逻辑 Pauli 一个逻辑周期可测，规模 Õ(n)，"精确开销有很大优化空间"（摘要）；通用 adapter（Swaroop 等 2410.03628）对任意 LDPC 码适用，t 个权重 O(d) 算符用 Õ(td) 辅助（摘要）；gauging（Williamson–Yoder 2410.02213）"可以适配任意量子码"，辅助比特数与被测算符权重成线性（摘要）；Cross 等 2407.18393：某些情况只需 Θ(w) 辅助比特测量权重 w 的算符（摘要）。这些是"理论上可行"，**对一个具体的新 BB 码要付出的具体比特数，我没有在文献里找到**。
2. **码设计时把逻辑操作写进筛选**：Eberhardt–Steffan（2407.03973）为 BB 码给出显式逻辑算符基与折叠横向 Clifford 门，并构造了 [[98,6,12]]、[[162,8,12]] 两个带这类门的 BB 码（仅见搜索摘要，未读全文）；mitten 码要求"square-invertibility"以获得群结构的低权重规范逻辑基（2607.28795 App. F）；barbell 码（2606.06062）在摘要里称对逻辑多 Pauli 测量也做了电路模拟，LER 与 memory 相近；Shaw–Terhal 2407.16336 给出了 morphing 下与表面码的逻辑 I/O（biplanar）。
3. **只做 memory，并说明局限**：IBM 2308.07915 的 Table 1 / Fig. 2 全是 memory 的 LER（该文 Sec. 9 另外用解析方式讨论了自同构门、ZX 对偶与逻辑测量，没有给出这些操作的电路级 LER，我只看到了章节标题与开头，未细读）；2606.02418 在引言里把逻辑门列为让高 k 码有价值的原因，但只评估码；OmniQEC 在 Sec. II.B 明说其实现面向 memory 实验，把逻辑操作 / 手术优化列为模块化扩展。
4. **串联 / 其它回避方式**：2605.21898 用 gross 码做内码，外码用 Reed–Solomon，逻辑操作仍用 Tour de gross 的 bicycle instructions。

**这对 H-003 的含义**：新码如果不是 gross / two-gross，memory 指标之外的两件事没有文献现成答案：（i）LPU/extractor 的比特数；（ii）手术指令的 d_circ 与 LER。H-003 最多能做的是：给出 memory 指标，并对入围码额外做一次**廉价的可操作性检查**（见建议 5），不要把"省了比特"写成整机结论。

## 新颖性判断
- 指标本身没有新颖性：每逻辑比特比特数、每轮 LER、等 LER 比特比、teraquop 都是现成的。新颖性只在"用这些指标作为搜索目标"，这一点在 `codesign-landscape.md` 里已判断。
- 与我们最接近的先例是 Riverlane 的"等 LER 比特比"（2507.19430）和 IBM 的 (2n/k, pL) 表（2308.07915 Table 1）；OmniQEC 的（N, pLER）曲线没有按 k 归一，不能直接借用。

## 对本项目的建议

**1. H-003 用两个指标，一个比特口径、一个错误率口径，外加一个由二者派生的"等效省比特"。**
- **指标 A（比特）**：Q = (n + m_X + m_Z)/k，其中 m_X、m_Z 是实际使用的校验行数（含冗余行，BB 码即 2n/k）。精确，不抽样。同时写出 k，并附"若需逻辑操作，可用逻辑比特 k−1"的副指标 Q′ = (n + m_X + m_Z)/(k−1)（对应 Tour de gross 的 11/12）。
- **指标 B（错误率）**：每逻辑比特每轮 LER = 每块每轮 LER ÷ k，SD6 噪声、同一解码器、同一电路族、同一外推方法。报告两处：p=1e-3 外推（失败谱 ansatz，d_circ 上界固定 w0，必要时与 IBM 式拟合并列）和 p=4e-3 直接采样。**块 LER 与每逻辑比特 LER 的换算必须写在表头**（IBM 原文是块 LER，OmniQEC 是每逻辑比特）。
- **派生量（对外说"省了多少比特"）**：把 gross [[144,12,12]]（Q=24）、two-gross（Q=48）、[[72,12,6]]、[[108,8,10]] 用**我们自己的管线**测出 (Q, B)，取其下包络线（log B 对 Q 线性插值，作为明确的建模假设）。新码的"等效省比特"= Q_ref(B_new)/Q_new，其中 Q_ref(B) 是包络线在该 LER 处的 Q。只有当新码点在包络线下方、且置信区间不跨线时才宣称改进。我用 IBM Table 1 的两个点粗算：5 个数量级对应 24 个比特/逻辑比特，即约 4.8 个比特/数量级；用 Tour de gross Table 2 算则是 11.3 个数量级、约 2.1 个比特/数量级，**两个口径差 2 倍多，所以这个换算只能用自己的管线**。
- 为什么不选 teraquop：本机测不到；gross 码在 p=1e-3 下进不去（2605.21898 摘要）；two-gross 的 idle 又远超 teraquop（10^-20.1），对设计比 gross 小或介于两者之间的码没有区分度。只在最后可以报告"若按 Wills 等的外推，达到 teraquop 区间所需 Q"作为背景，不作结论。

**2. 外推的做法（本机算力下）**
- 搜索阶段只用 p=4e-3 或 5e-3 的直接采样（OmniQEC 用 p=0.005，2607.25865 Sec. III.A）给候选排序，并同时记录 d_circ 的 BP-OSD 上界。
- 对入围的 ≤5 个码用失败谱 ansatz 外推到 1e-3（做法：2511.15177 Sec. 3.2、2506.03094 A.7），同时用 IBM 式拟合（2308.07915 Sec. 3）并列；两种外推对 gross 码用同一套。
- 结论只写成"相对于 gross 码在同一管线里的比值"，不引用 IBM / Tour de gross 的绝对数字作为我们的结果。若两种外推在比值的符号上不一致，就不宣称改进。
- 先做一次口径复核（建议作为 E-003 的子任务）：用我们的管线复现 gross code 的 pL(1e-3)，看落在 2×10⁻⁷（2308.07915 Table 1）还是 10^-8.8（2506.03094 Table 2）附近，并解释差别（解码器、归一、噪声实现）。这件事本身决定外推基线是否可信。

**3. 对照点（沿用 `codesign-landscape.md` 的建议）**：gross + IBM 深度-7、gross + Strikis 11 电路、Shaw–Terhal morphing [[144,12,12]]（Q=24）、[[288,12,18]]（Q=48）。

**4. 不要做的事**：不要把"memory LER 比 gross 好 N 倍"写成"整机省 N 倍"；不要用不带 k 归一的"同总比特数"比较（OmniQEC 的做法）；不要引用 two-gross 在 Table 2 里带方括号的测量 LER（那是假设值，不是数据）。

**5. 对入围码的逻辑操作可行性检查（廉价版，不做完整 LPU）**
- 平移自同构对逻辑空间的作用：计算 Z_ℓ×Z_m 平移产生的逻辑 CNOT 群的大小/秩，看是否像 gross 码那样"≤2 个生成元生成"（2506.03094 App. A.2 的性质，对新码未必成立）。
- 逻辑算符的最小权重表示：LPU / gauging 的辅助比特数随被测算符权重增长（2407.18393 摘要的 Θ(w)；2410.02213 摘要的"线性于权重"）；对每个入围码计算 X/Z 逻辑基的最小权重（MILP），与 gross 码的值对照。
- 新码若与 gross 同属 BB 且 (ℓ,m) 有"toric layout"（2506.03094 Sec. 2.1 脚注 2：其几何描述只覆盖有 toric 布局的 BB 码），才可能直接套用 Tour de gross 的 LPU 构造；否则要用通用 extractor / adapter，开销无现成数字。
- 把结果作为"可操作性"一栏写进 H-003 的结果表，不并进 Q。

**6. 动手前还要补读**：Tour de gross 的 App. A.1–A.3、A.8（逻辑基、LPU 构造、距离验证）；2407.03973（ES24，BB 码的逻辑算符与折叠横向门）；2605.21898 App. C 的 morphing 电路细节；2507.19430 Table 1 的 BB 对照行。
