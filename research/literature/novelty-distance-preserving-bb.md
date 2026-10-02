# 为非 gross 的 BB 码恢复电路距离（d_circ = d 或更高 d_circ）：新颖性检索
检索日期：2026-10-02；检索词：circuit distance [[90,8,10]] [[108,8,10]] bivariate bicycle schedule；BB code circuit-level distance equals code distance depth-8；[[120,8,12]] twisted torus circuit distance；gross code distance 12 interleaved Strikis follow-up；BB flag qubits circuit distance；以及对已有笔记中各论文的定向全文检索。

## 读取方式与局限（先看）
- **读了 PDF 全文文本**（curl 下载 arxiv.org/pdf/<id>，pdftotext 抽取，在抽取文本里按码参数、d_circ、circuit distance、gross、BB 等关键词定向检索，再通读命中处的上下文；没有逐页通读）：2603.05481 v2（14 Sep 2026）、2308.07915 v2、2506.03094 v1、2407.16336 v3、**2604.09797 v2（20 Apr 2026，这次拿到了全文文本；此前笔记里"未读全文"已作废）**、2601.12509、2601.17580、2609.12020、2603.21499、2606.30592、2601.09911 v1、2408.10001 v7、2603.22532、2603.00228、2606.17268、2605.04663、2609.39395、2609.39121、2503.03827。
- 对 AlphaSyndrome、PropHunt、FastSched、ASC 只做了关键词检索（bivariate / BB / gross / [[72 / [[90 / [[108 / [[144 / J72 / circuit distance / effective distance），没有通读。"没有给出这些码的 d_circ"的结论来自这些关键词检索和相关章节的阅读，不是逐页核对。
- 检索靠搜索引擎，不是 arXiv 全库检索，可能漏文。2026 年论文的编号和日期按 PDF 首页所示，未独立复核。
- 所有 d_circ 数字几乎都是 BP-OSD（或 MIP 未收敛时）得到的**上界**（"≤"），不是证明。下面表中"最好已知 d_circ"一律指"文献里报告的最小的上界所对应的电路"，即该电路的 d_circ 不会比这个数大。
- 版本说明：2603.05481 我读的是 v2；没有和 v1 逐字比较。

## 结论（3-5 行）
- **对 [[90,8,10]]、[[108,8,10]]、[[120,8,12]]、coprime [[126,12,10]] 这四个码，文献里能找到的所有 d_circ 都来自 IBM 式单辅助比特深度-7 电路（或其变体），数字是 ≤8、≤8、≤10、≤9，与 E-004 的数字一致；没有任何一篇给出过更高的 d_circ，也没有人对这些码搜索过别的调度。** 唯一"恢复到 d"的结果是换噪声模型（偏置噪声，2606.30592 Table II：[[90,8,10]] 恢复到 10），不是换电路。
- **Strikis 等 2603.05481 在方法上覆盖这些码（BB 码是其 LP 码框架的特例，App. A），但它所有关于 d_circ 的数字（Prop. 4–6、Fig. 12）只针对 gross 码；对 [[90]]、[[108]]、[[120]]、[[126]]、[[288]] 的非交错上界、构造或 d_circ 数字：未找到。** Fig. 2 / Table II 的码是 Tanner200、HGP625、Haah128、FB126，不含 BB 码。
- **没有找到任何关于这些码"单辅助比特、深度 7–8 下不可能 d_circ = d"的定理或下界。** 已有的不可能性结果（Strikis Prop. 4）只对 gross 码、非交错电路成立，是靠对 gross 码的扩展码做数值搜索得到的，不能外推。
- 判断：**"为非 gross 的 BB 码在同深度、同辅助比特数下找更高 d_circ 的电路"目前是空白（部分邻近），证据强度：中等偏低**（负面证据来自关键词检索与搜索引擎，且 Strikis 的框架让这件事对别人也很便宜，抢发风险高）。
- 代价侧：对这些码，没有任何已知的 d_circ = d 的电路，所以"代价"没有文献数字。邻近的参照：[[288,12,18]] 在 IBM 原电路下上界就是 18（不付任何代价，但只是上界）；gross 码的 d_circ=12 只有换码的 morphing 方案（288 总比特、连接度 5、不是 gross 码）。

## 关键论文
| arXiv | 作者 · 年份 | 做了什么 | 与本项目关系 | 关键数字（附出处） |
|---|---|---|---|---|
| 2308.07915 v2 | Bravyi 等（IBM）· 2023（v2 21 Feb 2024） | BB 码与深度-7 单辅助电路（Table 5，8 个 round 含 init/meas） | 所有 BB 码 d_circ 的原始出处 | Table 1：[[72,12,6]] ≤6；[[90,8,10]] ≤8；[[108,8,10]] ≤8；[[144,12,12]] ≤10；[[288,12,18]] ≤18。题注："All codes have weight-6 checks ... depth-7 syndrome measurement circuit"。正文（Table 1 下方）：猜想该电路对 [[72,12,6]] 是 distance-preserving；[[288]] 的 ≤18 "unlikely to be tight"。Sec. 5 末：935 个深度-7 变体 + 原电路共 936 个，"In the special case of the [[144,12,12]] code ... all 936 variants ... d_circ ≤ 10"。**这个 936 变体检验只对 [[144]] 做了，对 [[90]]、[[108]] 没有。** Sec. 10 Open question 4：建议用不同 cycle 用不同电路 |
| 2506.03094 v1 | Yoder 等 · 2025-06 | Tour de gross | gross / two-gross d_circ | Table 4（Sec. 2.6）：gross d_circ ≤10（idle/aut.、in-module、inter-module 三列都是 ≤10）；two-gross ≤18 / ≤18 / ≤17。题注："Cases that are known exactly are calculated using integer programming"，哪些格子是精确值，我没能从文字里确定。Outlook 条目"Achieving the code distance"：gross 的 d_circ ≤10；two-gross "not known to be any less than its code distance of 18, it would not be surprising if this was actually the case"；"it would be useful to find syndrome measurement schedules with larger circuit distance" |
| 2603.05481 v2 | Strikis, Browne, Beverland · 2026（v2 14 Sep 2026） | left-right 电路（LRC）、残余错误集、扩展码距离 d_ext；gross 码的非交错上界与 d_circ=11 猜想电路 | 方法覆盖 BB 码，数字只有 gross | App. A 末：BB 码是 LP 码的特例（protograph 1×1，群代数为两个循环群的积），"the same LRC depth arguments hold for BB codes"。Prop. 3（Sec. IV）：**对任意** SEC（含交错）d_circ ≥ d_ext(E)。Prop. 4（Sec. IV.3）：gross 码非交错 d_circ ≤11。Prop. 5/6、Fig. 11/12（App. H）：均匀平铺 ≤10；三色平铺只剩 3 种；深度 8 的 Fig. 12 电路，猜想 11。Sec. IV.3 末："our proof does not apply to interleaved circuits. It therefore remains an open question whether any interleaved circuit can achieve circuit distance 12." |
| 2407.16336 v3 | Shaw, Terhal · PRL 134, 090602 (2025)（v3 26 Mar 2025） | BB 码的 morphing 电路（无辅助比特，连接度 5） | 唯一的"换电路范式"结果 | Table I：[[72,12,6]] 标准 ≤6，end-cycle [[36,12,3]] ≤3；[[108,8,10]] 标准 ≤8，end-cycle [[54,8,8]] ≤7（只有 f_y 满足 Criterion 1）；[[144,12,12]] 标准 ≤10，end-cycle [[72,12,6]] ≤6；[[288,12,18]] 标准 ≤18，end-cycle [[144,12,12]] ≤12。**[[90,8,10]] 不在 Table I**。题注："n refers to the number of qubits in the BB code ... includes both data and ancilla qubits when ran as a morphing circuit"。App. A：d_circ 上界用 BP-OSD，两轮 QEC 的 Z 基 memory 实验。App. G / Table IX：找到更好的 end-cycle 变体：[[36,12,4]] ≤4、[[72,12,7]] ≤7 |
| 2604.09797 v2 | Shaw, Terhal · 2026-04（v2 20 Apr 2026） | morphing 电路的统一框架；Abelian 2BGA 码搜索；交替电路 | 与"跨 cycle 交替"相关 | Sec. 2.5 Prop. 3（eq. 4）：d_circ^alt(T) = d_circ^alt(1) = d_circ^non-alt(1) ≥ d_circ^non-alt(T)；示例只有旋转表面码。Sec. 3.3 / Fig. 9：搜索输出 end-cycle 码参数，只给界 d_circ ≤ min(d, d_end)（bare-ancilla 为 ≤ d）。Table 3/4 列出 [[72,12,6]]、[[108,8,10]]、[[144,12,12]]、[[288,12,18]] 的 2BGA 表示，**没有 d_circ 数字**；全文检索 gross / [[144 / [[90 / [[108，除这两张表外无其他命中 |
| 2601.09911 v1 | Kim, Gicev, Sevior, Usman · 2026-01-14 | 用时间动态电路实现 shift 自同构 | **[[120,8,12]] 的 d_circ 出处** | Table I：[[72,12,6]] ≤6；**[[120,8,12]]（α=4，ℓ,m=10,6，A=1+x+x⁻²y，B=1+y+xy²）≤10**；[[144,12,12]] ≤10；**[[170,16,10]]（α=−7，ℓ,m=17,5）≤10（= d）**。正文（Table I 后）："the degradation of the circuit distance from 12 to 10 was also observed for the [[120,8,12]] code, similar to the gross code"。电路为深度-7 的 CNOT 调度（Sec. II，引 [26,40]）；上界用 BP-OSD。Table II 为其 syndrome cycle |
| 2503.03827 | Liang, Liu, Song, Chen · 2025（PRX Quantum 6, 020357） | 扭曲环面上的广义 toric 码 | [[120,8,12]] 的码参数出处 | 摘要与正文：构造 [[120,8,12]]；我在该文里检索 circuit distance / d_circ，**未找到 d_circ 数字** |
| 2408.10001 v7 | Wang, Mueller · 2024（v7 10 Mar 2026） | coprime BB 码 | **[[126,12,10]] 的 d_circ 出处** | Sec. 5.2（Fig. 7 附近的正文）："simulations indicate that the [[144,12,12]] has a circuit-level distance of d_circ ≤ 10, while the [[126,12,10]] has d_circ ≤ 9"。所用电路：正文只说采用 IBM 文献 [8] 的做法，具体调度我没找到文字说明；该 [[126,12,10]] 是 coprime BB 版本（多项式与 IBM 的 GB 版本不同，见 Table 2） |
| 2606.30592 | Bi, Chang, Puri · 2026-06-29 | 偏置噪声下标准电路的 d_circ 上界 | 同码、换噪声模型恢复到 d | Table II：去极化噪声下 [[72,12,6]] 6、[[90,8,10]] 8、[[144,12,12]] 10；三种偏置模型在 η→∞ 下分别为 6、10、12。上界用 BP 随机搜索（Sec. III，引 IBM Sec. 6 的方法） |
| 2603.00228 | Jacoby, Retzker, Pastawski · 2026-02 | Stairway 码；也把 gross 码编译成两两测量 | 多辅助比特的邻近例子 | Sec. VII（正文 Fig. 10 附近）："long" 编译保持 d_circ（≤10），"short" 编译降到 ≤8，两者"require three ancillas per stabilizer, effectively doubling the total number of qubits"。**不是 d_circ=d 的电路** |
| 2603.21499 | Zhang 等（ASC）· 2026-03 | SMT/CP-SAT 求深度最优电路 | 深度下界 | Table II：[[72,12,6]]、[[90,8,10]]、[[108,8,10]]、[[144,12,12]]、[[288,12,18]] 的深度均为 7（ASAP 15–16，coloration 12）；Sec. V.A："first concrete evidence supporting the conjecture that no depth-6 circuits exist for these BB codes"。全文检索 distance：**只出现码距离，没有 d_circ**；其"automated circuit filter"（Sec. IV.C）按逻辑错误率从多次求解结果中挑，不看 d_circ |
| 2601.12509 | Liu 等（AlphaSyndrome）· 2026-01 | MCTS 搜调度 | 方法近邻 | BB 码只测 [[72,12,6]]：BP-OSD 降 44%，Unionfind 降 10%（Sec. 5.4、Fig. 13）；没有 d_circ 数字；检索 gross / [[90 / [[108 / [[144 无命中（除参考文献） |
| 2601.17580 | Viszlai 等（PropHunt）· 2026-01 | MaxSAT 消除歧义子图 | 方法近邻 | Table 1 的码无 BB 码；全文检索 bivariate 仅 1 处命中，在相关工作的一句话里；报告的是 effective distance，不含 BB 码 |
| 2609.12020 | Ye, Pabla, Palsberg · FastSched · 2026-09 | PPO 强化学习调度 | 方法近邻 | 全文只有一处提到 BB 码（Sec. 1 State of the Art，转述 AlphaSyndrome 对 [[72,12,6]] 的结果）；Table 1 无 BB 码；无 d_circ |
| 2603.22532 | Webster, Jacob, Higgott · 2026-03 | 距离计算算法 | 评估器工具 | Sec. 5.5.3 / Table 28–29：BB 码的 syndrome 提取电路"proved to be the most challenging circuits for distance-finding"；用的是 tesseract 仓库的测试电路，**没有按码给出 d_circ 数字** |

## 1. 各码已知的最好 d_circ

表中"电路"指得到该 d_circ 上界的电路。**除特别说明，辅助比特数 = 每个检查一个辅助比特，总比特 2n；深度 = 7 层 CNOT（含 init/meas 共 8 个 round）。** 没有任何一行是交错/流水/flag 的改进电路，除非明说。

| 码 | 最好已知 d_circ（上界） | 电路 | 出处 | 备注 |
|---|---|---|---|---|
| [[72,12,6]] | ≤6（= d） | IBM 深度-7，单辅助，2n=144 | 2308.07915 Table 1；正文猜想 distance-preserving | 无缺口。Shaw–Terhal morphing 的 end-cycle 码是别的码（[[36,12,3]] ≤3，2407.16336 Table I），不是 d=6 的改进 |
| [[90,8,10]] | ≤8（d=10，缺口 2） | IBM 深度-7，单辅助，2n=180 | 2308.07915 Table 1；2606.30592 Table II（去极化 8） | 偏置噪声 η→∞ 下 ≤10（2606.30592 Table II，改了噪声模型，电路不变）。不在 2407.16336 Table I。没有找到任何对 [[90]] 的调度搜索 |
| [[108,8,10]] | ≤8（缺口 2） | IBM 深度-7，单辅助，2n=216 | 2308.07915 Table 1；2407.16336 Table I | morphing 版本给的是另一个码 [[54,8,8]]，d_circ ≤7（2407.16336 Table I）。没有 [[108]] 的调度搜索 |
| [[120,8,12]] | ≤10（d=12，缺口 2） | 深度-7 CNOT 调度，单辅助 | 2601.09911 Table I 及其正文 | 码参数出处 2503.03827。本笔记**未核实**该码的多项式与 E-004 用的 BB120 是否为同一个码（2601.09911 给的是 A=1+x+x⁻²y，B=1+y+xy²，ℓ,m=10,6）|
| coprime [[126,12,10]] | ≤9（d=10，缺口 1） | IBM 式电路（正文称沿用 [8] 的做法，具体调度未找到文字说明） | 2408.10001 Sec. 5.2 | 与 [[144,12,12]] ≤10 同段给出 |
| gross [[144,12,12]]（对照） | IBM ≤10；Strikis 猜想 11（非交错，深度 8，单辅助）；非交错上界 ≤11 | 见 Fig. 12 | 2308.07915 Table 1；2603.05481 Prop. 4、Fig. 12 | 11 是猜想（一万轮外循环没有找到 <11 的逻辑算符，App. H），没有独立复现 |
| two-gross [[288,12,18]] | ≤18（= d，但只是上界） | IBM 深度-7，单辅助，2n=576 | 2308.07915 Table 1；2506.03094 Table 4（idle ≤18、in-module ≤18、inter-module ≤17）；2407.16336 Table I（标准电路 ≤18） | IBM 称"unlikely to be tight"；Tour de gross Outlook 称不知道是否小于 18。**能否说 d_circ=18 取决于 BP-OSD 的上界是否紧，文献没有证明** |
| [[170,16,10]]（不在你列的清单，但是 BB/2BGA 类、权重 6） | ≤10（= d，上界） | 深度-7 单辅助 | 2601.09911 Table I | 说明单辅助深度-7 电路在某些 BB 类码上上界就等于 d，没有一般性障碍 |

要点：
- E-004 的四个数字（BB90 ≤8、BB108 ≤8、BB120 ≤10、CP126 ≤9）都能在文献里找到对应：IBM Table 1（90、108）、2601.09911 Table I（120）、2408.10001 Sec. 5.2（126）。**E-004 的数字与文献一致。**
- **只有 [[72,12,6]] 和 [[288,12,18]]（以及 [[170,16,10]]）的上界等于 d，且都是不改电路的 IBM 原电路。缺口 ≥1 的是 90、108、120、126、144。**
- 所有数字都是上界，没有任何一个"d_circ 精确等于某值"的文献结果可以引用给这些码。

## 2. Strikis 等 2603.05481 对这些码的覆盖情况

读 PDF 全文，结论如下。
- **框架覆盖，数字不覆盖。**
  - App. A 末："Bivariate bicycle (BB) codes are special cases of LP codes ... Therefore, the same LRC depth arguments hold for BB codes."（这是**深度**论证。）Sec. III.B 与 App. A 对 LP/BB 码给出 LRC 的深度公式。
  - 但 d_circ 的结论（Prop. 4、5、6，Fig. 11、12）全部针对 gross 码：证明里用的是"某个固定 X 检查的 90 种单检查 CNOT 顺序"，对每种顺序在 **gross 码的**扩展码里搜一个逻辑算符（App. D）。90 种顺序这一步对任何权重-6 检查都成立，但每一种的 d_ext 要对每个码单独算，原文没有对别的码算。
- **非交错上界：对 [[90]]、[[108]]、[[120]]、[[126]]、[[72]]、[[288]] 均未找到。** 全文检索 [[90、[[108、[[120、[[72、[[288、two-gross、coprime：无命中（除参考文献）。gross 是文中唯一的 BB 码。
- **Fig. 2 / Table II：** 码是 HGP625 [[625,25,8]]、Tanner200 [[200,10,10]]、Haah128 [[128,14,8]]、FB126 [[126,8,9]]，不含任何 BB 码，也没有这些码的 d_circ 数字。App. F / Fig. 8 的对照码是 CC61 与 RQT108，也不含 BB 码。
- **对本方向最有用的两个一般性结论（都不限于 gross）：**
  1. Prop. 3（Sec. IV）：对任意 SEC（含交错）d_circ ≥ d_ext(E)。Corollary 1：非交错时 d′_circ = d_ext(E)。所以**非交错电路的 d_circ 可以通过对扩展码求最小权逻辑算符精确计算，而不必展开多轮完整电路。**
  2. Sec. IV 与 Sec. VII：从非交错电路出发、保持每个检查内部顺序不变、仅调时间做成交错电路，d_circ 不会下降（"may further improve it"）。
- 注意 E-004 的 IBM 项顺序（"X/Z 层交错"）按 Strikis 的定义很可能本身就是交错电路（见 `novelty-interleaved-circuits.md` 第 1.2 节的推断，原文没写，需核对）。所以对 90/108 来说，"非交错上界"并不直接限制 IBM 式交错电路。

## 3. 其他论文里有没有给出这些码的 d_circ 改进

| 论文 | 有没有这些码的 d_circ 改进 | 依据 |
|---|---|---|
| AlphaSyndrome 2601.12509 | **没有**。BB 码只有 [[72,12,6]]，报逻辑错误率（降 44% / 10%），不报 d_circ | Sec. 5.4、Fig. 13 |
| PropHunt 2601.17580 | **没有**。Table 1 无 BB 码 | Table 1；全文检索 |
| FastSched 2609.12020 | **没有**。Table 1 无 BB 码 | Table 1；全文检索 |
| ASC 2603.21499 | **没有 d_circ**。深度 7 对 72/90/108/144/288 全部最优（Table II） | Table II、Sec. V.A |
| Tour de gross 2506.03094 | **没有改进**。gross ≤10、two-gross ≤18，并在 Outlook 把"找到更大 d_circ 的调度"列为待做 | Table 4、Outlook |
| Shaw–Terhal 2407.16336 | **换码不换调度**。[[288]] 的 end-cycle 码 [[144,12,12]] d_circ≤12；[[108]] 的 end-cycle 码 [[54,8,8]] d_circ ≤7；[[72]] 的 [[36,12,3]] ≤3。对 [[90]] 没有结果 | Table I；Table IX（改进的 [[36,12,4]] ≤4、[[72,12,7]] ≤7） |
| Shaw–Terhal 2604.09797 | **没有这些码的 d_circ 数字**。给出一般结论：交替（时间反演）电路的 d_circ(T) = d_circ(1) ≥ 非交替的 d_circ(T)；只用旋转表面码举例。对 BB 码是否有收益：**未找到**。BB 码在 Table 3/4 出现，只列码参数 | Sec. 2.5 Prop. 3；Table 3、4；Sec. 3.3 |
| 其他（2606.30592、2603.00228、2601.09911、2408.10001） | 只是报告原电路的上界或换噪声（见上表），没有更好的电路 | 见上 |

补充一条关于交替电路的推理（我的判断，原文没写）：2604.09797 Prop. 3 的增益只在"最小权失败跨多个 QEC 轮次"时出现（表面码的例子正是如此）。IBM 的 d_circ 上界（2308.07915 Sec. 6、2407.16336 App. A）是用两轮 memory 实验求的。对 [[90]]、[[108]] 的最小权失败是否跨轮，我没有找到数据，所以交替电路是否有用**未知**。

## 4. 有没有理论结果说明 [[90,8,10]] 或 [[108,8,10]] 在单辅助、深度 7–8 下不可能 d_circ = 10

**未找到。** 相关的、容易被误读的结果：
- Strikis Prop. 4：只对 **gross 码、非交错**成立（d_circ ≤11）。对 [[90]]、[[108]] 没有类似命题。
- IBM 2308.07915 Sec. 5 末：936 个深度-7 变体全部 ≤10，**只对 [[144]]**。
- ASC 2603.21499：只说最优深度是 7（不存在深度 6），与 d_circ 无关。深度 7–8 的单辅助电路在 BB 码上可行，不构成对 d_circ 的限制。
- Strikis Sec. I 声称 Shor/flag 类方法"often incur additional circuit depth and/or qubits"：定性说法，没有定理。
- 反方向的旁证：[[170,16,10]]（2601.09911 Table I）与 [[288,12,18]]（2308.07915 Table 1）在深度-7 单辅助电路下上界就等于 d。所以"单辅助深度-7 对 BB 码不可能 d_circ=d"不成立（至少没有证据）。但这两个上界都只是 BP-OSD 上界，不是证明。
- 不能排除的风险：对 [[90]]、[[108]]，所有非交错电路的上界可能就低于 10（类似 gross 的 ≤11 < 12）。这件事可以用 Strikis 的方法（Prop. 3/Corollary 1 + 90 种单检查顺序）在不搜电路的情况下直接算，文献里没有人算过。

## 5. 新颖性判断

**这个方向（为非 gross 的 BB 码恢复电路距离、同深度同辅助比特数）：空白，邻近部分做过。证据强度：中等偏低。**

- 有没有人做过完全相同的事？**未找到。** 没有任何论文对 [[90]]、[[108]]、[[120]]、[[126]] 搜索过调度，也没有任何一篇报告过比 IBM 原电路更高的 d_circ。
- 最接近的几篇及差别：
  1. 2603.05481（Strikis）：方法最近，框架覆盖 BB 码，但只做了 gross 码；没有这些码的任何数字。
  2. 2407.16336 / 2604.09797（Shaw–Terhal）：换电路范式，结果是另一些码（[[54,8,8]] ≤7 等），没有给出 d=10 的码的更好电路。
  3. 2606.30592：偏置噪声下 [[90]] 恢复到 10，改的是噪声模型，不是电路。
  4. 2601.09911、2408.10001：报告了 [[120]]、[[126]] 的上界，没有搜索调度。
  5. AlphaSyndrome、PropHunt、FastSched、ASC：方法近邻，但对象不含这些码，指标不是 d_circ。
- 证据强度为什么只有"中等偏低"：
  - "未找到"是搜索引擎加定向关键词检索的结果，不是 arXiv 全库检索。
  - Strikis 的 Prop. 3 / Corollary 1 把非交错电路的 d_circ 化成了扩展码距离，这让别人对其他 BB 码重复其 gross 分析的成本很低。抢发风险高，尤其 Strikis 作者与 IBM 同属一个圈子（作者之一在 IBM Quantum），且 Tour de gross 的 Outlook 明确点名这件事。
  - E-004 的 IBM 项顺序在 [[90]]、[[108]] 上得到 ≤8，与 IBM Table 1 一致，说明"缺口"本身是事实，不是评估器的人为结果。
- **如果已经有人做到 d_circ = d，代价是什么？** 对这些码：没有，无数字可引。邻近的参照：
  - gross 码 d_circ=12：只有换码的 morphing 方案（2407.16336 Table I：[[288,12,18]] 的 end-cycle 码 [[144,12,12]] ≤12），总比特 288、连接度 5，不是 gross 码。
  - 多辅助比特：2603.00228 把 gross 码编译为两两测量，每个检查 3 个辅助比特、总比特翻倍，但 d_circ 只保持 ≤10，并没有恢复到 12。flag 电路用于 BB 码的数字：未找到。
  - 偏置噪声：不改电路，但要求辅助比特噪声强偏置（2606.30592）。

## 对本项目的建议
1. **在把 H-003 主线改成"为 BB 码找保距离电路"之前，先做一件文献没做过的便宜事：用 Strikis 的 Prop. 3 / Corollary 1，对 [[90]]、[[108]]、[[120]]、[[126]] 各算一次"非交错电路 d_circ 的上界"**（90 种单检查顺序，对每种在扩展码里搜一个小权重逻辑算符）。这是 E-004 之外最便宜、信息量最大的一步：若某码的非交错上界已 <d，则该码的目标应改为"交错电路或 d_circ 更高的电路"，并且这个结果本身就是新的。实现要用的是项目自己的评估器公开入口，不是改评估器。
2. 目标的写法：要注明"d_circ 是 BP-OSD/MILP 上界"，并在 hypotheses.md 里区分三档：(a) 非交错上界已证（Strikis 方法）；(b) 交错电路无已知上界；(c) 单辅助深度-7/8 的存在性（[[170,16,10]]、[[288,12,18]] 的上界等于 d，作为"可能性"旁证，不是证明）。
3. 价值提示：E-004 在 p=4e-3 下发现调度对 B 的影响 ≤1.4 倍，而 d_circ 的指数收益只在低 p 显现；所以这条主线的评估必须在低 p（外推到 1e-3 或更低）进行，成本很高。这一点与文献无关，是 E-004 自己的结论，列在这里提醒。
4. 引用时的措辞：所有 d_circ 都写"≤"和"BP-OSD 上界"；Strikis 的 11 是猜想；[[120,8,12]] 的 ≤10 来自 2601.09911 Table I，其多项式是否与 E-004 的 BB120 相同**未核实**；2408.10001 的 [[126,12,10]] 所用电路的具体调度**未找到文字说明**。
5. 动手前建议补读（我没读全）：Strikis App. D（扩展码最小权逻辑算符的搜索方法）与 Sec. VII；2506.03094 App. A.8（哪些 d_circ 是 IP 精确值）；2408.10001 的电路说明；2503.03827 的多项式与 E-004 BB120 的对照。
