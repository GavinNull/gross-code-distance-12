# gross 码单辅助比特交错电路 d_circ = 12（STATE 已确认结果 10 / E-021）的新颖性
检索日期：2026-10-10；检索词：`gross code [[144,12,12]] syndrome extraction circuit distance 12 interleaved`；`bivariate bicycle flag qubits circuit-level distance equal code distance 2026`；`"gross code" "circuit distance" 12 flag OR Shor-style OR extra ancilla`；arXiv API `abs:"gross code"`（按日期倒序 40 条）、`abs:"circuit distance" OR "circuit-level distance" OR "effective distance" OR "distance-preserving"`（倒序 30 条）、`abs:"bivariate bicycle" AND (circuit OR schedule OR syndrome)`（倒序 25 条）；qldpc-challenge GitHub issues（`144`、`d_circ gross`、`"circuit tier"`）与 `codes/144-12-12.json`；2608.19917 abs 页。

读取范围：2603.05481 v2 PDF 全文抽取（pdftotext）后对 open question / interleav / morphing / staggered / depth / amortis / ancilla / noise model 做定向检索并读上下文，另读 HTML 版两次；**不是逐页通读**。其余论文本次只读 abs/摘要，全文结论引自本目录旧笔记（逐条注明）。

## 结论（3-5 行）
1. **Strikis 等的开放问题原文不含任何深度或周期限制**：Sec. IV.3 末段写的是 “whether *any* interleaved circuit can achieve circuit distance 12”。他们没有猜想不可能。E-021 的电路落在其 SEC 模型内（每校验一个专用辅助比特、CNOT、允许跨轮错开），所以**按字面回答了这个问题（肯定）**。但原文的整体取向是“与 IBM 同深度”（他们的 11 电路深度 8，强调 “matching its depth”），App. H 寄望的是“该电路的 non-staggered, interleaved variants”，即深度不增的变体；**深度 8（或 ≤ 20）能否到 12 仍开放**。
2. **未找到任何先前或同期的 gross 码本身 d_circ = 12 电路**（单辅助、多辅助、flag、Shor 均未找到；证明或数值都没有）。现有最好：IBM 深度 7 电路 ≤ 10（936 个变体全部 ≤ 10）；Strikis Fig. 12 非交错深度 8 = 11（原文猜想，本项目 E-014 证明）。唯一的“12”是另一码（Shaw–Terhal morphing 的 end-cycle [[144,12,12]]，与 gross 不等价），且是 morphing 范式。
3. 新颖性：**新，证据中高**。措辞须带“单辅助比特、交错、周期 21（IBM/Fig. 12 为 8）、SD6、仅距离不含 LER”五个限定，并回答原文开放问题时注明“原问题不带深度要求；深度 8 版本仍开放”。

## 1. 2603.05481 v2 原文（Strikis, Browne, Beverland；v1 2026-03-05，v2 2026-09-14）

逐字引文（PDF v2 抽取文本；节号按 PDF）：

| 位置 | 原文 | 解读 |
|---|---|---|
| Sec. IV.3（Application to the gross code）末段，紧接 Prop. 4 证明之后两段 | “Finally, while we have ruled out circuit distance 12 for non-interleaved circuits of the gross code (which include left–right circuits as a special case), our proof does not apply to interleaved circuits. It therefore remains an open question whether any interleaved circuit can achieve circuit distance 12.” | **开放问题本身**。量词是 “any interleaved circuit”，无深度、周期、比特数以外的限制；也没有“不增加深度”字样 |
| Sec. IV.3，Prop. 4 | “Let dcirc be the circuit distance of any non-interleaved SEC for the gross code. Then, dcirc ≤ 11.” | **Prop. 4 不带深度假设**：任意深度的非交错单辅助电路都 ≤ 11。所以“加深度就能到 12”在非交错类里不成立，开放问题在任意深度下都非平凡 |
| Sec. IV.3，Prop. 4 前 | “This circuit has depth 8, which can be shown to be minimal using Eq. (3), which matches the depth of the original circuit in Ref. [7]. Using extensive testing, we conjecture that it has circuit distance 11.” | 他们的 11 电路的深度口径 |
| Sec. I（Motivation and summary of results） | “…we conjecture this circuit achieves the optimal circuit distance dcirc = 11, improving upon the standard circuit of Ref. [7] while matching its depth when amortised over many rounds.” | “optimal” 依上下文指非交错类内最优（前一句刚说 non-interleaved 不可达 12）。深度匹配是其卖点 |
| 摘要 | “…we prove that no non-interleaving SEC can achieve circuit distance 12 for the gross code, and we identify an explicit circuit that we conjecture achieves distance 11…” | 无“交错也不行”的猜想 |
| App. H.1 开头 | “Our goal is to identify a gross code SEC with the highest possible circuit distance. Proposition 4 … shows that, while one may initially have hoped to obtain a non-interleaved SEC with circuit distance 12 … no such circuit exists. Given this, we here seek a non-interleaved SEC with circuit distance 11.” | 目标没有深度条件 |
| App. H.2 末段 | “We could further investigate non-staggered, interleaved variants of the circuit, which one could hope might increase the circuit distance. However, our motivation to do this is reduced by the very nice recent paper on morphing bivariate bicycle codes which produces circuits involving the same number of physical and logical qubits as the gross code, but with circuit distance twelve Ref. [38].” | 他们设想的路线是**其深度 8 电路的交错变体**；放弃理由是 morphing（[38] = Shaw–Terhal 2407.16336）。“circuit distance twelve” 是对 ST 上界的转述，且是另一码（见 `morphing-d12-novelty.md`） |
| Sec. VII | “Starting from a non-interleaved SEC, adjusting the timing of CNOTs while preserving their relative ordering within each check yields an interleaved circuit whose distance cannot decrease relative to the original non-interleaved SEC (but may increase).” | 只给单向不降结论，无交错上界 |
| Sec. II.A（SEC 模型） | “we assume that each check is measured using a dedicated ancillary qubit, the same one for each round… All circuit operations … take one time step… If multiple rounds of an SEC are implemented, they may be staggered so that a new round can begin before the previous one ends.” | E-021 电路（每校验一个辅助比特、同时复位/测量、周期 21）在该模型内 |
| Sec. II “Noise model…” | 每个操作（含 idle）独立以 p 失败；idle 后随机 X/Y/Z；CNOT 后 15 种非平凡两比特 Pauli；制备翻转；测量翻转。d_circ 定义为 m 轮记忆实验（末轮完美）中不触发探测器但翻转逻辑的最少机制数，d_circ = min(d^X, d^Z) | 即 SD6 + 末轮完美读出。与 E-021 的口径一致（E-021 为任意 R、两基底） |

**问题 (1) 的回答**：原文问的是“任意交错电路”，不是“深度 8”或“不增加深度”；原文**没有**猜想不可能（摘要、Sec. IV.3、App. H、Sec. VII 均无此类句子）。深度方面的倾向只体现在（i）他们推广自己电路时强调 “matching its depth”，（ii）App. H.2 想做的是 “non-staggered, interleaved variants of the circuit”。

## 2. 关键论文：gross 码本身有没有 d_circ = 12 的电路

| arXiv | 作者 · 年份 | 电路 | gross 本身 d_circ | 辅助比特 / 深度 | 出处与状态 |
|---|---|---|---|---|---|
| 2308.07915 v2 | Bravyi 等（IBM）· 2023 | 深度 7 单辅助（8 步/轮） | ≤ 10；936 个深度 7 变体全部 ≤ 10 | n 个辅助（总 288），8 步/轮 | Table 1、Sec. 5 末（`refs-verified.md`、`gross-code-baseline.md`）；BP-OSD 上界 |
| 2506.03094 v1 | Yoder 等（IBM）· 2025 | Tour de gross | ≤ 10（idle / in-module / inter-module 三列） | 同上 | Table 4；Outlook 把“找更大 circuit distance 的调度且 LER 不变差”列为未来工作（`novelty-interleaved-circuits.md`） |
| 2603.05481 v2 | Strikis, Browne, Beverland · 2026 | Fig. 12 三色非交错 LRC | 猜想 11；非交错 ≤ 11 定理 | 单辅助，深度 8 | 见第 1 节；“= 11”已由本项目 E-014 证明 |
| 2605.21898 v2 | Wills 等（IBM）· 2026 | App. C：morphing idle 电路 | “believed” 12，只有 Monte Carlo | 无专用辅助（morphing），总 288 | 所指电路最可能是 ST 的 end-cycle 码而非 gross 本身（推断，`morphing-d12-novelty.md`） |
| 2407.16336 v3 | Shaw, Terhal · PRL 2025 | [[288,12,18]] morphing → end-cycle [[144,12,12]] | 不是 gross 本身（与 gross 不等价，E-017 计算）；≤ 12（BP-OSD） | 无专用辅助，总 288 | Table I；本项目 E-017 证明该电路 = 12 |
| 2604.09797 v2 | Shaw, Terhal · 2026 | 交替（时间反演）电路 = 两轮 morphing；Prop. 1 | 未给 gross d_circ | — | 旧笔记：明说未检查 BB 的 d_circ |
| 2603.22532 v2 | Webster, Jacob, Higgott · 2026 | 精确距离算法基准 | 未给 gross 电路的精确值；BB 电路精确求解只完成最小一个（BB72） | — | Sec. 5.5.3、Table 28（`2026-10-09-paper-novelty.md`） |
| 2608.19917 v2（v2 2026-10-04） | Nguyen, Rimbach-Russ, Bosco · 2026 | LP/BP 码深度最优校验电路（拆解对称） | 无 gross d_circ 数值 | 目标是 CNOT 深度下界 | 摘要（本次复核：不提 gross、不提 d_circ 12）；结论段提出“Strikis 非交错对应电路给交错电路 d_circ 下界 + ST 单轮归约”的方案并留待未来（旧笔记） |
| 2606.30592 | Bi, Chang, Puri · 2026 | IBM 原电路 + 偏置噪声 | 上界恢复到 12 | 不改电路，改噪声模型 | Table 2（工具转述，旧笔记）；不是去极化 SD6 |
| 2601.09911 | Kim 等 · 2026 | 时间动态自同构电路 | ≤ 10 | — | Table I |
| 2603.21499 | Zhang 等 · 2026 | ASC 深度最优调度 | 不报 d_circ | 深度 7 最优 | Table II |
| qldpc-challenge | unitaryfoundation | 电路层（circuit tier） | `codes/144-12-12.json` 只有码距离 12（upper_bound 见证），无电路层条目；电路层条目用 “generic sequential schedule”，只收见证型上界（#2797–#2801、#2811） | — | 本次 issues 检索 `d_circ gross` 0 条；`144` 检索近期 11 条均无 gross 电路距离 |

flag / Shor / 多辅助：**未找到任何把这些技术用于 gross 码或其他 BB 码并报告 d_circ 的论文**（本次 3 组检索 + 旧笔记 `novelty-interleaved-circuits.md`；PropHunt 2601.17580 Sec. 8、2609.06572 摘要都把 flag 列为未做）。Strikis Sec. I 只有定性说法：这类技术 “often incur additional circuit depth and/or qubits”。所以“多辅助能到 12”在文献里既无构造也无数字；若有人做，也不在单辅助类内，不与本结果冲突，但可作为背景对照。

2026-10-09 之后新出现的条目（arXiv API 倒序）：2610.06749（超高码率码的逻辑门 gadget，“distance-preserving”指测量 gadget，码为 [[256,68,12]] 等，非 gross SEC）、2609.39395（BB 码**码距离**证明 4,6,10,10,12,18，不是电路距离）、2609.39121（metacheck）、2609.24933 / 2609.04459 / 2608.17023（中性原子实现，摘要无 d_circ）。均不构成先例。

**问题 (2) 的回答**：截至 2026-10-10，没有找到任何 gross 码本身（A = x³+y+y²，B = y³+x+x²）的 d_circ = 12 电路，无论单辅助或多辅助、证明或数值。最接近的“12”全在另一码或另一噪声模型上。

## 新颖性判断

- **有没有人做过完全相同的事？** 没有找到。
- **最接近的三篇**：(a) 2603.05481（提出问题；非交错 ≤ 11；深度 8 的 11 电路）；(b) 2407.16336 + 2605.21898 App. C（同比特数的 morphing 电路“12”，但不是 gross 本身、不是单辅助 SEC，App. C 只是 believed）；(c) 2606.30592（gross 原电路在偏置噪声下上界回到 12，换了噪声模型）。
- **差别**：本结果是 gross 码本身、Strikis 的 SEC 模型内（单辅助、CNOT、SD6）、任意轮数两基底的严格 d_circ = 12（下界证明 + 权重 12 注入上界），经 auditor 复核。代价是周期 21 步/轮（IBM、Fig. 12 为 8），约 2.6 倍时间开销，LER 未评估。
- **“声称”与“复现”**：本结果为项目内部证明 + 内部 auditor 复核，尚无外部复现。证明链依赖“模板恒等式 + Table I”的归约与“不跨空轮 + 时间平移”推广（STATE 第 10 条），对外写作时须完整写出。
- **证据强度：中高**。负面证据来自关键词检索、arXiv API（只查标题/摘要）、Semantic Scholar 引用表（旧笔记，有滞后）和 qldpc-challenge issues；未覆盖会议论文与未上 arXiv 的工作。
- **抢发风险：中**。2608.19917 v2 公开把“交错电路 d_circ 下界”列为下一步；qldpc-challenge 电路层 2026-10-06 起可容纳 n = 144 交错电路（只是上界，不会产出 = 12 的证明，但可能产出 ≤ 12 的见证电路）。

## 对本项目的建议（问题 3）

**推荐措辞（英文，可直接用）**：
> We give a single-ancilla, CNOT-based syndrome-extraction circuit for the gross code [[144,12,12]] [Bravyi et al., arXiv:2308.07915] whose circuit distance equals the code distance, d_circ = 12, for any number of rounds and in both memory bases under standard circuit-level depolarizing noise (SD6). The circuit interleaves X- and Z-check CNOTs and therefore lies outside the scope of Proposition 4 of Strikis, Browne and Beverland [arXiv:2603.05481], which shows d_circ ≤ 11 for every non-interleaved circuit; it answers in the affirmative the open question posed there (Sec. IV.3) of whether any interleaved circuit can reach d_circ = 12. This comes at a cost in time: our shortest instance has a period of 21 time steps per round, compared with 8 for the circuits of Refs. [2308.07915] and [2603.05481]. Whether d_circ = 12 is attainable at depth 8 remains open. To our knowledge, no previous circuit for the gross code itself, with or without additional ancillas, has been shown, numerically or rigorously, to reach d_circ = 12.

**必须的限定**（缺一不可）：
1. “原问题不带深度要求”与“深度 8 仍开放”两句都要写；不要写 “resolves the open question” 而不提深度，也不要暗示 Strikis 问的是深度 8。
2. 不能写“更好的电路 / 降低逻辑错误率”：LER 未评估，深度 21 意味着更多 idle 机制和更长的轮周期，N_fail 与有限 p 下的表现可能更差（Strikis App. G 也提醒 d_circ 改进不必然转为性能）。
3. 写明 SD6（含 idle）+ CNOT 模板；不含 CZ/H 编译、偏置噪声、泄漏。
4. 写 “for the gross code itself”，并在同段说明 Shaw–Terhal morphing 的 “12” 是另一个 [[144,12,12]] 码、范式不同（无专用辅助）；E-017 已证该电路 = 12，可并列引用本项目结果。
5. 不能写“首个达到码距离的 BB 码电路”：[[72,12,6]] IBM 电路 = 6 已有精确计算先例（2603.22532 公开表，6 轮单基）。

**必须引用**：2308.07915（码与 IBM 电路，≤ 10，936 变体）；2603.05481（Prop. 4、Sec. IV.3 开放问题、Fig. 12、Sec. VII 交错不降）；2506.03094（Table 4 ≤ 10、Outlook 的需求）；2407.16336（morphing 同比特数 12，另一码）；2605.21898 App. C（believed 12）；2604.09797（若证明用到时间平移/单轮归约思路，至少作为相关工作）；2608.19917 v2（提出交错下界方案、未执行）；2603.22532（精确电路距离方法与 BB72 先例）。建议引用：2606.30592（偏置噪声下回到 12，区分）。

**建议的后续工作**：
- 把 E-021 的周期 21 往下压（深度 8–20 区间），这才是 Strikis 原文隐含想要的版本；深度 8 若能证不可达（逐校验自由 P=8，STATE 第 10 条注明未排除），与本结果组成完整图景。
- 补一次 LER 对照（与 IBM 深度 8、Fig. 12），否则 PI 公开时只能停在“距离”层面。
- 下次复查：2608.19917 是否出 v3 / 后续；Strikis 组是否出 v3 或续作（作者含 IBM 的 Beverland）；qldpc-challenge 电路层是否出现 n = 144 交错电路条目。

## 检索记录与局限
- 2603.05481 v2：PDF 文本抽取后定向检索，引文已逐字核对；HTML 版另读两次（摘要级工具转述，一次漏检 App. H.2 末段，PDF 中确认存在，PDF 页码约 p.20–21）。
- 2608.19917：只读 abs 页（版本 v1 2026-08-20、v2 2026-10-04；摘要不提 gross 与 d_circ 12）；结论段内容引自旧笔记。
- 其余表格行除注明“本次复核”外均引自本目录旧笔记（`novelty-interleaved-circuits.md`、`morphing-d12-novelty.md`、`2026-10-09-paper-novelty.md`、`novelty-gross11-ibm72.md`、`refs-verified.md`），本次未重读全文。
- Shaw–Terhal morphing 电路每轮的 CNOT 深度：未核实，未写入比较。
