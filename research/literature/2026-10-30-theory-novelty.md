# 理论 A、B 的新颖性核查（lit-scout，2026-10-30）

对象：`research/theory/2026-10-29-B-sufficient-criterion.md`（δ 余链、负环 / 两钩子证书）与 `research/theory/2026-10-29-A-period-lower-bound.md`（T(P) 周期下界、对性质障碍）。只读检索，没有下载文件。

## 读了什么

- **SBB，arXiv:2603.05481 v2 HTML 全文**（152,633 字符，分三次读完：0–100k 定向读两遍，100k–末尾读一遍，包括 App. A–H）。重点是 Sec. II.1 的定义、Prop. 3、Cor. 1 证明、Prop. 4 证明、Sec. IV.3、Sec. VII、App. G、App. H.1–H.2（Prop. 5、6）。
- 看了 abs 页或 HTML 摘要的：Li 等 2509.26494（HTML 前 100k）、Liang 等 2609.37231（HTML 前 100k）、Manes–Claes 2308.15520、Webster–Jacob–Higgott 2603.22532、Delfosse–Paetznick 2304.05943、Delfosse–Beverland–Tremblay 2109.14599、Tremblay–Delfosse–Beverland 2109.14609、Tan–Stambler 2409.02193、Ghosh 等 2610.03429、Chu 2609.39705、Hirai 等 2603.01628、Kishony 等 2602.09099、McEwen–Bacon–Gidney 2302.02192、Rodatz–Poór–Kissinger 2410.17240、2608.02773、2608.05518。
- Shaw–Terhal 2407.16336 与 2604.09797 用的是项目已有的笔记（`novelty-distance-preserving-bb.md`、`novelty-interleaved-circuits.md`）。
- arXiv API 按日期倒序查了两组：abs 含 "circuit distance" / "circuit-level distance" / "hook error" 的 30 条（最新到 2610.33347，2026-10-23），以及 "bivariate bicycle" / "syndrome extraction" 的 25 条（最新到 2610.35735，2026-10-26）。WebSearch 查了 cochain / coboundary / round offset、depth lower bound + circuit distance、hook cancellation across rounds 三组关键词。
- 任务里写的"Liang et al. 2503.03827"实际是扭曲环面码的构造论文（Gröbner 基，[[120,8,12]] 等），abs 页没有任何电路内容，与本问题无关，可能是编号记错了。"Bacon / Rodatz 等的时空码 2405.xxxxx"我没有定位到确切编号。Rodatz 等真正相关的论文是 2410.17240（ZX 保距离重写做 Floquet 化），它不涉及 X/Z 交错的形式化。

## 结论

| 项 | 判定 | 置信度 | 必须引用 |
|---|---|---|---|
| 1. δ 余链；体内可分段 ⇔ δ 是上边缘 | **新**（SBB 的非交错是 δ 为常数的特例） | 中高 | 2603.05481（Sec. II.1 定义、Cor. 1、Thm. 1）；Z₂ 正确性约束引 2509.26494 |
| 2. 提升 = 差分约束 / 负环；两钩子证书 | **新**（提升 / 检测的机制本身是定性已知的） | 中高 | 2603.05481（Prop. 3 后的讨论、App. G） |
| 3a. P ≥ 9、P ≥ 10（平移不变单辅助，gross 与 [[90]]） | **新** | 高 | 2603.05481（Prop. 4、5）；2308.07915（深度 7 的 936 个变体）；2603.21499、2509.26494（只关于正确性的深度 ≥ 7） |
| 3b. "校验里每一对比特都落在最小权重逻辑里"障碍 | **部分已知**：机制是经典的钩子对齐，SBB Prop. 4 是它的数值版本；把它写成显式的对覆盖性质，再与平坦性组合，是新的 | 中 | quant-ph/0110143（钩子）；2603.05481 Prop. 4；项目自己的 [[18,4,4]] 结果 |

### 1. δ 余链与"可分段 ⇔ 上边缘"

SBB 是最接近的工作。我通读了全文，它没有任何逐对的轮次偏移、势函数、余链、上边缘、优先图或环。原文的相关定义如下：

- 非交错："all X-type CNOTs precede all overlapping Z-type CNOTs"，或者反过来（Sec. II.1）。"交错"没有正式定义，只有一句 "CNOTs from checks that share data qubits may be interleaved"。
- Cor. 1 的证明靠插入无错空闲，使电路 "temporally partitioned into X- and Z-type parts"。它不重标轮次，也不讨论多轮之间怎么处理。
- 多轮："they may be staggered so that a new round can begin before the previous one ends"。深度定义为 T^(m)/m 的极限，并说 "the depth is amortised over many rounds"。
- App. H 的结尾只写到 "non-staggered, interleaved variants" 作为可能的方向。Sec. VII 把轮间重叠下怎么保距离列为 "an important topic for future work"。

所以，"一个流水交错电路在什么时候可以通过逐校验重标轮次化成非交错电路"这个问题，SBB 没有提出，也没有给答案。理论 B 的命题 3(a)（⇔ δ = b_z − a_c）回答了它，是新的。命题 3(c) 是 SBB Cor. 1 的另一种证明，必须这样表述并引用 SBB。

其他的形式化都只停留在**单轮、Z₂** 层面。Li 等 2509.26494 定义了一个 "contamination matrix"，正确性条件是：每一对重叠的 X、Z 校验上，"XX-first orderings over the shared qubits ... must be even"（这一说法他们归于 Zhang 等）。这是给每对校验赋一个 Z₂ 值，不是给每对校验赋整数轮次；文中没有上同调语言，并且明确声明 "it makes no claim about circuit distance"。它的 "periodic" 指同态扭曲，不是时间周期。理论 B 的 Lemma 2（|Q| = 2 时两个台阶指标相等）可以看成这个正确性条件在整数、多轮上的加强版，写论文时应当引用 2509.26494 来说明这层关系。

以下几篇都没有类似的对象：Tremblay–Delfosse–Beverland 2109.14609（coloration 电路，abs 只给深度上界）；Manes–Claes 2308.15520（HGP 码对任意电路距离稳健，abs 中没有排序形式化）；Webster–Jacob–Higgott 2603.22532（距离算法基准）；Delfosse–Paetznick 2304.05943（时空码，abs 中没有排序、上同调或距离结果）；McEwen–Bacon–Gidney 2302.02192（时间动态电路，abs 中没有 X/Z 跨轮形式化）；Shaw–Terhal 2407.16336 与 2604.09797（时间反演折叠，Prop. 3）；2608.05518（这里的 "X-to-Z round-scheduling ratio" 指 X 轮与 Z 轮的比例，是另一回事）。在 WebSearch 和 arXiv API 结果里，也没有看到"syndrome schedule + cochain / coboundary"的用法。

我看过 abs 但没读全文的有 2109.14609、2308.15520、2304.05943；它们的正文里有没有单轮版本的类似记号，我没有核对。不过这些都是 2023 年以前、单轮的工作，SBB 2026 年把非交错本身当作新概念提出，说明圈内此前没有这层形式化。

### 2. 负环 / 差分约束 / 两钩子证书

SBB 只定性描述了机制：Prop. 3 只是不等式，原因是 "error propagation happens over multiple time steps"，交错让误差在扩散前部分被探测；它还说 "One way to avoid this detection is to consider non-interleaved circuits"。App. G 只提了一句 "improves the detection of harmful hook errors"。文中没有"给定一个扩展码逻辑，判断它能否提升成电路故障"的判定问题，也没有证书。

其他工作：

- Liang 等 2609.37231 的 "fault-response certificate" 是电路距离的下界证书（按故障束分配计数，用 CNOT 顺序让钩子横向于逻辑弦）。它用了链复形和上同调，但没有差分约束或负环，也不针对跨轮交错。
- Ghosh 等 2610.03429 给出电路距离的 LP **上**界（MacWilliams 恒等式）和 SDP 证书。abs 中没有排序环。
- 表面码、色码的"钩子不对齐逻辑"系列（Hirai 等 2603.01628、Kishony 等 2602.09099 与 2603.28852、2610.33347 junction hooks）都是靠几何上的钩子朝向，没有读出时序的环判据。

判定：定理 6 和推论 7 是新的。论文里的措辞应当是"把 SBB 定性描述的交错探测机制写成可判定的差分约束系统，并给出可手核的证书"。

### 3. 理论 A：保距离电路的深度 / 周期下界

已有的下界都**只针对正确性，不针对距离**：

- Zhang 等 2603.21499 用求解器证明 IBM 列出的 BB 码都不存在深度 6 的电路。
- Li 等 2509.26494 自称 "first analytic, family-wide impossibility result"，结论是深度 ≥ 7，但明确排除了 staggered / amortised 模型，并且写道 "Depth does not determine fault tolerance"。
- Delfosse–Beverland–Tremblay 2109.14599 与 Chu 2609.39705 给的是局部连通性下的深度或割下界，与距离无关。

与距离相关的已有结果都是**在给定电路类里给距离上界**：

- SBB Prop. 4：gross 的任何非交错电路 d_circ ≤ 11。证明对一个校验的 90 种 CNOT 顺序逐一做数值搜索，"In every case we find a logical operator of weight at most 11"，其中 "45 of the 90 cases have weight at most 10"。
- SBB Prop. 5："uniformly-tiled non-interleaved" 的 gross 电路 ≤ 10。
- SBB Prop. 6：三色铺排只剩 3 种。
- IBM 2308.07915：gross 的 936 个深度 7 变体全部 ≤ 10（引自项目已有笔记）。

这些结果都没有对交错 / 流水电路给出"周期 ≤ P 时必然丢距离"的下界。SBB 自己把交错电路列为开放问题（"our proof does not apply to interleaved circuits"）。所以理论 A 的 P ≥ 9 和 P ≥ 10（体内、类 T(P)、两个码）是**新的**，置信度高：我的检索覆盖到 2026-10-26，没有竞争者。表面码那边有 Kishony 等的"最小周期 6"（2602.09099）和 Hirai 等的"最小深度 4"，但那是能够达到的构造，不是保距离的下界，码也不同。

对性质障碍（定理 1）：

- 机制本身是经典的：两比特钩子与最小权重逻辑对齐会丢一个距离（Dennis–Kitaev–Landahl–Preskill quant-ph/0110143 的表面码钩子）。
- SBB Prop. 4 实际上就是这个机制在非交错情形的数值版本。在非交错电路里，所有钩子都是"平坦"的，而 ≤ 11 正好等于 d − 1。但 SBB 没有把它写成"每一对都在最小权重逻辑里"的性质；我专门核对过，原文没有这样的对覆盖陈述。
- 理论 A 新增了两点：一是把它写成显式的、与码无关的性质；二是用平坦性（G 在钩子边上是否为常数）把它推广到交错电路，从而得到 T(8) 中没有满距离电路。

所以判定为**部分已知**。论文应写成"SBB Prop. 4 的数值步骤可以由一个对覆盖性质解析地替代，并推广到交错类"，并引用 SBB Prop. 4 和项目自己的 [[18,4,4]] 结果。

## 建议的措辞（英文，供论文用）

- "Non-interleaved circuits [2603.05481] are exactly those whose round-offset cochain δ is constant. We show more generally that a pipelined circuit can be re-timed into a temporally partitioned one if and only if δ is a coboundary."
- "Strikis et al. note that interleaving lets part of a propagating error be detected [2603.05481]. We make this precise: whether an extended-code logical lifts to an undetected circuit fault is a system of difference constraints, and a negative cycle (in the simplest case, two hooks read in opposite orders by two private readers) certifies that it does not."
- "Previous lower bounds on syndrome-circuit depth concern correctness only [2603.21499, 2509.26494]; distance bounds are known only for non-interleaved circuits [2603.05481, Props. 4–5]. We prove that translation-invariant single-ancilla circuits with period P ≤ 9 cannot reach full distance on the gross and [[90,8,10]] codes."

## 局限

- 2109.14609、2308.15520、2304.05943、2407.16336 没有读全文，只读了 abs 或已有笔记。它们是单轮的老工作，在其中出现整数轮次余链的可能性低，但不能排除。
- arXiv API 只检索标题和摘要；会议论文和没有上 arXiv 的工作没有覆盖。
