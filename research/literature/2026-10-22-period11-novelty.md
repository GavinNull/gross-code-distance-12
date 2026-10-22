# 周期 11 电路（STATE 已确认结果 16–18）的新颖性与必引文献
检索日期：2026-10-22；重点窗口：2026-10-09 之后。

检索词与来源：arXiv API（按提交日期倒序）`abs:"bivariate bicycle"`（40 条，最新到 2610.28867，2026-10-20）、`abs:"circuit distance" OR "circuit-level distance" OR "effective distance"`（30 条）、`abs:"gross code" OR "144,12,12" OR "90,8,10"`（25 条）、`abs:"syndrome extraction" AND (schedule OR idle OR depth OR interleaved OR pipelined)`（40 条）；WebSearch：“gross code circuit-level distance exactly 10”、“bivariate bicycle idle noise depth trade-off”、“pipelined syndrome extraction qLDPC circuit distance”、“interleaved … Strikis Beverland follow-up”、“bivariate bicycle idle error sweep”；qldpc-challenge 的 issues（`144`）、PR 列表（最近 25 条，到 2026-10-22）、issue #1026 全文。读了正文的：2603.05481 v2 HTML（Sec. I、II、IV.3、V.2、VI、App. F–H，定向检索，非逐页）、2503.10988 v2 HTML（Sec. 4、App. D）。其余只读 abs 页或 API 摘要，下文逐条注明。

## 结论（3-5 行）
1. 2026-10-09 之后没有出现任何 gross 或 [[90,8,10]] 的 d_circ = d 电路，也没有任何单辅助、流水回绕调度的 BB 电路距离结果。搜索引擎里唯一的“gross d_circ = 12”条目是本项目自己的公开仓库（GavinNull/gross-code-distance-12，Release v1.0，写的还是周期 18）。
2. IBM gross 电路的 d_circ 在文献里一直只有上界 ≤ 10（2308.07915；Tesseract 2503.10988 也只写 “at most 10”，其 MaxSAT 精确计算只做了 [[72]] 和 [[90]]）。我们 R ≤ 3 的精确值 10 是第一个精确值，但必须带 “R ≤ 3” 和噪声模型限定。
3. 最有力的新框架来自 Strikis 等自己的 Prop. 5（App. H.1）：**任何均匀铺排（uniformly tiled）的非交错 gross 电路 d_circ ≤ 10**。u11 正是均匀铺排的，交错后到 12，所以“高出 2”可以直接对着一个已发表的定理说，而不只是对着自己的 d_ext。这是本轮最值得写进论文的一点。
4. 证据强度：(1)(2) 中高；(3) 中；(4) 是文献整理，不涉及新颖性。

## 关键论文

| arXiv | 作者 · 年份 | 做了什么 | 与本项目关系 | 关键数字（附出处） |
|---|---|---|---|---|
| 2603.05481 v2（2026-09-14，无 v3） | Strikis, Browne, Beverland | LRC 框架；非交错 ≤ 11（Prop. 4）；均匀铺排非交错 ≤ 10（Prop. 5）；交错不降距离（Sec. VII） | 问题 (1)(3)(4) 的核心 | Prop. 5（App. H.1）：uniformly tiled 定义为所有 X 校验做相同操作、彼此平移，任意这类非交错 SEC d_circ ≤ 10；Sec. I 把 LRC 称为先前 “pipelined product colouration circuits” 的推广，引 [48]；App. G.2 的单轮比较把 idle 噪声设为零以隔离 CNOT 顺序的影响；App. F 认为 PropHunt、AlphaSyndrome 电路深度大增抵消了距离收益；Sec. VI 的 Tanner200 轮间重叠后深度 21 → 18 |
| 2308.08648 | Xu 等（Nature Phys. 20, 1084, 2024） | 中性原子恒定开销容错；pipelined product coloration circuits | “流水”这个词与做法的先例 | 作为 Strikis [48] 被引（本次从 2603.05481 参考文献核实，未读 2308.08648 原文） |
| 2308.07915 v2 | Bravyi 等（IBM） | gross 与 [[90]] 码及深度 7 电路 | 基线 | Table 1：gross ≤ 10，[[90]] ≤ 8；Sec. 6：每周期 2n 个显式 Idle 位置，idle 噪声只加在显式 Idle 门上（`noise-models.md`） |
| 2503.10988 v2（2025-08-06） | Aghababaie Beni, Higgott, Shutty（Tesseract） | MaxSAT 精确电路距离 | 问题 (2) 的最近先例 | App. D：[[72]] = 6、[[90]] = 8 为 MaxSAT 精确值；gross 只写 “at most 10”，取自 IBM 的上界，没有自算（本次读 HTML 核实）；Fig. 3 题注写 “has circuit distance 10”，没带 “at most”，引用时要注意 |
| 2603.22532 v2 | Webster, Jacob, Higgott | 精确距离算法基准 | 问题 (2) | Sec. 5.5.3 / Table 28：BB 电路族只算完 [[72]]，gross 没有精确值（旧笔记 `novelty-gross11-ibm72.md`） |
| 2506.03094 v1 | Yoder 等（Tour de gross） | 模块化架构 | 问题 (2)(4) | Table 4：gross d_circ ≤ 10（旧笔记）；idle 指令逻辑错误率约 10^-8.8 @ p=10^-3（检索摘要转述，未读原文，未核实） |
| 2603.01628 v2（2026-06-20） | Hirai, Ikari, Ueno, Suzuki | 表面码 “ZX interleaving” 调度，最小深度下保持满距离 | 问题 (3) 的跨码族先例 | 摘要：交错 Z/X 稳定子铺排，模拟中达 d，已有最小深度方法为 d−1；表面码、数值，不涉 d_ext、不涉 qLDPC |
| 2609.40319 v1（2026-09-30） | Durazo Rocha 等（LocalASC） | 两块码有序边着色调度，含 X/Z 交错的奇偶约束 | 交错调度的近邻 | 摘要：重叠 X/Z 对上 X 先于 Z 的共享比特数必须为偶数；不报 d_circ，不提 gross、[[90]]、idle |
| 2509.26494 v4（2026-10-16） | Li 等 | 单轮、单辅助下 BB 码深度 6 不可能，7 最优（DRAT） | 深度下界背景 | 摘要：结论限于单轮、不跨轮错开；不讨论 d_circ |
| 2603.21499 | Zhang 等（ASC） | SMT 深度最优调度 | 问题 (4)：深度与 LER | 摘要：深度约降 50%，LER 平均降 7–8 倍（一般 qLDPC）；BB 实例证明无深度 6 |
| 2108.10457 | Gidney 等 | SD6 / SI1000 噪声模型 | 问题 (4)：λ 取值依据 | Table 2：SD6 idle = p；SI1000 idle = p/10（另有 resonator idle 2p）（`noise-models.md`） |
| 2609.39522 v2（2026-09-30） | Layer codes | 调度深度约减半，idle 容忍度 | 问题 (4)：idle 强度扫描的方法先例 | 摘要：可容忍比旋转表面码长 1.7–3.0 倍的 idle 间隔；非 BB |
| 2606.30592 v1 | Bi, Chang, Puri | 偏置辅助比特 | 问题 (4) 旁证 | 摘要：p = 2×10^-3 处 LER 近一个数量级改进；不是去极化 SD6 |
| 2601.12509 / 2601.17580 | AlphaSyndrome / PropHunt | 调度搜索 | 问题 (4)：深度换距离的反例 | 经 Strikis App. F 转述：深度大增抵消距离收益（非 BB 码） |
| qldpc-challenge #1026（2026-09-12 至 10-05） | unitaryfoundation | 电路层交错调度回填 | 抢发监测 | 交错 + 偶数奇偶约束后 BB 型电路从 19–21 层降到 8–9 层；无 gross、无 [[90]]、无 d_circ = d；不引 Strikis |

2026-10-09 之后新出现、已排除的条目（只读摘要）：2610.28867、2610.28748、2610.28008、2610.24503（解码器）；2610.25213 LiftDiff、2610.13880 Bicycle Race（码搜索；后者模拟 [[102,20,10]]、[[120,24,10]]，不涉 gross/[[90]] 电路）；2610.18130、2610.17612、2610.15975、2610.15857、2610.13879；2610.09749（Shor/Steane 型电路约简，非 qLDPC）。均无 BB 电路距离。

## 新颖性判断

**(1) 有没有先前或同期的 gross / [[90]] 电路达到 d_circ = d，或流水回绕单辅助调度？** 没有找到。外部文献里 gross 最好的是 Strikis Fig. 12 的 11（深度 8，他们猜想、我们 E-014 证明），[[90]] 最好的是 IBM 电路的精确 8（Tesseract）。10-09 之后 arXiv 上 BB 相关的 40 条摘要、电路距离相关的 30 条摘要里，没有一篇报告 BB 电路的 d_circ 改进；qldpc-challenge 的电路层只有通用顺序调度和不收敛的上界。“流水”本身不新：Strikis 的 LRC 允许轮间错开（Sec. II.1），并说明它推广了 Xu 等的 pipelined product colouration circuits。所以能说新的不是“流水”，而是“均匀、回绕流水 + X/Z 交错，在单辅助比特类里达到 d_circ = d”。外部唯一会被搜到的“gross = 12”是我们自己的仓库，Release v1.0 仍写周期 18；论文 revision O 已是周期 11，建议发新 release，否则读者会看到两个周期数。

**(2) IBM gross 电路有没有先前的精确值？** 没有。IBM 原文是 BP-OSD 上界和猜想；Tour de gross、Tesseract 都只写 ≤ 10，Tesseract 的 MaxSAT 只覆盖 [[72]]、[[90]]；Webster 等的基准只算完 [[72]]。我们的“每轮恰 144(Z)/288(X) 个权重 10 逻辑，R ≤ 3 无更低权重”是第一个精确值，但只到 R ≤ 3，不能写成任意 R。另有一点要注意：IBM 自己的噪声模型只在显式 Idle 门上加 idle 噪声（每周期 2n 个），而我们的枚举是 SD6。对这个电路两者的 d_circ 是否相同我没有核对，所以要写明噪声模型。

**(3) 交错或流水把 d_circ 提到 d_ext 之上，“高出 2”是否新？** 外部文献里只有两类东西：Strikis Sec. VII 的单向结论（交错不降、“may increase”，没有实例），以及表面码上 Hirai 等的 ZX 交错（最小深度下 d 对 d−1，数值，另一码族，不是 d_ext 的语言）。BB 码上没有任何 d_circ > d_ext 的已发表实例。

这里我认为最好的写法是对着 Strikis Prop. 5，而不是对着我们自己的 d_ext。理由是：u11 在 Strikis 的意义下是均匀铺排的（所有 X 校验做同样的操作、彼此平移），Prop. 5 证明了这一类里所有非交错电路 ≤ 10。我们只加了交错就到了 12。这比“比自己的 d_ext 高 2”更硬，因为审稿人可以直接去查一个已发表的定理，也不用先接受我们的 d_ext 定义。需要核对的一点：Prop. 5 的定义只说 X 校验（“the same operations uniformly, but translated”），没说 Z 校验；u11 两侧都平移不变，应当落在定义内，但写之前请 lead 对一下 App. H.1 原文。

对 gross 要分清两个“高出”：高出自己的分段对应电路（d_ext = 10）2，高出均匀非交错类上界（Prop. 5）2，但只高出全部非交错电路的最优值（11）1。对 [[90]]，“高出所有可分段电路 2”在我们 10-15 的 c16 结果里就已经有了（也已随 v1.0 公开），c11 的新东西是周期 16 → 11，不是“+2”。所以论文里“两个电路都比自己的 d_ext 高 2”可以写，但不能把 [[90]] 的 +2 说成本轮首次。

**(4) idle 噪声与深度的权衡。** 没有找到专门扫描 BB 码 idle 强度的论文。可引的有：Strikis 把低深度和少 idle 列为设计目标，App. G.2 正好也把 idle 设为零来隔离调度的作用，这给我们的 λ = 0 分析一个现成的方法先例；App. F 指出深度大增会抵消距离收益，这正是我们 λ = 1 下差 6–17 倍的情形，应当主动承认。λ = 0.1 可以用 SI1000 的 idle = p/10（2108.10457）作物理依据，但 SI1000 别的参数也不同，只能说“idle 强度与 SI1000 相当”。

**最接近的三篇**：2603.05481（Prop. 4/5、Sec. VII、App. F–G）；2503.10988（IBM 电路精确值，gross 只有上界）；2603.01628（交错恢复满距离的表面码先例）。

**声称与复现**：本项目结果都是内部证明 + 内部 auditor 复核，没有外部复现。u11 的列表完备性还没有证书（STATE 19）。

**证据强度**：(1) 中高（arXiv API 只查标题/摘要，有 1–3 天滞后；会议论文和未上 arXiv 的工作没覆盖）；(2) 中高（三个最可能给出精确值的来源都直接核对了）；(3) 中（Prop. 5 是 WebFetch 读 HTML 得到，未逐字核对定义细节）；**抢发风险：低到中**，过去两周没有新竞争者，qldpc-challenge 已有交错驱动但只出上界。

## 对本项目的建议

**必须引用**：2603.05481（Prop. 4、Prop. 5、Sec. II.1 错开、Sec. VII、App. F、App. G.2）；2308.07915（码、基线、≤ 10 / ≤ 8、显式 Idle 噪声）；2503.10988（[[90]] 精确 8；gross 只有 ≤ 10）；2308.08648（pipelined product coloration circuits）；2108.10457（SD6、SI1000 的 idle 系数）；2506.03094（gross ≤ 10）。
**建议引用**：2603.22532（精确距离算法，gross 未完成）；2603.01628（表面码 ZX 交错恢复满距离）；2603.21499 与 2509.26494（深度最优与深度下界，说明周期 11 的代价）；2609.40319（交错的偶数奇偶约束）；2601.12509、2601.17580（经 Strikis App. F，深度换距离的反面例子）。
**可选**：2609.39522（idle 间隔容忍度的扫描方法）、2606.30592（偏置辅助，另一条挡钩错误的路）。

**建议措辞（英文稿）**：

- 主结论：“We give period-11, translation-invariant, single-ancilla syndrome-extraction circuits in which every X and every Z check uses the same CNOT order, with rounds pipelined and wrapped around the period. Under SD6 noise their circuit distance equals the code distance, 12 for the gross code and 10 for [[90,8,10]], for any number of rounds and in both memory bases.”
- 与 Prop. 5 对照（推荐作为“+2”的主表述）：“Proposition 5 of Ref. [2603.05481] shows that every uniformly tiled, non-interleaved circuit for the gross code has circuit distance at most 10. Our gross-code circuit is uniformly tiled and differs only in being interleaved; it reaches 12. Equivalently, it exceeds by two the extended-code distance of its own CNOT order, which by Proposition 3 of Ref. [2603.05481] is the circuit distance of the corresponding segmentable circuit. To our knowledge this is the first circuit for a bivariate bicycle code shown to exceed its non-interleaved counterpart by two.”
- 不能漏的对照句：“The best non-interleaved gross-code circuit has circuit distance 11 [2603.05481, Fig. 12; proven in this work], so relative to all non-interleaved circuits the gain is one.”
- 流水的出处：“Staggering consecutive rounds is permitted in the model of Ref. [2603.05481] and generalizes the pipelined product coloration circuits of Ref. [2308.08648]; the new ingredient here is interleaving X- and Z-check CNOTs on each data qubit within a uniform, wrapped-around schedule.”
- IBM 精确值：“By exhaustive enumeration we find that the depth-8 circuit of Ref. [2308.07915] has circuit distance exactly 10 under SD6 for R ≤ 3 rounds, with 144 (Z) and 288 (X) weight-10 logical faults per round. Previously only the upper bound d_circ ≤ 10 was known [2308.07915, 2506.03094, 2503.10988].”
- LER 段：“With idle errors removed (λ = 0), the period-11 [[90,8,10]] circuit has a lower per-round logical error rate than the depth-8 circuit of Ref. [2308.07915] at every sampled p in 2–5×10⁻³ with both decoders. At idle strength p/10, comparable to the SI1000 model [2108.10457], the two are indistinguishable, and under full SD6 idle noise our circuit is worse by a factor of 6–9 with BP-OSD and 9–17 with Relay-BP. This is the trade-off anticipated in Ref. [2603.05481, App. F]: the gain in circuit distance is paid for in idle locations, so the benefit depends on how idle errors compare with gate errors on the target hardware. Setting idle noise to zero to isolate the effect of CNOT ordering follows Ref. [2603.05481, App. G.2].”

**不能写**：
- “first distance-preserving BB circuit”（[[72]] = 6、[[70,6,9]] = 9 已有先例，见 `2026-10-15-bb90-novelty.md`）；
- 把 [[90]] 的 “+2” 当作本轮新结果（c16 已有，且已公开）；
- “IBM's circuit has d_circ = 10”而不带 “R ≤ 3” 和 “SD6”；
- “first pipelined schedule”（Strikis、Xu 等已有）；
- 不带 λ = 0 限定的 “outperforms IBM”；gross u11 在 λ = 0 下与 IBM 只是相当（STATE 18），不能和 [[90]] 写成同一句；
- “11 is the minimum period”（STATE 17）。

**后续**：
1. 发新的 GitHub release，把公开描述从周期 18 改到 11，避免搜索结果里两个周期数并存。
2. 请 lead 或 auditor 逐字核对 Prop. 5 的 uniformly tiled 定义是否涵盖 X、Z 两侧都均匀且跨轮错开的电路；如果定义要求非错开，主措辞要改成“Prop. 5 的类加上错开仍 ≤ 10”是否成立的问题，届时再查。
3. 核对 IBM 电路在 IBM 自己的显式 Idle 噪声模型下 R ≤ 3 是否仍为 10（预计相同，但没算过）。
4. 下次复查：2603.05481 是否出 v3；qldpc-challenge 电路层是否出现 n = 144 或 n = 90 的交错条目。
