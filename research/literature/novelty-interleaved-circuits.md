# 交错 / 多辅助 / flag / 跨 cycle 交替电路能否让 gross code 达到 d_circ=12：新颖性检索
检索日期：2026-10-02；检索词（WebSearch + arXiv html/pdf 读取）：gross code circuit distance 12 interleaved flag；bivariate bicycle syndrome extraction circuit distance equal to code distance extra ancilla；joint search BB code polynomials and schedule；alternating time-reversed syndrome extraction BB；Strikis 2603.05481 follow-up；hook errors BB flag qubits；IBM gross code improved schedule 2026 等。
读取方式与局限（请先看）：
- 2603.05481 v2：我读了 v2 PDF 的全文文本（WebFetch 把 PDF 存到本地后用 pdftotext 抽取，双栏版面下行号不可靠，所以下面引用以"节/命题/附录"为准）。HTML 摘要工具的转述与 PDF 原文有出入时，以 PDF 原文为准。
- 2407.16336（Shaw–Terhal PRL）、2506.03094（Tour de gross）、2603.21499（ASC）、2601.12509（AlphaSyndrome）、2601.17580（PropHunt）、2609.12020（FastSched）、2607.25865（OmniQEC）：均取到 PDF 全文文本，但我只对相关关键词（gross/BB/interleav/flag/circuit distance/引用关系）做了定向阅读，没有逐页通读。
- 2604.09797（Shaw–Terhal 2026）：PDF 超过 10MB 抓不下来，只能通过 arXiv HTML 的工具摘要读到，**未读到全文**，表格（App. C.4）内容未读到。
- 2606.30592、2609.39121、2609.06572、2508.09082、2606.02418、2604.01040、2609.11723、2607.28795：只读到 HTML 经工具转述的片段，未通读，结论只在已标注范围内可信。
- 检索靠搜索引擎，不是 arXiv 全库检索，可能漏文。2026 年论文的编号、日期、数字未经我独立复核。
- 对 2603.05481 的 v1 与 v2 我没有做逐字差异比较；abs 页注明 v2（2026-09-14）"corrected figures in Appendix H and expanded the introduction"（abs 页，经工具转述）。下面所有内容均来自 v2。

## 结论（3-5 行）
- **"交错电路让 gross code 达到 d_circ=12"：未找到任何人做过；原作者在 v2 里明确写成开放问题**（2603.05481 v2 Sec. IV.3 末段，原文："our proof does not apply to interleaved circuits. It therefore remains an open question whether any interleaved circuit can achieve circuit distance 12."）。他们没有给出交错电路的构造，也没有给出交错电路的下界或上界。
- 多辅助比特 / flag / Shor 型电路用于 BB 码或 gross code：**未找到**。2603.05481 Sec. I 只泛泛说这类技术"often incur additional circuit depth and/or qubits"，没有 gross code 数据；PropHunt（2601.17580）在 Related Work 明说自己不加 flag、flag 留作 future work。
- 邻近但不等同的结果有三条：（a）Shaw–Terhal（2407.16336 Table I）一个**不同的** [[144,12,12]] 码（[[288,12,18]] BB 码的 morphing end-cycle 码）d_circ≤12，总比特数与 gross code 相同；（b）Bi–Chang–Puri（2606.30592）在偏置噪声下 IBM 原电路的 d_circ 上界恢复到码距离，但那是换了噪声模型；（c）Shaw–Terhal 2026（2604.09797）证明"交替（时间反演）电路的 d_circ 不低于非交替电路"，但据我读到的片段只在表面码/环面码上展示，BB 码未见。
- "gross code 上 Strikis 的 d_circ=11 电路 vs IBM 电路 vs AlphaSyndrome/PropHunt 风格电路的逻辑错误率"：**没有任何一篇做过**（Strikis 自己没有对 gross code 做电路噪声模拟；他们对 AlphaSyndrome/PropHunt 的比较只用了非 BB 码）。
- "码 + 调度联合搜索"（BB/2BGA 多项式与标准单辅助比特调度一起搜，以电路级性能为目标）：**未找到**。最近的是 2604.09797（morphing 电路范式下联合优化 Abelian 2BGA 码与电路）和 OmniQEC（LLM 搜码，调度为固定边着色）。

## 关键论文
| arXiv | 作者 · 年份 | 做了什么 | 与本项目关系 | 关键数字（附出处） |
|---|---|---|---|---|
| 2603.05481 v2 | Strikis, Browne, Beverland · v1 2026-03-05，v2 2026-09-14（abs 页） | left-right 电路（LRC）框架；剩余错误（residual error）距离与扩展码距离 d_ext；对 gross code 的非交错电路上界；交错电路只给了"不降低"的单向定理 | **直接相关**：交错电路是其明确列出的开放问题 | 见下面第 1 部分各条 |
| 2308.07915 v2 | Bravyi et al. · 2023 | IBM 原始 BB 码与深度-7 调度 | 基线；其 Table 5 调度本身是"交错"的（见第 1 部分的推断） | d_circ≤10（Table 1）；936 个深度-7 变体都≤10（Sec. 5，见 `gross-code-baseline.md`）；Open question 4：不同 cycle 用不同 SM 电路（Sec. 10，见 `novelty-schedule-search.md`） |
| 2506.03094 | Yoder et al.（IBM）· 2025-06-03 | Tour de gross | IBM 后续论文，仍用 d_circ≤10 | Table 4：gross code d_circ≤10（idle/aut.、in-module、inter-module 三列均≤10），two-gross ≤18/≤18/≤17；Outlook 条目"Achieving the code distance"："it would be useful to find syndrome measurement schedules with larger circuit distance ... while simultaneously achieving logical error rates that are no worse"（Sec. Outlook，PDF 文本） |
| 2407.16336 v3 | Shaw, Terhal · PRL 134, 090602 (2025) | BB 码的 morphing 电路，连接度 6→5 | 最近的"d_circ=12 且总比特数同 gross code"，但码不同 | Table I：[[288,12,18]] 标准电路 d_circ≤18；其 morphing end-cycle 码为 [[144,12,12]]，d_circ≤12；标准 [[144,12,12]] d_circ≤10；表注：n 指 BB 码 n，"includes both data and ancilla qubits when ran as a morphing circuit"（所以总比特 288）。d_circ 为 BP-OSD 上界：p=1e-4、product_sum、osd_cs、OSD order 100、BP 100 次迭代（Appendix，PDF 文本）。正文称 end-cycle 码是"a second 'gross' code that could be targeted"。Fig. 3：该码在 uniform 去极化电路噪声下与标准 [[144,12,12]] "perform similarly"（原文措辞，具体数值未读到） |
| 2604.09797 | Shaw, Terhal · 2026-04-10（修订 04-20，abs 页） | 把 morphing 电路用于联合优化码与电路（连接度、门类型、比特数）；证明交替电路是两轮 morphing 电路 | 与"联合搜索"和"跨 cycle 交替"都相关 | **只读到 HTML 工具摘要，未读全文。** Sec. 2.5 Prop. 3（摘要转述）：d_circ^alt(T)=d_circ^alt(1)=d_circ^non-alt(1)≥d_circ^non-alt(T)；示例只给了旋转表面码 d_circ^non-alt(T)=max(d−T,⌈d/2⌉)、交替版 d−1。Sec. 3.3："We numerically search through morphing circuits for Abelian 2BGA codes and find circuits with code parameters that strictly improve upon the bare-ancilla circuits"。表格内容未读到；"gross"、"[[144"在我读到的片段中未出现 |
| 2606.30592 | Bi, Chang, Puri · 2026-06-29 | 偏置噪声（ancilla 上 ZZ 主导）下标准电路的有效故障距离 | 同样"d_circ 恢复到码距离"，但靠改噪声模型，不是改电路 | Table 2（摘要转述）：去极化下 [[90,8,10]]≤8、[[144,12,12]]≤10；三种偏置模型（full-bias、non-CX bias、ancilla-only bias）下 d_circ 上界恢复到码距离；电路用 IBM 深度-7（ref. [14]）；p=2e-3、η=100 时 gross code 逻辑错误率降 8.5 倍（Sec. VI.3, Fig. 4）。未引用 Strikis（工具转述） |
| 2603.21499 | Zhang et al. · 2026-03-23 | ASC：SMT/CP-SAT 求深度最优调度 | 深度地板 | Table II：[[144,12,12]] ASAP 16、coloration 12、ASC 7（CNOT/TICK 深度），编译<5 分钟；摘要：对 IBM 列出的所有 BB 码"no depth-6 ... circuit exists"。我在全文里搜 distance，只出现码距离，**没有 d_circ 数字**；评估器是 Stim + BP-OSD，噪声同 IBM 原文 |
| 2601.12509 | Liu et al. · 2026-01-18（ASPLOS'26） | AlphaSyndrome（MCTS + 译码器反馈） | 方法近邻 | BB 码只有 [[72,12,6]]：相对 IBM 调度 BP-OSD 降 44%、Unionfind 降 10%（Sec. 5.4，Fig. 13）；全文检索 gross/[[144/Strikis/flag：没有 gross code、没有 Strikis、没有 flag |
| 2601.17580 | Viszlai et al. · 2026-01-24（ASPLOS'26） | PropHunt（MaxSAT 迭代消除歧义子图） | 方法近邻 | Table 1 码：表面码 [[9,1,3]]–[[81,1,9]]、LP [[39,3,3]]、[[54,11,4]]、RQT [[108,18,4]]、[[60,2,6]]，**无 BB 码**（Sec. 6）；Sec. 8：不加额外 ancilla/flag，"future work could explore augmenting the circuits output by PropHunt with flag fault-tolerance" |
| 2609.12020 | Ye, Pabla, Palsberg · 2026-09 | FastSched（PPO RL） | RL 对手 | Table 1 码只有表面码、Steane、LP39、RQT54、RQT60、RQT108 等（J7,1,3K…J108,18,4K），**无 BB 码**；对 AlphaSyndrome 平均降 25.9%（11 个电路）、对 PropHunt 降 71.7%（8 个电路）（Sec. 5.1，Table 1）；全文检索：不含 Strikis/left-right |
| 2607.25865 | Yan et al. · 2026-07-28 | OmniQEC（LLM 搜码，慢环做电路级评估） | "码搜索 + 电路级评估" | 调度："scheduled through edge colouring of the associated Tanner graph [43]"（Methods，Circuit-synthesis module）；在 N=98 和 N=240 物理比特预算下优于 [[72,12,6]] 和 [[144,12,12]]（摘要）；Strikis 仅出现在参考文献表 [47]；Outlook 说"future: agents that adapt circuit schedules, flag-qubit placement"，即**调度/flag 未被搜索** |
| 2609.06572 | （作者未核实）· 2026-09 | 权重 8 的 BB 码搜索与电路级模拟 | 码搜索，不联合调度 | 摘要转述："Whether the schedule can be made fault tolerant (e.g. via flag qubits or a careful CNOT ordering ...) is the key open circuit question for weight-8 codes"；用深度 10 的 maximally packed 调度做电路级模拟（Sec. 6.2，工具转述） |
| 2606.02418 | Cruz-Benito et al.（IBM）· 2026-06 | LLM 进化搜 BB 码 | 码搜索，不联合调度 | 评估为码级参数（k、BP-OSD 距离、MILP 认证），"No syndrome extraction schedule is searched"（工具转述） |
| 2508.09082 | （作者未核实）· 2025 | 低连接度广义自行车码与 hook error | 不联合搜索 | 工具转述：构造对 hook error 稳健的提取模式，不给出电路距离=码距离的完整电路 |

## 1. 2603.05481 v2 在交错电路上说了什么

### 1.1 定义（原文，PDF 全文）
- **Left-right circuit（Sec. III.A，Eq. 4–6）**：把数据比特分成左集合（l 个）和右集合（r=n−l 个），HX=[LX|RX]，HZ=[LZ|RZ]。对 LX、RX、LZ、RZ 各取一个二部 Tanner 图的合法边着色 C(·)。LX 与 RZ 的 CNOT 并行，按边颜色排时间步，用 t1=max(|C(LX)|,|C(RZ)|) 步；然后 LZ 与 RX 的 CNOT 以同样方式排，时间步整体平移 t1+1，用 t2=max(|C(LZ)|,|C(RX)|) 步。X 辅助比特在时间步 1 制备、在 t1+t2+2 测量；Z 辅助比特在 t1+3 制备、在 t1+2 测量。总深度 t=t1+t2+2（Eq. 6）。原文："The staggering guarantees that the circuit is valid, since all CNOTs for the Z checks are applied before the CNOTs for the X checks of the same round, i.e., the SEC is non-interleaved."
- **Non-interleaved（Sec. II.A）**：原文："In general, CNOTs from checks that share data qubits may be interleaved. In contrast, non-interleaved circuits are those in which either all X-type CNOTs precede all overlapping Z-type CNOTs, or all Z-type CNOTs precede all overlapping X-type CNOTs." 极端例子是 alternating-XZ 电路（先测完所有 X 检查再测所有 Z 检查）。
- 他们的 SEC 模型（Sec. II.A）：每个检查一个专用辅助比特，CNOT 为主，所有操作（制备、测量、一/二比特门、idle）各占一个时间步，多轮可以错开（staggered）。注意：这里"alternating"指同一轮里先 X 后 Z，**不是**跨 cycle 交替电路，不要和 IBM Open Question 4 或 Shaw–Terhal 的 alternating 混淆。

### 1.2 关于交错电路的结论
- **Theorem 1（Sec. IV，Eq. 9–12，PDF 文本）**：对非交错电路 C′，d′_circ = d_ext(E)，且 d′_circ ≤ d_ext(R) ≤ Δ(E)；Eq. 12：d′_circ ≤ d_circ（后者为对应的交错版本的电路距离）。原文解读："forming an interleaved version of the circuit cannot reduce the distance but may further improve it."（Sec. IV，Theorem 1 后的讨论）。Sec. VII 进一步精确说明：从非交错 SEC 出发、保持每个检查内部 CNOT 相对顺序只调整时间，得到的交错电路距离不会下降"(but may increase)"，并写"This suggests that further performance gains may be achieved through clever interleaving strategies, which could serve as a foundation for future work on SEC design."
- **没有给出交错电路的构造，也没有给出交错电路的距离上界或下界。** Prop. 4（d_circ≤11）只对非交错电路成立；证明靠"任何非交错 SEC 的剩余错误集必含某单检查的 90 种集合之一"，对交错电路不适用。
- **开放问题（Sec. IV.3 末段）**：交错电路能否达到 d_circ=12（见上面引文）。
- **App. H 末尾**：作者自己说"We could further investigate non-staggered, interleaved variants of the circuit, which one could hope might increase the circuit distance. However, our motivation to do this is reduced by the very nice recent paper on morphing bivariate bicycle codes which produces circuits involving the same number of physical and logical qubits as the gross code, but with circuit distance twelve Ref. [38]."（[38]=Shaw–Terhal PRL 134, 090602。注意：见第 2 部分，这是另一个 [[144,12,12]] 码。）
- **数字（附出处）**：gross code 非交错电路 d_circ≤11（Prop. 4，Sec. IV.3；90 种单检查排序中 45 种已推出≤10）；均匀平铺非交错电路≤10（Prop. 5，App. H）；三色平铺：4^3=64 种组合中仅 3 种（互为颜色循环置换）扩展码距离上界为 11（Prop. 6 证明，App. H）；Fig. 11 说明 90^3−3=728997 种其余模式≤10；Fig. 12 给出深度 8 的显式电路，d_ext 上界 11，conjecture 取等；支持证据是对该电路搜最小权重逻辑算符"ten thousand outer loops"没找到 <11 的，对标准电路一个 outer loop 就找到权重 10 的（App. H 第 2 小节）。这是上界搜索，不是证明。
- **没有 gross code 的电路噪声逻辑错误率**：Fig. 2 的码是 Tanner200、HGP625、Haah128、FB126（Table II），不含 gross code；我对全文检索 "gross" 的所有出现位置，没有找到对 d_circ=11 电路的 pL 模拟。他们在 App. G 声明 d_circ/N_fail 的改进"do not necessarily translate directly to better QEC system's performance"。
- **关于"多辅助/flag/Shor 型"（Sec. I）**：原文："Hook errors can be mitigated using Shor-type syndrome extraction, by augmenting single-ancilla SECs with flag qubits, or through related gadget constructions. However, such techniques often incur additional circuit depth and/or qubits"，无定量数据。
- **Strikis 列出的开放/未来方向（Sec. VII、App. G）**：（i）交错电路能否到 12（Sec. IV.3）；（ii）"clever interleaving strategies"（Sec. VII）；（iii）扩展到 Floquet / morphing 等时间依赖码、逻辑操作与码变形，需要"rethinking how CNOT schedules are defined and coordinated across successive SEC rounds"，以及相邻轮重叠带来的开销（Sec. VII）；（iv）残差画像无法反映不同检查之间残差错误的相互作用，建议做更重的分析（App. G，FB126 的唯一反例）。没有"联合码搜索"之类的条目。
- **我的推断（原文没写，请核对 `decoder_setup.py` 后再用）**：IBM Table 5 调度在 Z 右检查用第 1、2、6 轮（A1^T、A3^T、A2^T），X 右检查用第 3、4、5 轮（B2、B1、B3），所以对同一个右数据比特，有的重叠检查对是 Z 先于 X（轮 1、2 对 3–5），有的是 Z 后于 X（轮 6 晚于 3–5）。这符合 Strikis 的"交错"定义，所以 IBM 原电路很可能是**交错电路**（d_circ≤10），而 Strikis 的 d_circ=11 电路是非交错的 LRC。这意味着"交错就更好"并非自动成立；Theorem 1 的单向性只保证"同一内部顺序的非交错电路"不会因交错而变差。

## 2. 有没有人给出 d_circ 等于码距离的 gross code（或其他 BB 码）电路

| 对象 | 结果 | 代价 | 来源与状态 |
|---|---|---|---|
| gross code 本体（A=x³+y+y²，B=y³+x+x²），去极化噪声，标准单辅助比特 | 最优已知 d_circ=11（猜想），≤11 对非交错电路是定理 | 深度 8（摊销后，与 IBM 原电路相同） | 2603.05481 Prop. 4、Fig. 12。**未达 12**；单作者组声称，未见独立复现 |
| 另一个 [[144,12,12]] 码（[[288,12,18]] BB 码的 morphing end-cycle 码） | d_circ≤12（BP-OSD 上界） | 总物理比特 288（含 ancilla，与 gross code 相同）；连接度 5；4 轮收缩电路（Table II）；不是 gross code 本身，是 2BGA 码；Fig. 3 模拟称性能与标准 [[144,12,12]] 相近 | 2407.16336 Table I。上界为 BP-OSD 估计（p=1e-4，OSD order 100），非精确值 |
| 标准 gross code + 偏置噪声 | d_circ 上界"恢复到码距离"（12），gross code 逻辑错误率 p=2e-3、η=100 降 8.5 倍 | 无电路改动，但假设 ancilla 噪声强偏置 | 2606.30592 Table 2、Sec. VI.3（工具转述，未读全文） |
| [[288,12,18]]（two-gross） | IBM 原电路 d_circ≤18（"unlikely to be tight"），Tour de gross 的 Table 4 给 two-gross d_circ≤18（idle/aut.、in-module），inter-module≤17 | 无改动 | 2308.07915 Table 1、Sec. 3；2506.03094 Table 4。**这些是 BP-OSD 上界**，不是证明等于 18 |
| 其他 BB 码（[[72,12,6]]、[[90,8,10]]、[[108,8,10]]） | IBM 原文：≤6、≤8、≤8（Table 1，见 `gross-code-baseline.md`）；Shaw–Terhal Table I 给 [[72,12,6]] 标准 ≤6、morphing 的 [[72,12,6]] end-cycle 码 d_circ 数字见其表（我只核到 [[144]]、[[288]] 行，其余未逐行核对） | — | 同上 |
| 带 flag / Shor / 多辅助的 BB 电路 | **未找到** | — | 搜索未见；PropHunt Sec. 8 与 2609.06572 都把 flag 列为未做 |
| 交错 + 单辅助比特，d_circ=12 | **未找到**；作者列为开放问题 | — | 2603.05481 Sec. IV.3 |

- **IBM 后续论文**：2506.03094（Tour de gross，2025-06）仍写 gross code d_circ≤10（Table 4），并把"找 d_circ 更大的调度且逻辑错误率不差于现有调度"列为 Outlook 条目。未找到 IBM 在 2026 年发布了 d_circ>10 的 gross code 电路。2606.02418（IBM Cruz-Benito）只搜码，不涉调度。
- **PropHunt / AlphaSyndrome / ASC / FastSched / OmniQEC 与 gross code**：全文检索的结果是——AlphaSyndrome、PropHunt、FastSched 都没有评估 gross code（BB 码仅 AlphaSyndrome 的 [[72,12,6]]）；ASC 只给出 gross code 深度 7（Table II），没给 d_circ；OmniQEC 用边着色调度、没报 d_circ。所以这五篇**没有任何一篇给出 gross code d_circ 的新数字**。Strikis Sec. VI.1 / App. F 称 PropHunt 的示例电路"achieved a larger circuit distance"但深度超过 3 倍；AlphaSyndrome 示例深度超过 2 倍（用的是 CC61 与 RQT108，非 BB 码）。

## 3. AlphaSyndrome 与 Strikis 等人是否互相比较过逻辑错误率

- **有一次单向比较，且不在 BB 码上**：Strikis App. F / Fig. 8 把 LRC 与 AlphaSyndrome 的 [[61,1,9]] 六角色码（CC61）电路、与 PropHunt 的 [[108,18,4]] RQT108 电路各比一个"representative circuit"，用他们自己的噪声模型和模拟设置（Sec. II.A、App. E）；结论："the substantial increase in circuit depth offsets the potential gain in circuit distance under realistic error-rate regimes"，即 LRC 更好。我没有读到具体倍数（Fig. 8 的曲线我读不到数值）；这是**作者自己做的、对手电路只取一个代表**的比较，不是独立复现。Sec. VI 末的 Note added 另称这两个工作"attain higher accuracy but at a much higher computational cost, thereby providing a complementary approach"。
- AlphaSyndrome（2026-01）早于 Strikis（2026-03），不可能比较；FastSched（2609.12020）对 AlphaSyndrome、PropHunt 比较了，但全文检索不含 Strikis / left-right；ASC 不含；OmniQEC 只在参考文献表中列了 Strikis。
- **gross code 上谁更好：没有人比较过**（AlphaSyndrome 没测 gross code；Strikis 没对 gross code 做电路噪声模拟；PropHunt/FastSched 无 BB 码）。唯一的 BB 码对比是 AlphaSyndrome vs IBM 调度的 [[72,12,6]]：BP-OSD 降 44%，Unionfind 降 10%（2601.12509 Sec. 5.4、Fig. 13，噪声为 IBM Brisbane 校准）。

## 4. "码 + 调度联合搜索"是否有人做过

- **标准单辅助比特调度 + BB/2BGA 多项式一起搜、以电路级性能为目标：未找到。**
- 最近的几项，及差别：
  - 2604.09797（Shaw–Terhal 2026）：在 morphing 电路范式下，对 Abelian 2BGA 码枚举收缩树，优化 end-cycle 码参数、连接度、比特数（摘要、Sec. 3.3）。差别：电路族是无辅助比特的 morphing 电路，不是 IBM 式单辅助比特 CNOT 调度；表格我没读到；搜索方法不是 LLM/SA/RL（"numerically search"，细节未读到）。**部分覆盖，需要读全文确认。**
  - OmniQEC（2607.25865）：LLM 搜码 + 电路级评估闭环，覆盖四个 qLDPC 族（含 BB）；差别：调度固定为边着色，没有调度搜索，评估用 pLER，不报 d_circ；消融无 SA/随机对照（见 `novelty-schedule-search.md`）。
  - IBM 原文 2308.07915：搜 BB 码时用的是码参数，并另外枚举了 936 个深度-7 调度变体。不是联合搜索。
  - 2606.02418（LLM 搜 BB 码）、2609.06572（权重 8 BB 码）：只搜码；后者明说调度是否容错"is the key open circuit question"。
  - 2508.09082：构造对 hook error 稳健的 GB 码调度，不联合搜索（工具转述）。
- 另有一个 GitHub 仓库（Anil077476/qldpc-bivariate-bicycle，搜索结果摘要）对 [[72,12,6]] 枚举所有 6!×6! 交错顺序，保留检测器确定的 2736 种有效调度（9 种重叠模式）。我没有读仓库，只见搜索摘要，**不能当作文献**，但说明"交错顺序可枚举且有合法性条件"对 [[72,12,6]] 在规模上可行（对 gross code 未验证）。条件为：每个重叠 (X 检查, Z 检查) 对中，X-CNOT 先于 Z-CNOT 的共享数据比特数为偶数。

## 5. 其他明显空白

1. **精确验证 Strikis 的 d_circ=11 电路**：Theorem 1 给出 d′_circ = d_ext(E)（对完整残差集等号），把电路距离计算化为小得多的扩展码距离问题，原文自己说"potentially allowing the exact distance (not just a bound) to be determined using exhaustive numerical methods"（Sec. IV，Theorem 1 后）。他们只做了上界搜索。是否有人用 MIP/SAT（如 2603.22532 的工具）做了精确验证：未找到。
2. **gross code 上的公平逻辑错误率对比**：IBM 电路 / Strikis d_circ=11 电路 / ASC 深度-7 电路 / AlphaSyndrome-PropHunt-FastSched 电路，同噪声、同译码器、p=1e-3 附近——**没有人做过**（见第 3 部分）。这条风险低，但新颖度也只是"基准评测"级。
3. **跨 cycle 交替电路用于 gross code**：IBM 原文 Open question 4（2308.07915 Sec. 10）与 Tour de gross 的 Outlook 都点了不同 cycle 用不同电路；Shaw–Terhal 2026 Prop. 3（2604.09797 Sec. 2.5）证明时间反演交替电路的 d_circ 不低于非交替电路，并说交替电路"can be larger"；但据我读到的片段，数值只出现在表面码/环面码，**BB 码上未见**（未读全文，需要核实）。Strikis 的 Prop. 4 针对"重复同一个 SEC"的非交错电路，我的推断是它不覆盖交替电路（原文没有讨论，需核对其 SEC 定义）。
4. **交错 + 多辅助/少量 flag 的混合方案的代价曲线**：无人给出 gross code 上"多少额外比特/深度换多少 d_circ，是否净收益"。Strikis 声称这类技术"typically worsening performance"（Sec. I），但这是定性说法，没有 gross code 数据。
5. **偏置/非均匀噪声下的调度优化**：2606.30592 表明噪声模型可以改变 d_circ 结论；Tour de gross 的 Outlook 也提到不同组件错误率不同。在 SI1000 或测量/Bell-coupler 错误更大的噪声下搜调度：未找到。
6. **AlphaSyndrome/PropHunt/FastSched 在 BB 码、gross code 上的结果**：FastSched 与 PropHunt 完全没测 BB 码，AlphaSyndrome 只测 [[72,12,6]]。用 gross code 做这些方法的对照：未找到。

## 新颖性判断
- **"用交错/多辅助/flag/跨 cycle 交替电路让 gross code 达到 d_circ=12（控制深度与比特数）"：判断为"空白，但有邻近的部分结果"。**
  - 有没有人做过完全相同的事？**未找到**。作者自己写的是开放问题（2603.05481 v2 Sec. IV.3），文献里也没有 gross code 的 d_circ=12 电路。
  - 最接近的三篇及差别：
    1. 2407.16336（Shaw–Terhal）：d_circ≤12 的是一个**不同的** [[144,12,12]] 码（morphing end-cycle 码），总比特 288，连接度 5，上界为 BP-OSD 估计。不是 gross code 本身。
    2. 2606.30592：只在偏置噪声下"恢复"到码距离，电路和码都不变。不是去极化噪声。
    3. 2604.09797：证明交替电路 d_circ 单调不降，但（据我读到的）只示例表面码/环面码。
  - **证据强度：中等**。2603.05481 v2 的相关章节我读了原文，所以"作者承认未解决"这点可靠。"全文献无人做过"这点受限于搜索覆盖（不是 arXiv 全库检索）和 2604.09797 未读全文；多辅助/flag 方向的"未找到"尤其是搜索引擎层面的负面证据。
  - **价值提示**：Strikis 自己说因为有 Shaw–Terhal 的 d_circ=12 结果，"our motivation to do this is reduced"。若 PI 的目标是"有一个 d_circ=12 的 288 比特 [[144,12,12]] 码"，那么 Shaw–Terhal 已部分满足；新结果的卖点必须是"标准 gross code 的固定连接度 6 与单辅助比特电路"，或明显更低的 N_fail / pL。
  - **一个可核对的风险**：若存在某种理论障碍，使任何交错电路也无法达到 12，则该方向会变成一个"负结果"（也可发表）。目前我没有找到这类下界，也没有找到反例构造。
- **"码 + 调度联合搜索"：判断为"部分做过"**（2604.09797 在 morphing 范式下；OmniQEC 在固定调度下做码 + 电路级评估）。标准单辅助比特调度范式下联合搜索：未找到。证据强度：低到中（2604.09797 的表格没读到）。
- **"gross code 公平逻辑错误率对比"：空白**，证据强度：中（多篇全文检索确认没人在 gross code 上比较）。

## 对本项目的建议
1. 在向 PI 汇报"交错电路达到 d_circ=12"方向时，同时写明：这是 Strikis 明确列出的开放问题，没有任何已知下界或构造；同时已有一个同参数不同码的 d_circ≤12 结果（Shaw–Terhal，288 比特），所以动机需要重述，不能只说"gross code 没有 d_circ=12 电路"。
2. **最有希望的空白 1：交错 + 跨 cycle 交替电路的 d_circ 搜索，并用精确方法验证。** 理由：Theorem 1 提供"从非交错 d_circ=11 电路出发只调时间不会变差"的单调性，所以可以以 Fig. 12 电路为起点做局部搜索；Shaw–Terhal 的交替电路 d_circ 单调性给出另一条独立路径；IBM 原文 Open Question 4 也指向这里。搜索目标可以用 N_fail 或 d_circ 上界（BP-OSD 估计）当快速评估器，最终用 MIP/SAT 精确验证。这里搜索空间较小、评估器已有、且可以对照 SA/随机搜索（满足 CLAUDE.md 铁律 5）。
3. **最有希望的空白 2：gross code 上的公平基准 + 对 Strikis 电路的独立精确验证。** 成本低、风险低，直接服务 G0/G1 关卡，也是任何后续"超过 baseline"声明的必要前置（同噪声、同译码器比较 IBM / Strikis d_circ=11 / ASC 深度-7）。新颖性是"基准与复核"级，不是新方法级，但为空白 1 提供对照。
4. 多辅助/flag 方向我不建议先做：Strikis 声称代价通常得不偿失，且需要同时控制深度、比特数和译码器适配；搜索空间也更大。除非空白 1 被证明走不通再考虑"仅给少数危险检查加 flag"。
5. 动手前需要补读（我没读到）：2604.09797 全文（尤其 Sec. 2.5 对 BB 码的应用、App. C.4 的表）；2606.30592 的完整噪声定义；2603.05481 App. E 的噪声模型与 Fig. 8 数值；Shaw–Terhal 2407.16336 Table I 中 [[72,12,6]]、[[90,8,10]]、[[108,8,10]] 行。
6. 引用时的措辞：Strikis 的 d_circ=11 是"conjecture"，所有 BP-OSD 距离是"上界"；Shaw–Terhal 的 [[144,12,12]]≤12 是另一个码。不要写成"gross code d_circ=12 已被实现"。
