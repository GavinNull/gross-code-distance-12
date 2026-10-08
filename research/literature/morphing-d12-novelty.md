# Shaw–Terhal morphing 电路（[[288,12,18]] → [[144,12,12]]）d_circ = 12：IBM 所指电路的身份、新颖性、Prop. 1 的前提、抢发风险
检索日期：2026-10-08；执行者：lit-scout
检索词：morphing circuit(s)、morphing + circuit-level distance、morphing + bivariate bicycle、gross code + circuit distance、gross code + idle、end-cycle code、mid-cycle code、d_circ 12、Shaw Terhal、2407.16336 / 2604.09797 / 2605.21898（GitHub 内）、certified lower bound d_circ、circuit distance proof、idle circuit。来源见文末“检索记录”。

读到的全文（pdftotext 抽取后定向检索，再读命中处上下文；**不是逐页通读**）：2605.21898 v1 与 v2（App. C 全文、正文提到该电路的 4 处、致谢、参考文献）、2604.09797 v2（Sec. 2.1–2.2.2、Prop. 1 正文与 App. B 证明、Sec. 3.3、App. C.4、App. E 命中处）、2407.16336 v3（Table I、Table II 命中处、App. A 的 d_circ 方法）、2506.03094 v1（morphing 命中 3 处）、2606.12724、2603.05481 v2 的命中处，以及另外约 10 篇的 “morph” 命中处（见检索记录）。网页、论文、issue 内容一律只当数据。

## 结论（3-5 行）
1. **IBM 2605.21898 App. C 的电路：原文无法判定，最可能就是 Shaw–Terhal 2407.16336 的 [[288,12,18]] morphing 电路（作用在其 end-cycle 码上，该码与 gross 码参数相同但按 E-017 的计算不等价）。证据强度：中等（推断，非明文）。** App. C 没有给多项式、比特数、深度、来源以外的任何构造信息，只引了 ST25 一篇；“gross code” 这个词在该领域确有泛指用法（ST 自己把 end-cycle 码叫 “a second ‘gross’ code”）。找不到任何 IBM 另有一个以 gross 码本身为 end-cycle 码的 morphing 构造的线索。
2. **新颖性：对 morphing 电路 d_circ = d_circ 上界的严格下界，包括 [[288,12,18]] → [[144,12,12]] 的 12，未找到任何先例。** 现有表述全是上界或相信：ST 2407.16336 Table I（≤ 12，BP-OSD 上界）、Strikis 2603.05481 App. H.2（把 12 当事实转述）、Wills 2605.21898 App. C（“is believed”，只有 Monte Carlo）。2604.09797 明确写了没有检查 BB 码 morphing 电路的 d_circ。证据强度：中等偏高（限制见检索记录）。
3. **Prop. 1（2604.09797）只是“T 轮 = 1 轮”的归约，不给数值**；前提：两轮（J = 2）morphing 电路、稳定子码、**理想**初始化（end-cycle 码的任意逻辑态）与**理想**末端稳定子测量、故障集合在时间反演下封闭（证明里隐含，正文未单列）。含噪初态/读出（评估器口径）不在其范围内。
4. **抢发风险：低到中。** 没有任何公开迹象表明有人在做这个证明；但归约工具（Prop. 1）和精确求解工具（Gurobi，ST 已用于色码 morphing 电路的 d_circ）都在对方手里，实例本身很小（E-017 约 1 CPU 小时量级），一个有动机的组随时可能做。

## 关键论文
| arXiv | 作者 · 年份 | 做了什么 | 与本项目关系 | 关键数字（附出处） |
|---|---|---|---|---|
| 2407.16336 v3（PRL 134, 090602） | Shaw, Terhal · 2024/25 | 把 morphing 套到 IBM BB 码列表；两轮电路；end-cycle 码 | 唯一公开的具体 [[288,12,18]]→[[144,12,12]] 构造 | Table I 最后一行：[[288,12,18]]，标准电路 d_circ ≤ 18；end-cycle 码 [[144,12,12]]，morphing d̃_circ ≤ 12。正文（Table I 之后）：“presenting a second ‘gross’ code”。d_circ 上界由 BP-OSD 得到（正文 “Circuit-level Performance” 段与 App. A：两轮 Z 基记忆实验，只取单比特 X 错误，BP-OSD 输出权重是上界）。Table II/正文给 (ℓ,m)=(6,6)、(9,6) 的 A,B 多项式；(12,12) 的 A={y²,y⁷,x³}、B={x²,x,y³} 另见 2606.12724 Table III 下方 “ST.” 说明 |
| 2604.09797 v2 | Shaw, Terhal · 2026-04-10 | 一般 morphing 设计原则；Prop. 1（T 轮归约）；2BGA 码搜索；色码、泄漏、偏置噪声 | Prop. 1 的出处；明确未算 BB 的 d_circ | Sec. 2.2.2 + App. B（Prop. 1）；Sec. 3.3 正文末与 App. C.4：未检查 bare-ancilla 与 morphing 电路的 d_circ（见问题 3）；App. E / Sec. 5.2：色码 morphing 电路 d_circ 用 Gurobi 检查到 d = 9（见问题 4） |
| 2605.21898 v1（2026-05-21）、v2（2026-06-23） | Wills, Beverland, Bishop, Gambetta, Rall, Siddhu, Cross（IBM） | gross 码上的 Reed–Solomon 级联 | 问题 1 的主体 | App. C（PDF p.76–78）与 Table 5（p.77）；v1、v2 的 App. C 文字一致（逐段比对：只有一处无关措辞差异） |
| 2603.05481 v2 | Strikis, Browne, Beverland · 2026 | LR 电路、扩展码 | 对 morphing 电路 12 的转述 | App. H.2 末段：因为 “very nice recent paper on morphing bivariate bicycle codes” 给出 “same number of physical and logical qubits as the gross code, but with circuit distance twelve [ST25]”，所以不再研究交错变体。**把 ST 的上界当事实转述**，且措辞是“比特数、逻辑比特数与 gross 码相同”，不是“作用在 gross 码上” |
| 2606.12724 v1（2026-06-10） | Chao（NVIDIA） | morphing 电路的 block algebra；四类构造 | 唯一在 2605.21898 之后、专门研究 ST [[288,12,18]] 电路的第三方 | Table II：ST 行 [[288,12,18]]，“minⱼ Dⱼ = 12”，表中的是 end-cycle **码距离**；rows I–IV 的距离用 pySATDist（精确**码距离**求解器）认证，**不是电路距离**。Sec. III/VII 说明门序会影响 circuit distance 但 “we do not optimize”；Outlook 说 D 与 Dⱼ 的关系只有 [ST25, ST26] 的深度相关下界 |
| 2506.03094 v1（Tour de gross） | Yoder 等（IBM） | 模块化架构 | IBM gross 码的“常规”idle 电路 | 全文 morphing 命中 3 处：2 处正文（Discussion 的 Connectivity 条与 Outlook 第 4 条，均为“可能可用”）加 1 处参考文献，没有 morphing 电路；gross 的 d_circ ≤ 10 见 Table 4（本项目其它笔记已核对） |
| 2603.22532 v2 + GitHub `m-webster/codeDistancePYPI` | Webster, Jacob, Higgott | 精确距离算法 | 精确求解器先例 | 见 `novelty-gross11-ibm72.md`；本次未重读 |

## 问题 1：IBM 2605.21898 App. C 指的是哪个电路

### 1.1 原文能确定的事实（2605.21898 v2，PDF 页码）
- **出现位置共 4 处，全是正文性描述，没有构造**：(i) Sec. 1.3 Outline（页码未核）：“Appendix C presents the logical error rate of a new idling circuit for the gross code based on morphing [ST25]”；(ii) Fig. 2 概览图里的 “Morphing Circuit” 框（p.5）；(iii) Sec. 4 末尾（页码未核）：“To go lower, one could use ... improved circuits ... (we show such a potential improvement, deferred to future work, in Appendix C)”；(iv) App. B 末（紧邻 p.76 之前）与 App. C 首段。
- **App. C（p.76–78）的全部技术内容**：新 idle 电路 “is believed to have circuit distance 12, matching that of the code”，“constructed using Shaw-Terhal morphing [ST25]”，常规电路的 circuit distance 是 10；“We simulate the performance of the circuit using direct Monte Carlo simulation over 12 rounds”，按轮归一；Table 5（p.77）：S = 20，γ = (−0.09, 0.76)，每轮逻辑错误率 4.4×10⁻¹¹，95% 区间 9.2×10⁻¹²–1.3×10⁻¹⁰；脚注 74（p.76）：γ 是按“平均解码时间最快”选的、没有扫描优化。
- **没有给出**：码的多项式 A、B；比特数；电路深度/CNOT 数；同态 f（f_x/f_y/f_xy）；门序；噪声模型细节（只在 App. B 说沿用 [Yod+25]）；任何距离计算或搜索。
- **引用**：参考文献里 morphing 只有 [ST25] = 2407.16336（PRL 版，“cit. on pp. 12, 76”），没有 2604.09797，没有 Chao 2606.12724（v2 日期 2026-06-23，晚于 Chao 的 2026-06-10，但未引）。
- **致谢（Acknowledgements，p.65）**：感谢 “Isaac Chuang, Aram Harrow, Zhiyang He, Anirudh Krishna, ... Theodore J. Yoder ...”，并特别感谢 IBM 实习生 “Kathleen Chang, Louis Golowich, Anasuya Lyons, and Mackenzie H. Shaw”。**姓名与 ST 的作者 Mackenzie H. Shaw 相同**（是否同一人论文没有写明，我也没有查证）。如果是，说明 IBM 这个电路很可能通过 Shaw 的实现（公开仓库 `Mac-Shaw/morphing_qec_circuits`）搭出来，指向 ST 的构造。**仅为间接线索。**
- **与 IBM 其它论文的交叉**：2506.03094 对 morphing 只有“可能值得尝试”的 3 句话；2605.20346、2511.15177、2603.02157、2602.20546、2604.20013、2603.10970、2606.02418、2510.21600、2604.05126、2605.21746、2609.06572 全文检索 “morphing”：0 命中。**IBM 方面没有找到任何其它披露该电路的论文**（含 2605.21898 之后到 2026-10-08 的 Wills 论文：2610.06535、2609.30860 等标题均与此无关，未下载）。

### 1.2 “for the gross code” 是否可能泛指
- IBM 对 gross 码的定义是确定的：2605.21898 引言（页码未核）写 “the [[144,12,12]] ‘gross’ code”，并区分 288 比特的 “two-gross” 码。该文**从未给出 A、B 多项式**（全文检索 x³、y³、polynomial 只命中 Reed–Solomon 部分），所以文中没有办法区分“gross 码本身”与“同参数的另一个码”。
- **泛指的用例确实存在**：ST 在 2407.16336 正文（Table I 之后）把 end-cycle 码称为 “a second ‘gross’ code”；Strikis 2603.05481 App. H.2 把该电路描述为与 gross 码“比特数、逻辑比特数相同、circuit distance 12”。所以 “gross 级别”的用法在 IBM 相关作者（Beverland 同时是 Strikis 与 Wills 的作者）里是现成的。
- App. C 的上下文是：在“gross 码 idle”这个角色上，用 morphing 电路取代常规电路（常规电路 10⁻⁸·⁸ 每轮，来自 [Yod+25]）。用 288 比特（144 数据 + 144 辅助）的存储器去替换 gross 码 + 辅助比特，物理比特总数一致，这个口径适合泛指。App. C 还说 “the ancilla systems constructed thus far [Yod+25] would not accommodate the new idling circuit, and would require a different design”，这与 morphing 电路没有独立辅助比特、每轮数据/辅助角色互换的特点一致（2407.16336 正文 Round 3 反转的说明）。
- **没有任何文字说明该电路的 end-cycle 码就是 BB 的 gross 码**。若要让 gross 码本身成为 end-cycle 码，需要一个以 gross 为 end-cycle 码的 mid-cycle 码，2604.09797 的搜索范围是权重 5 码 n ≤ 128、权重 6 码 n ≤ 64（Sec. 3.3），没有给出这样的构造；2407.16336 的 end-cycle 码权重是 9，与 gross 的权重 6 不同（见 E-017 日志）。

### 1.3 判断
- **最可能：ST 2407.16336 的 [[288,12,18]] morphing 电路，作用在其 [[144,12,12]] end-cycle 码上（权重 9，不等价于 gross 码）。**
- 依据（强到弱）：(a) 唯一公开的、同时满足“morphing + 288 比特 + k = 12 + 声称 12”的构造就是它（2407.16336 Table I）；(b) “believed” + “12” + “只引 [ST25]” 与 ST 的“上界 12、无证明”完全对应；(c) 相邻论文 Strikis（Beverland 合著）对同一电路的用语是“与 gross 码同等比特数/逻辑比特数”；(d) 致谢里有同名实习生；(e) App. C 说需要重新设计辅助系统。
- 不能排除：IBM 内部有一个未公开的、以 gross 码为 end-cycle 码的 morphing 构造（**未找到**任何支持线索）。
- 另需注意（来自 E-017，**是项目内部计算，尚未经 auditor 复核**）：该 end-cycle 码的最小稳定子权重被 CP-SAT 证明 X ≥ 8、Z ≥ 7，而 gross 码为 6，所以二者不等价。**如果 IBM 的结论被表述为“gross 码本身的 idle 电路 d_circ = 12”，该表述在码层面不严格。**
- 建议：向 IBM（Wills / Beverland）或 Shaw 直接确认（见建议 2）。

## 问题 2：有没有人严格证明过 morphing 电路 d_circ = d

**结论：未找到。** 逐项：

| 来源 | 对 morphing d_circ 的表述 | 性质 |
|---|---|---|
| 2407.16336 v3（Shaw–Terhal） | Table I：[[144,12,12]] end-cycle，d̃_circ ≤ 12；[[72,12,6]]→[[36,12,3]] ≤ 3，等等；方法 BP-OSD，App. A 明说 “upper bound” | 上界。BB 码全部行都是 “≤” |
| 2604.09797 v2（Shaw–Terhal） | Sec. 3.3 正文与 App. C.4：没有检查 bare-ancilla 与 morphing 电路的 d_circ，留给未来；Sec. 2.2.2：d_circ ≤ min(d, 各 end-cycle 距离) | 无 BB 数值；只有 Prop. 1 这个归约 |
| 2604.09797 色码部分（Sec. 5.2、App. E） | 用 Gurobi 检查 “Extra Qubits” 色码电路的 d_circ 与预期一致，d = 3, 5, 7, 9（Sec. 5.2 末段） | 色码、小距离的精确/MIP 计算，不是 BB，不是 12 |
| 2605.21898 v2（Wills 等） | App. C：“believed” 12；只有直接 Monte Carlo | 非证明 |
| 2603.05481 v2（Strikis 等） | App. H.2 末段：转述 12 | 转述上界，且 Prop. 4/5 讨论的是非交错 LR 电路，不含 morphing |
| 2606.12724（Chao） | 认证的是 rows I–IV 的**码距离**（pySATDist），ST 行只列 end-cycle 距离 12；明确不优化门序 | 无 d_circ 证明 |
| 2406 年至今其它引用 2407.16336 的论文 | 见下“引用筛查”：未发现含 morphing d_circ 下界的内容 | — |
| qldpc-challenge（GitHub） | issues/代码检索 “morphing” 0 命中；电路层（RFC 0001 rev 2, issue #505）明确只记录“witness-backed upper bound”，无下界；n = 144 的交错电路因规模上限（#2797、#2811）才刚能入榜，`codes/144-12-12.json` 的 d 也是 `upper_bound` 见证 | 无 |

**引用筛查（对 2407.16336）**：Semantic Scholar 引用列表共 52 条（2026-10-08 取得，另 4 条无 arXiv 号）。按标题全部过了一遍；对最可能涉及的 12 篇做了全文 “morph” 检索并读命中处：2606.12724、2608.19917、2603.05481、2601.09911、2609.39758、2610.06036、2509.00850、2604.01040、2607.04082、2606.09678、2605.04663、2512.01943。结果：多数只在参考文献/引言里引用；2601.09911（“morph” 命中其实多为 automorphism，未见 morphing 的 d_circ）；2608.19917 只读了命中处（7 处），未见 morphing d_circ 结果；2509.00850 Sec. V 只比较 LER，并写明路由方法“可能牺牲 circuit-level distance”，无证明；2512.01943（Wolanski）讲 dropouts 下的编译；2609.39758（时空容错理论）只在展望里把 morphing 列为可应用方向。其余 40 条标题明显无关（逻辑门、解码器、架构、色码/Floquet 等），未下载。S2 的引用表本身缺 2604.09797 与 2605.21898（索引滞后），所以又用 arXiv API 检索了 `all:"morphing circuit(s)"`（全部 4 条命中：2606.12724、2604.09797、2503.18657、2407.16336）和 `abs:morphing AND abs:"bivariate bicycle"`（2 条：2604.09797、2407.16336），并列了 Shaw、Terhal 的全部近作（Shaw 最近 arXiv 论文 2604.09797，Terhal 最近相关 2604.09797）。**这些检索都没有出现 morphing d_circ 的严格下界。**

**IBM 2605.21898 的引用方（S2，4 条）**：2610.04613、2609.06572、2605.11318、2606.03507，标题均与 morphing 无关。

**判断**：新。最接近的是（1）2407.16336 Table I（同一个电路的上界 12）、（2）2605.21898 App. C（相信 12 的 Monte Carlo 证据）、（3）2604.09797 Prop. 1（归约工具，使该问题变成单轮问题）。差别：这三篇都没有给出下界；本项目（E-017）的做法是 Prop. 1 + 单轮扩展码 + 精确 DFS。**该结果在 E-017 里尚未经 auditor 复核，也未覆盖 f_y、f_xy 与论文层序，不能在公开口径里写成“已证明”。**

## 问题 3：2604.09797 Prop. 1 的准确陈述、前提，以及该文对此电路 d_circ 的说法

（引用说明：按“每次回答至多一句短引文”的规则，除下面这一句外全部用转述，并给出位置；需要逐字原文请读 2604.09797 v2 Sec. 2.2.2 与 App. B。）

**陈述**（Sec. 2.2.2 “Computational Cost of Determining The Circuit-level Distance”，p.5；App. B 重述并证明，p.36–37）：对 “any two-round morphing circuit for a stabiliser code”，d_circ(T) = d_circ(1)，其中 T 是记忆实验中的测量轮数。

**前提（按我的阅读）**：
1. **电路类型**：两轮（J = 2）morphing 电路。Sec. 2.2.1 把“符合 Fig. 1(a) 结构的任何电路”都叫两轮 morphing 电路，不论是否由 morphing 原则设计。多于两轮的 morphing 电路不适用（Sec. 2.6.2 明说 “the computationally-efficient method ... in Prop. 1 no longer applies”）。ST 的 [[288,12,18]] 电路是两轮，满足。
2. **d_circ(T) 的定义**（Sec. 2.2.2，p.5）：理想地制备某个 end-cycle 码 C_j^end 的任意逻辑态，做 T 个测量轮，再**理想地**测量最后一个 end-cycle 码的稳定子；d_circ(T) 是造成不可检测逻辑错误的最少电路级故障数。脚注 1 解释了为什么必须从 end-cycle 码开始（从 mid-cycle 码开始时第一个收缩电路作用在 |00⟩ 上什么也不做）。**所以 Prop. 1 的是“理想初始化 + 理想末端读出”口径，不是评估器那种含噪初态/读出的口径。**
3. **证明依赖的对称性**（App. B，p.36–37，Fig. 24）：每个故障 E 可以被其“时间反演镜像” E′ 替换，E′ 触发相同的常规探测器 D^(2)、相同的可观测量（传播到最近的 mid-cycle 码后相同），把落在最后一轮的故障逐个折回前一轮，权重不增。因此**故障集合必须在时间反演下封闭**（复位错误 ↔ 测量错误，CNOT 后的两比特泛错误 ↔ 镜像位置的错误，空闲位置一一对应）。证明文字没有把这点列为独立假设，**也没有专门讨论空闲故障**（全文 “idle” 只在 normal circuit 的定义与噪声模型表里出现）。E-017 对 sd6 逐项核对过对称性（日志 §4，论证、未另行计算）。这是**对项目最关键的隐含前提**，建议 auditor 单独核对。
4. **只对记忆实验成立**：脚注 11 明说该时间反演对稳定性实验不成立（首末轮缺探测器）。
5. **Prop. 1 本身不给 d_circ 的值**：它只说 d_circ(T) 与 T 无关，即只需分析一轮。上界 d_circ ≤ min(d, d_j^end)（Sec. 2.2.2）是另一个独立的、平凡的结论。

**该文对 BB 电路的 d_circ 说了什么**：
- Sec. 3.3 正文（p.15）与 App. C.4（p.44）：搜索结果里的 d 只是 end-cycle 码距离，“the circuit-level distance ... may be lower than d”；App. C.4 明确说没有检查 bare-ancilla 和 morphing 电路的 d_circ，留待未来研究具体的码/电路。
- 引言说上一篇（2407.16336）对 BB 码 “found new so-called end-cycle codes” 的参数与另一 BB 码相同；没有 d_circ 数值。
- 全文没有出现 [[288,12,18]] 电路的 d_circ 数值或证明。

## 问题 4：抢发风险

| 方 | 证据 | 评估 |
|---|---|---|
| Shaw–Terhal（TU Delft/QuTech） | 最新一篇 2604.09797 v2（2026-04-20）；自己说 BB/2BGA 的 d_circ “leave it to future work”（App. C.4）；Sec. 5.2 末提到一个关于三角形权重 6 色码电路的新想法 “actively investigating”；GitHub `Mac-Shaw/morphing_qec_circuits` 最后一次提交 2025-08-29；Shaw 与 Terhal 2026-04 之后没有新 arXiv 论文（arXiv API 作者检索）。他们同时拥有 Prop. 1 与 Gurobi 的实践（色码 d ≤ 9） | **中低**。有能力、有工具、问题在他们的归约之内；但没有任何公开迹象表明在做，且近期焦点是色码/Floquet/泄漏。 |
| IBM | 2605.21898 v2 App. C 只说 “aim to narrow the confidence interval in future”（继续 Monte Carlo，p.77），没有提证明；2506.03094 把 morphing 列为未来方向；IBM 作者（Beverland）在 Strikis 里把 12 当事实转述；2605.21898 之后到 10-08 没有 IBM 新论文提到 morphing | **低到中**。方向是缩窄 LER 置信区间与重新设计辅助系统，不是距离证明；但 Beverland 同时在 Strikis 的 SEC 证明线与 IBM 的 morphing 线上，需注意。 |
| qldpc-challenge 榜单 | `morphing` / `end-cycle` / `Shaw` 在 issues（含 PR）与代码检索均无 morphing 条目（end-cycle 仅出现在无关的 PR 里）；电路层只接受 witness 型上界（RFC 0001 rev 2，#505），无下界，也没有 morphing 电路格式；2026-10-06 刚把规模上限提到 135,000 机制（#2811），n = 144 交错电路才能入榜；`codes/144-12-12.json` 无 circuit 字段 | **低**（对 morphing 的 12）。 |
| Chao（NVIDIA） | 2606.12724 复现了 ST 电路，但只认证码距离，不优化门序，没有 d_circ | 低。 |
| 未公开的工作 | 无从检查 | 未知 |

**总体**：低到中。没有找到任何一方正在做这件事的证据，但（i）Prop. 1 是公开的，把问题变成单轮小实例；（ii）三篇论文都把 12 当作“被相信的事实”，说明社区有动机把它变成定理；（iii）qldpc-challenge 的 AI agent 活动密度很高（以天计），一旦它们接入 morphing 电路格式，上界见证会很快出现（但它们的流程只给上界，无下界）。

## 新颖性判断
- **有没有人做过完全相同的事？** 没有。没有任何论文或公开榜单条目给出任何 morphing 电路的严格 d_circ 下界；对 [[288,12,18]] → [[144,12,12]] 尤其没有。
- **最接近的三篇**：2407.16336（同一电路，上界 12，BP-OSD）、2604.09797（Prop. 1 归约，明说未检查 BB 的 d_circ）、2605.21898 App. C（相信 12，Monte Carlo）。
- **“声称”与“复现”**：12 这一数字有三处声称（ST 上界、Strikis 转述、Wills 相信），**没有任何独立复现的下界**；E-017 的 DFS 属于本项目内部结果，尚无 auditor 复核。
- **措辞建议**：只能说“据我们所知，首个 morphing 电路的严格 d_circ 下界”，范围要限定为 ST 的 [[288,12,18]] 电路（具体同态、门序），**不能**说“gross 码的 idle 电路 d_circ = 12 已证明”，因为该电路作用在与 gross 不等价的 end-cycle 码上（见问题 1.3），且 IBM 的所指未确认。

## 对本项目的建议
1. 公开口径里必须区分三件事：(a) ST 电路（end-cycle 码 [[144,12,12]]，权重 9）与 IBM 的 gross 码（权重 6）不是同一个码；(b) Prop. 1 的理想边界口径与评估器的含噪边界口径不同，需要 E-015 B7 式的边界论证；(c) 当前验证的只是 f_x + 仓库层序一种变体。
2. **请 lead 决定是否联系作者确认 IBM 的所指**：对象是 2605.21898 的通讯/共同作者（Beverland 或 Wills）或 Shaw。问题只需一句：App. C 的电路是否即 2407.16336 Table I 的 [[288,12,18]] morphing 电路；若不是，多项式与同态是什么。联系作者属于对外发信，需 PI 同意。
3. 请 auditor 单独核对 Prop. 1 的隐含前提：sd6 故障集合在时间反演下封闭（尤其是空闲故障与各层 DEPOLARIZE 的位置）。2604.09797 App. B 没有把这点写成显式假设。
4. 补做 f_y、f_xy 与论文层序（swap23）变体，因为 IBM/Strikis 提到的“12”没说明是哪一个变体（ST 说 d̃_circ 上界对所有 f 与两个 end-cycle 码相同，见 2407.16336 Table I 题注，但那只是上界）。
5. 抢发窗口：问题在 ST 的归约之内，且 E-017 计算量很小；建议在 auditor 复核后尽快放出带时间戳的预印本或公开仓库，并明确引用 2407.16336、2604.09797、2605.21898 App. C、2603.05481 App. H.2。
6. 开新搜索前，定期复查：arXiv `all:"morphing circuit"` 的新条目、Shaw/Terhal 的新作、qldpc-challenge 是否出现 morphing 格式或 n = 144 的 morphing 条目。

## 检索记录
- **arXiv 全文 PDF（pdftotext 后定向检索，读命中上下文）**：2605.21898 v1/v2、2604.09797 v2、2407.16336 v3、2506.03094 v1、2606.12724 v1、2603.05481 v2、2608.19917、2601.09911、2609.39758、2610.06036、2509.00850、2604.01040、2607.04082、2606.09678、2605.04663、2512.01943；另对 2605.20346、2511.15177、2603.02157、2602.20546、2604.20013、2603.10970、2606.02418、2510.21600、2604.05126、2605.21746、2609.06572 只检索 “morphing”（0 命中）。2606.30592 下载失败，未读。
- **arXiv API（摘要/标题字段，非全文）**：`all:"morphing circuit(s)"`、`abs:morphing AND abs:"bivariate bicycle"`、`abs:morphing AND abs:"circuit-level distance"`（0 条）、`au:Terhal`、`au:Shaw_Mackenzie`、`au:Wills_Adam`、`au:Beverland_M`、`au:Yoder_Theodore`、`abs:"gross code" AND abs:circuit / idle / "circuit distance"`。注意：arXiv API 不支持全文检索，作者 `au:Beverland_M` 返回的是无关作者，因此对 Beverland 的新作检索不完整。arXiv 版本页：2605.21898 仅 v1、v2；2604.09797 仅 v1、v2；2407.16336 v1–v3。
- **Semantic Scholar 引用表**：2407.16336（52 条）、2605.21898（4 条）、2604.09797（12 条）、2506.03094（161 条，筛 2025-10 之后的标题与作者）。索引滞后，列表不完整。
- **GitHub**：`unitaryfoundation/qldpc-challenge` 的 issues/PR 检索词 morphing、Shaw、2407.16336、2604.09797、2605.21898（均 0）、gross circuit tier、circuit tier 144、d_circ exact lower bound、certified lower bound d_circ、idle circuit、circuit distance proof、end-cycle、mid-cycle、144-12-12、288-12-18；代码检索 morphing（0）；读了 #505 RFC、#2797、#2863、#1204 的相关段落与 `codes/144-12-12.json`。`Mac-Shaw/morphing_qec_circuits` 提交历史（最后一次提交 2025-08-29）。
- **WebSearch**：3 组（Shaw Terhal morphing gross 12 proof；IBM morphing idling Wills；morphing [[144,12,12]] end-cycle exact），结果均回到上述论文，没有新来源。
- **未覆盖**：arXiv/期刊全文检索；2407.16336 引用中约 40 条仅按标题排除；未发表的工作；会议报告或幻灯片；S2 索引滞后的最新论文；向作者求证。
- 关于 E-017 的引用均出自项目内部日志 `research/journal/2026-10-08-E-017-gross-morphing-scoping.md`，**不是文献，未经 auditor 复核**。
