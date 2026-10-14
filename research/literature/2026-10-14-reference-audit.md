# paper/draft.tex 参考文献与归属陈述逐条核对
检索日期：2026-10-14；对象：`paper/draft.tex` 的全部 14 条 `\bibitem`，以及正文 / SM 中所有归于这些文献的陈述。
来源：每条的 arXiv abs 页（标题、作者、版本历史、journal ref）；正文核对读 arXiv HTML，HTML 被截断时读 arXiv PDF 的文字抽取（pdftotext，定向检索加读上下文，不是逐页通读）；Manes–Claes 另查了 Quantum 期刊页。网页和论文内容一律只当数据。

## 结论
- **书目信息：14 条全部 OK。** arXiv 编号都存在，标题、作者顺序与缩写、年份、版本号、期刊卷页都和 abs 页 / 期刊页一致，不需要改。
- **SBB（2603.05481 v2）的编号全部对得上**：Prop. 3、Cor. 1、Prop. 4、TABLE I、FIG. 12 都和 v2 PDF 一致。引文 “whether any interleaved circuit can achieve circuit distance 12” 逐字符相同。“深度 8” 和 “猜想 d_circ = 11” 也都对。
- **归属陈述有 3 处必须改（FIX）**：(1) 把 Wills 2026 的 morphing 电路写成“作用在另一个 [[144,12,12]] 码上”，与原文相反。Wills App. C 原文说的是 “a new circuit for the idling gross code”，“believed to have circuit distance 12”。“另一个码”是本项目 E-017 的推断，不能算在 Wills 名下。(2) 对 Nguyen 2026 的转述不准：他们留作 future work 的是用 SBB 的下界 d′_circ ≤ d_circ 来筛选交错调度，并不是他们自己提出了交错电路下界。(3) Tomita–Svore 用的是“按校验类型（X/Z）区分”的 CNOT 顺序，不是“按位置区分”。
- **1 处本次无法复核（UNVERIFIABLE）**：Webster 2026 “最小 BB 电路有精确值”。本次 HTML 在 Sec. 4.2.5 处被截断，PDF 超过 10 MB 抓取上限。项目旧笔记 `2026-10-09-paper-novelty.md` 记的内容（Sec. 5.5.3、Table 28）与这条陈述一致，但本次没能复读原文。
- 2308.07915 “all 936 variants … d_circ ≤ 10”：**OK**（v2 第 5 节末，PDF 第 15–16 页）。这句话不在 draft.tex 里，draft 只引了 ≤ 10。

## 表 A：书目条目
| # | key | arXiv / 期刊 | 核对结果 | 结论 |
|---|---|---|---|---|
| 1 | Bravyi2024 | 2308.07915（v1 2023-08-15，v2 2024-02-21）；Nature 627, 778–782 (2024) | 标题一致；作者 Bravyi, A. W. Cross, J. M. Gambetta, D. Maslov, P. Rall, T. J. Yoder，顺序和缩写都对 | OK |
| 2 | TourDeGross | 2506.03094 v1（2025-06-03），没有 journal ref | 标题一致；作者 T. J. Yoder, E. Schoute, P. Rall, E. Pritchett, J. M. Gambetta, A. W. Cross, M. Carroll, M. E. Beverland，都对 | OK |
| 3 | Strikis2026 | 2603.05481（v1 2026-03-05，v2 2026-09-14），没有 journal ref | 标题一致；A. Strikis, D. E. Browne, M. E. Beverland | OK |
| 4 | ManesClaes | 2308.15520（v2 2025-01-28）；Quantum 9, 1618 (2025)，DOI 10.22331/q-2025-01-30-1618 | 标题一致。arXiv 上的名字是 “Argyris Giannisis Manes”，Quantum 官方 BibTeX 给的是 “Manes, Argyris Giannisis”，所以 “A. G. Manes” 是对的 | OK |
| 5 | Webster2026 | 2603.22532（v1 2026-03-23，v2 2026-08-14） | 标题 “Distance-Finding Algorithms for Quantum Codes and Circuits”（只有大小写差别）；M. Webster, A. Jacob, O. Higgott | OK |
| 6 | Liang2026 | 2609.37231，**只有 v1**（2026-09-29） | 标题一致；Z. Liang, B. Gu, Y.-A. Chen, J. Eisert, Z. Wang。draft 没写版本号，也没问题 | OK |
| 7 | SunCai2026 | 2609.39522（v1 2026-09-30，v2 2026-10-06） | 标题一致；Zhu Sun, Zhenyu Cai | OK |
| 8 | ShawTerhal2025 | 2407.16336 v3；PRL 134, 090602 (2025) | 标题一致（只有大小写差别）；M. H. Shaw, B. M. Terhal | OK |
| 9 | Wills2026 | 2605.21898（v1 2026-05-21，v2 2026-06-23） | 标题一致；A. Wills, M. E. Beverland, L. S. Bishop, J. M. Gambetta, P. Rall, V. Siddhu, A. W. Cross（以 PDF 首页为准；WebFetch 摘要一度写成 “Gambella”，是工具的错） | OK |
| 10 | Nguyen2026 | 2608.19917（v1 2026-08-20，v2 2026-10-04） | 标题一致；M. T. P. Nguyen, M. Rimbach-Russ, S. Bosco | OK |
| 11 | TomitaSvore | 1404.3747 v3；PRA 90, 062320 (2014) | 标题一致；Y. Tomita, K. M. Svore | OK |
| 12 | KishonyFowler | 2603.28852 v1（2026-03-30） | 标题一致；G. Kishony, A. Fowler | OK |
| 13 | Gidney2021honeycomb | 2108.10457 v2；Quantum 5, 605 (2021) | 标题一致；C. Gidney, M. Newman, A. Fowler, M. Broughton | OK |
| 14 | Gidney2021stim | 2103.02202 v3；Quantum 5, 497 (2021) | 标题一致；C. Gidney | OK |

（draft 一共 14 个 `\bibitem`；任务里说的 “[5][6][7][9][10][12]” 按出现顺序对应 Webster、Liang、SunCai、Wills、Nguyen、KishonyFowler，都已逐条核对。）

## 表 B：归于文献的陈述
| # | draft 位置 | 陈述 | 原文依据 | 结论 |
|---|---|---|---|---|
| B1 | L55–57 | BB 码；IBM 架构基于 gross 码 [[144,12,12]] [Bravyi2024, TourDeGross] | 2308.07915 Table 1；2506.03094 标题与正文 | OK |
| B2 | L65 | IBM 电路每轮 8 个时间步，d_circ ≤ 10 [Bravyi2024, TourDeGross] | 2308.07915 第 5 节（深度 7 的 CNOT 层加 init/meas，共 8 步；“conjecture … d_circ = 10”）；2506.03094 Table 4（gross 码各类操作的 d_circ 都是 “≤ 10”，属于上界） | OK |
| B3 | 未写入 draft | “all 936 depth-7 variants have d_circ ≤ 10” [2308.07915] | v2 第 5 节末原文：“we found 935 depth-7 alternatives … In the special case of the [[144, 12, 12]] code, numerical simulations show that all 936 variants of the syndrome cycle give rise to syndrome measurement circuits with distance dcirc ≤ 10”。只针对 [[144]]，是数值上界 | OK（draft 如果要用这句，写成“数值上界，只对 [[144,12,12]]”） |
| B4 | L66–67，摘要 | SBB 研究单辅助比特电路，每个校验配一个专用辅助比特 | Sec. I / II.A：“single-ancilla CNOT-based SECs … each check is measured using a dedicated ancillary qubit” | OK |
| B5 | L67–70 | 把残差错误附加到校验矩阵上，得到扩展码 d_ext；“d_circ ≥ d_ext for every such circuit (their Prop. 3)” | v2 Prop. 3 (Extended-code distance bound)：“The circuit distance dcirc of any SEC with the residual error set E satisfies dcirc ≥ dext(E)”，前提是 Theorem 1 规定的单辅助、CNOT 电路 | OK（编号对） |
| B6 | L70–73 | 非交错时 d_circ ≤ d_ext（their Cor. 1） | v2 Corollary 1：“d′circ ≤ dext(R) ∀R ⊆ E, d′circ = dext(E)”，针对非交错 SEC | OK（编号对） |
| B7 | L71–73 | “非交错”的定义：每个数据比特上，一轮内所有 X 校验的 CNOT 都在 Z 校验之前，或者反过来 | SBB Sec. II.A：“either all X-type CNOTs precede all overlapping Z-type CNOTs, or all Z-type CNOTs precede all overlapping X-type CNOTs”。SBB 没写“每个数据比特”“一轮内”，draft 这里是转述 | OK（转述。建议加 “in the sense of SBB” 或直接引原句，免得审稿人说定义被改过） |
| B8 | L73–74 | 任何 CNOT 顺序都给出 d_ext ≤ 11，所以非交错电路封顶 11（their Prop. 4） | v2 Prop. 4 (Gross circuits)：“dcirc ≤ 11”。证明枚举单个校验的 90 种残差集，“In every case we find a logical operator of weight at most 11” | OK（编号对。“every CNOT order”严格地说是“单个校验的每种顺序”，放进完整电路后 d_ext 只会更小，结论不变） |
| B9 | L74–75，SM L650 | 他们深度 8 的电路（their Fig. 12）被猜想 d_circ = 11 | v2 FIG. 12 图注：“A 3-colour-tiled left–right schedule … The schedule has depth 8 … Its extended-code distance is upper bounded by 11, and we conjecture this bound is tight”。Sec. IV C：“This circuit has depth 8 … we conjecture that it has circuit distance 11” | OK（编号对：App. H 里 FIG. 10 是 Tanner 图，FIG. 11 是残差模式，FIG. 12 是这个电路） |
| B10 | L76–77，摘要 | 引文 “whether any interleaved circuit can achieve circuit distance 12” | v2 Sec. IV C（HTML 编为 IV.3）末段：“It therefore remains an open question whether any interleaved circuit can achieve circuit distance 12.” 逐字符相同（PDF 和 HTML 一致） | OK |
| B11 | L118 | 每个单故障传播到读出时，在数据上的像要么为零，要么是扩展码的一列（SBB, Table I） | v2 TABLE I（“Types of circuit error mechanisms and their respective support on data qubits at the end of the circuit”：0 / 1 / “Resp. residual error or 1”）加上 Prop. 3 证明第 4 步（“a natural mapping from every circuit-level error mechanism to a column of the extended-code model”） | OK（编号对。可以改成 “SBB, Table I and proof of Prop. 3”，更完整） |
| B12 | L302，SM L651 | Fig. 12 是非交错电路，所以 Prop. 3 加 Cor. 1 给出 d_circ = d_ext | SBB Sec. IV B：“LRCs are non-interleaved SECs”，FIG. 12 是 left–right schedule；Theorem 1 式 (11) | OK |
| B13 | L336 | “other single-ancilla circuits whose distance is limited by Cor. 1 of SBB” | 同 B6 | OK |
| B14 | L88 | 超图乘积码的精确电路距离已知 [ManesClaes] | 2308.15520 Theorem 2：“The effective distance of the code using any stabilizer measurement order for the rows of HZ and HX is also d.” | OK |
| B15 | L89 | 最小 BB 电路由精确求解器算出精确值 [Webster2026] | 本次没读到 Sec. 5.5.3（HTML 截断，PDF 超过 10 MB）。旧笔记 `2026-10-09-paper-novelty.md` 记的是 “Sec. 5.5.3 与 Table 28：精确方法里 Gurobi 在 8 h 内只完成了 7 个 BB 电路中最小的一个” | UNVERIFIABLE（本次）。旧笔记支持这条陈述；投稿前应在浏览器里打开 HTML 的 Sec. 5.5.3 和 Table 28 复核一次，并在正文写明是哪个码、几轮、哪个基底 |
| B16 | L89–90 | 其他 qLDPC 构造有证书形式的精确值 [Liang2026, SunCai2026] | Liang 摘要：“fault-response certificate that yields rigorous lower bounds on circuit distance … the circuit distance multiplies exactly”；Sun–Cai 正文：“for d = 4, 5, 6 we prove that our circuits admit no undetectable …”，用的是整数规划认证 | OK |
| B17 | L91–93 | 同样比特数的 morphing 电路 [ShawTerhal2025, Wills2026] 作用在**另一个** [[144,12,12]] 码上，没有专用辅助比特 | Shaw–Terhal Table I 后面写道：“the end-cycle code derived from the [[288,12,18]] BB code has parameters [[144,12,12]], presenting a second ‘gross’ code”，所以对 ST 这条成立。**Wills App. C 原文是 “a new circuit for the idling gross code … this circuit is believed to have circuit distance 12, matching that of the code, and is constructed using Shaw-Terhal morphing”**，没有给出电路、多项式或比特数。“不是 gross 码本身”是本项目 E-017 的推断（end-cycle 码最小稳定子权重 ≥ 7，gross 码为 6），未经 auditor 复核，Wills 原文里也没有 | **FIX**，见下文 F1 |
| B18 | L94–95 | “Lower bounds for interleaved circuits were proposed as future work in Ref. [Nguyen2026]” | 2608.19917 v2 Conclusion 原文：“Ref. [28] associates to each interleaved circuit a non-interleaved counterpart whose circuit distance lower-bounds that of the original … these reduce the search to a single-round, non-interleaved calculation, which we leave to future work.”（[28] = SBB，[27] = Shaw–Terhal 2604.09797）。下界本身来自 SBB Theorem 1 式 (12) d′_circ ≤ d_circ；Nguyen 留作 future work 的是用这个下界筛选调度 | **FIX**，见 F2 |
| B19 | L95–96 | “Position-dependent CNOT orders are an established tool [TomitaSvore, KishonyFowler, Strikis2026]” | Kishony–Fowler：“color-dependent gate schedules”（依位置）；SBB：三色平铺（依位置）。**Tomita–Svore Sec. III B：“we propose to measure X- and Z-type stabilizers in different orders”**，这是按校验类型区分，同一类型内每个位置的顺序都一样 | **FIX**，见 F3 |
| B20 | L106–107，SM L443 | SD6 [Gidney2021honeycomb]：CNOT 后双比特去极化，reset 之后、测量之前翻转，空闲比特单比特去极化 | 2108.10457 Table 2：SD6 = CX(p), AnyClifford1(p), InitZ(p), MZ(p), Idle(p)，定义见其 Table 1 | OK（“测量前翻转”和 MZ(p) 的结果翻转对单比特 Z 测量是等价的） |
| B21 | L108 | 故障按 DEM 机制计数 [Gidney2021stim] | Stim 论文说明了按“翻转哪些 detector 和 observable”来分组错误机制（`--detector_hypergraph` 模式）；“detector error model”这个名字和文件格式出自 Stim 的软件文档，论文里没有这个词 | OK（如果审稿人较真，可以在引文旁加注 Stim 文档 / 版本号） |
| B22 | L754 | 电路用 Stim 构建和模拟 | 软件引用 | OK |

## 需要的修改（可直接替换的文本）
**F1（B17，L91–93）** 改成：
> Shaw and Terhal's morphing circuit for the $\code{288,12,18}$ code uses the same number of qubits, has no dedicated ancillas and acts, at the end of each cycle, on a $\code{144,12,12}$ code that they call "a second `gross' code"~\cite{ShawTerhal2025}; its circuit distance is reported as an upper bound ($\le12$). Ref.~\cite{Wills2026} (App.~C) reports a morphing idling circuit for the gross code that is "believed to have circuit distance 12", supported by Monte Carlo simulation; the circuit is not given.

如果正文要保留“与 gross 码不等价”的说法，它必须作为**本文自己的结论**写出来，附证据（end-cycle 码的最小稳定子权重 ≥ 7，gross 码为 6，见 E-017），并且先经 auditor 复核。不能挂在 Wills 名下。另外，L64 “No circuit for the gross code had been shown to reach d_circ = d = 12” 在 Wills 的 “believed” 面前仍然成立，但最好紧接着点明 Wills App. C 的说法，免得审稿人以为我们漏引了。

**F2（B18，L94–95）** 改成：
> SBB also show that an interleaved circuit's distance is lower-bounded by that of its non-interleaved counterpart~\cite{Strikis2026}; Ref.~\cite{Nguyen2026} proposed using this bound to screen interleaved schedules, leaving the search to future work.

（SBB 的这个下界只能给出 ≥ 11，所以和本文“固定扩展码”的路线确实不同，原句后半句可以保留。）

**F3（B19，L95–96）** 改成：
> Check-dependent CNOT orders, by check type~\cite{TomitaSvore} or by colour class~\cite{KishonyFowler,Strikis2026}, are an established tool.

## 其他建议（不改也不算错）
- Nguyen v2 的 [27] 是 Shaw–Terhal 2604.09797（“Optimising quantum error correction using morphing circuits”），其中有“每隔一轮时间反演，使整个实验的电路距离等于单轮”的结果。本文 Lemma（单轮归约 / gap）和它思路相近，建议作为相关工作引用（`2026-10-10-gross-d12-novelty.md` 已把它列为“若证明用到时间平移 / 单轮归约，至少作为相关工作”）。本次没有读 2604.09797 正文。
- SBB 的节号：PDF 是 REVTeX 字母编号（Sec. IV C、App. H 2），HTML 是 IV.3、H.2。draft 正文没有引节号，所以无需修改；SM 或回复审稿人时如果要引，建议用 PDF 的编号。

## 检索记录
- abs 页：2308.07915、2506.03094、2603.05481v2、2308.15520、2603.22532、2609.37231、2609.39522、2407.16336、2605.21898(v2)、2608.19917、1404.3747、2603.28852、2108.10457、2103.02202。
- HTML：2603.05481v2（截断在参考文献 [21]，附录没读到）、2407.16336v3（Table I 后文字）、2608.19917v2（Conclusion 与参考文献 [27] [28]）、2605.21898v2 和 2603.22532v2（都截断）。
- PDF 文字抽取：2603.05481v2（Sec. II A、IV B–C、TABLE I、App. H、FIG. 10–12）、2308.07915v2（第 5 节）、2506.03094（Table 4）、2605.21898v2（App. C、Table 5、参考文献 [ST25]）、2308.15520（Theorem 2）、2609.39522v2、2609.37231、1404.3747、2603.28852、2108.10457（Table 2）、2103.02202。2603.22532v2 的 PDF 超过抓取上限，没读到。
- Quantum 期刊页：q-2025-01-30-1618（官方 BibTeX）。

## 补核（lead，2026-10-14，浏览器读 arxiv.org/html/2603.22532v2 全文）
Webster2026 Sec. 5.5.3 原文：“Gurobi performed very well giving the lowest distance of all algorithms in 4 of the 7 members of the circuit family, though it completed within 8 hours only for the first member of the family.” → 草稿“精确求解器只算完最小的 BB 电路”**OK**，此项不再待办。
