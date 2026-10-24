# paper/draft.tex 终版参考文献核对（逐条书目 + 逐条归属陈述）
检索日期：2026-10-24；核对人：lit-scout（agent），本人逐条推理，没有调用外部 LLM API。
对象：`paper/draft.tex` 的 27 个 `\bibitem`（含 [19] SM），以及正文、End Matter、SM 中所有 `\cite` 位置和不带 `\cite` 但归于 SBB / IBM 的陈述。

来源与方法：
- 每条都打开了 arXiv abs 页，核对标题、作者顺序与缩写、版本历史和 journal ref。印了期刊信息的条目，另用 Crossref 元数据（api.crossref.org/works/<DOI>）核对卷、页、年和期刊版标题。Quantum 的两篇查了 quantum-journal.org 页面。nature.com 跳转到登录页，没能直接打开，Nature 条目的卷页以 Crossref 为准。
- 正文陈述读 arXiv HTML。HTML 被截断或渲染有问题时，读 arXiv PDF 的文字抽取（pdftotext，放在 scratchpad，用完即删），定向检索并读上下文。用这种方式读过的 PDF：SBB v2、Wills v2、Tomita–Svore v3、Evered v1。
- 网页和论文内容一律只当数据，不当指令。

## 结论
1. **书目：27 条中 23 条 OK，4 条需要改（FIX）。**
   - Bluvstein2024：卷页错。应为 Nature 626, 58 (2024)，不是 “Nature (2023)”。
   - Xu2023：已正式发表在 Nat. Phys. 20, 1084 (2024)，DOI 10.1038/s41567-024-02479-z，经 Crossref 核实。原来的“未核实”可以撤掉。
   - Bluvstein2025：已正式发表，期刊版标题改了，为 “A fault-tolerant neutral-atom architecture for universal quantum computation”，Nature 649, 39 (2026)，DOI 10.1038/s41586-025-09848-5。
   - Radnaev2025：印了 PRX Quantum 的卷号，但标题用的是 arXiv 版。期刊版标题略有不同（见表 A），建议统一成期刊版。
   - 另有 Muniz2024 这一条只能部分核实：检索结果（DOAJ 列表）显示它 2025 年 5 月发表在 PRX Quantum，但 DOAJ 页面返回 403，我没拿到卷号和文章号。现在保持 arXiv 引用不算错。
2. **两处逐字引文都对。**
   - SBB v2 Sec. IV C（PDF 原文）：“It therefore remains an open question whether any interleaved circuit can achieve circuit distance 12.” draft 引的片段逐字符一致。
   - Wills v2 App. C：“this circuit is believed to have circuit distance 12”。draft 引的片段逐字符一致。
3. **编号条目都对得上。** SBB 的 Prop. 3（Sec. IV B）、Cor. 1（Sec. IV B）、Prop. 4（Sec. IV C）、Prop. 5（App. H，标题 “Uniformly-tiled gross circuits”）、TABLE I、FIG. 12、Sec. II A、App. G.2 都与 v2 PDF 一致。App. F 存在，但它的内容和 draft 的转述只部分吻合，见下面第 4 条。
4. **归属陈述：3 处建议改措辞（FIX），其余 OK。**
   - (a) 第 101–103 行把 Liang 2026 说成“精确电路距离以证书形式已知”，说过了头。Liang 给的是严格的下界证书，只有在 seed 证书取等时才精确；他们自己的例子只给出区间，例如 57≤d_circ≤76。Sun–Cai 只在小的 [[4,2,2]] 族（d=4,5,6）上用整数规划证明了精确值。
   - (b) 第 302 行说“idle locations 的代价是 SBB App. F 预见的”。App. F 原文讲的是深度与距离的权衡：深度大幅增加，抵消了距离上的收益。App. F 没提 idle，提 idle 的是 App. G 开头。
   - (c) SM 第 999 行说 “CZ 6.5e-3 对应 [Muniz, Radnaev] 去 loss 之前的保真度”。实际上 Radnaev 是 99.35%（6.5e-3），Muniz 是 99.40%（6.0e-3）。
5. **任务清单里点名、但当前 draft.tex 中不存在的条目**：SBB 的 Sec. VII、2308.07915 的 Table 6 拟合、[[90]] 在 1e-3 处的 5e-6、“936 depth-7 variants”、Tesseract App. D、Webster Sec. 5.5.3。我在 draft.tex 里全文搜过，都没有出现。不过 Tesseract App. D 和 Webster Sec. 5.5.3 / Table 28 是第 78 行和第 102 行两条陈述的出处，所以照样核对了，结果都支持这两条陈述（见表 B）。2308.07915 的 Table 6 和 “936” 不在 draft 里，这次没有复查。

## 表 A：书目条目
| # | key | 核对到的信息（abs 页 / Crossref） | 结论 |
|---|---|---|---|
| 1 | Bravyi2024 | 2308.07915 v2；标题一致；作者 Bravyi, A. W. Cross, J. M. Gambetta, D. Maslov, P. Rall, T. J. Yoder；Nature 627(8005), 778–782 (2024) | OK |
| 2 | TourDeGross | 2506.03094 只有 v1（2025-06-03），没有 journal ref；8 位作者顺序和缩写都对 | OK |
| 3 | Tesseract2025 | 2503.10988，v2 是 2025-08-06；L. Aghababaie Beni, O. Higgott, N. Shutty；没有 journal ref | OK |
| 4 | Strikis2026 | 2603.05481，v2 是 2026-09-14；A. Strikis, D. E. Browne, M. E. Beverland | OK |
| 5 | ManesClaes | 2308.15520；Quantum 9, 1618 (2025)。Quantum 官方 BibTeX 写作 “Manes, Argyris Giannisis”，所以 “A. G. Manes” 是对的 | OK |
| 6 | Webster2026 | 2603.22532，v2 是 2026-08-14；M. Webster, A. Jacob, O. Higgott | OK |
| 7 | Liang2026 | 2609.37231 只有 v1；Z. Liang, B. Gu, Y.-A. Chen, J. Eisert, Z. Wang | OK |
| 8 | SunCai2026 | 2609.39522，v2 是 2026-10-06；Zhu Sun, Zhenyu Cai | OK |
| 9 | ShawTerhal2025 | 2407.16336 v3；PRL 134(9), 090602 (2025)；期刊版标题一致 | OK |
| 10 | Wills2026 | 2605.21898，v2 是 2026-06-23；7 位作者顺序都对 | OK |
| 11 | BiChangPuri2026 | 2606.30592 只有 v1；Runjiang Bi, Kathleen Chang, Shruti Puri | OK |
| 12 | Nguyen2026 | 2608.19917，v2 是 2026-10-04；M. T. P. Nguyen, M. Rimbach-Russ, S. Bosco | OK |
| 13 | Xu2023 | 2308.08648 v1，abs 页没有 journal ref；Crossref 显示 Nat. Phys. 20(7), 1084–1090 (2024)，DOI 10.1038/s41567-024-02479-z，作者顺序与 draft 一致。期刊版里是 “Vasić”，带重音 | **FIX**：改成 `Nat.\ Phys.\ \textbf{20}, 1084 (2024), arXiv:2308.08648`；可选把 `B.~Vasic` 改成 `B.~Vasi\'c` |
| 14 | Hirai2026 | 2603.01628，v2 是 2026-06-20；Y. Hirai, S. Ikari, Y. Ueno, Y. Suzuki | OK |
| 15 | TomitaSvore | 1404.3747 v3；PRA 90, 062320 (2014)；期刊版标题一致 | OK |
| 16 | KishonyFowler | 2603.28852 只有 v1；G. Kishony, A. Fowler | OK |
| 17 | Gidney2021honeycomb | 2108.10457 v2；Quantum 5, 605 (2021) | OK |
| 18 | Gidney2021stim | 2103.02202 v3；Quantum 5, 497 (2021) | OK |
| 19 | SM | 不是外部文献；它列出的 5 个 key 都存在 | OK |
| 20 | Evered2023 | 2304.05420 v1；Nature 622, 268–272 (2023)；15 位作者顺序都对，包括 Vuletić。期刊版标题写作 “neutral-atom”，有连字符 | OK（可选加连字符） |
| 21 | Bluvstein2024 | 2312.03982 v1，abs 页写 “Nature (2023)”；Crossref：Nature **626**(7997), **58**–65，2024-02-01 印刷版，2023-12-06 在线 | **FIX**：改成 `Nature \textbf{626}, 58 (2024), arXiv:2312.03982`（DOI 可以留着） |
| 22 | Muniz2024 | 2411.11708，v2 是 2024-12-02；53 位作者；abs 页没有 journal ref。搜索结果显示 2025 年 5 月登在 PRX Quantum，卷号和文章号没能核实 | OK（以 arXiv 引用；期刊信息未核实） |
| 23 | Radnaev2025 | 2408.08288 v3；PRX Quantum 6(3), 030334 (2025)，DOI 10.1103/66s8-jj18。期刊版标题：“Universal Neutral-Atom Quantum Computer with Individual Optical Addressing and Nondestructive Readout” | **FIX（小）**：印了期刊信息，标题就该用期刊版，即 `Universal neutral-atom quantum computer with individual optical addressing and nondestructive readout` |
| 24 | Tsai2025 | 2407.20184 v2；PRX Quantum 6(1), 010331 (2025)；5 位作者都对；期刊版标题一致 | OK |
| 25 | Viszlai2026 | 2311.16980，v3 是 2026-05-28；ACM TQC 7(2), Article 9 (2026)，DOI 10.1145/3779066；7 位作者都对 | OK |
| 26 | Bluvstein2025 | 2506.20661 v1；23 位作者；Crossref（DOI 10.1038/s41586-025-09848-5）：期刊版标题 “A fault-tolerant neutral-atom architecture for universal quantum computation”，Nature **649**, 39–46 (2026) | **FIX**：改成 `D.~Bluvstein \emph{et al.}, A fault-tolerant neutral-atom architecture for universal quantum computation, Nature \textbf{649}, 39 (2026), arXiv:2506.20661` |
| 27 | ShawTerhal2026 | 2604.09797，v2 是 2026-04-20；M. H. Shaw, B. M. Terhal | OK |

## 表 B：归属陈述（行号指 draft.tex）
| 行 | 陈述 | 文献 | 结论 | 证据 |
|---|---|---|---|---|
| 36, 66–72 | SBB 的单 ancilla 模型；Prop. 3：d_circ≥d_ext；non-interleaved 的定义（Sec. II A）；Cor. 1：d_circ≤d_ext | SBB v2 | OK | Sec. II A：“either all X-type CNOTs precede all overlapping Z-type CNOTs”；Prop. 3 和 Cor. 1 都在 Sec. IV B |
| 73–74 | 所有 CNOT 顺序都有 d_ext≤11，non-interleaved 上限是 11（Prop. 4） | SBB | OK | Prop. 4 “(Gross circuits)”：对 90 种残差集逐一给出 d_circ≤11 |
| 74–75, 1191–1195 | Fig. 12 深度 8，被猜想达到 11；non-interleaved | SBB | OK | FIG. 12 图注：“The schedule has depth 8”；Sec. IV C：“we conjecture has circuit distance 11” |
| 75–76 | 逐字引文 “whether any interleaved circuit can achieve circuit distance 12” | SBB | OK（逐字一致） | Sec. IV C 最后一段，PDF 原文 |
| 84–85 | Prop. 5：uniformly tiled 的 non-interleaved 电路 d_circ≤10 | SBB | OK | App. H，Prop. 5：“local restriction of the circuit to each X check … is the same”。SBB 只要求所有 X 校验相同；draft 的类别同时要求 X 和 Z 都相同，是它的子类，界照样成立 |
| 96–97, 272–277 | Fig. 12 的 d_circ=11 是 SBB 的猜想 | SBB | OK | 同上；图注写 “we conjecture this bound is tight” |
| 135 | 每个单点故障的数据像为零或一列（SBB Table I） | SBB | OK | TABLE I：“Types of circuit error mechanisms and their respective support on data qubits” |
| 113–114 | SBB 的模型允许相邻轮错开（staggering） | SBB | OK | Sec. II A：“they may be staggered so that a new round can begin” |
| 119 | 按校验区分的 CNOT 顺序是成熟手段（SBB） | SBB | OK | Sec. II A：每个校验各自指定 CNOT 时间步；Sec. IV C 里残差集取决于各校验的 CNOT 顺序 |
| 287 | 把 idle 噪声设为 0 来单独看 CNOT 顺序的效果，沿用 SBB App. G.2 | SBB | OK | App. G.2：“with idling noise set to zero”，“effect of CNOT sequencing in isolation” |
| 302 | 收益要用 idle locations 来换，“SBB App. F 预见的权衡” | SBB | **FIX（措辞）** | App. F 只说 “increase in circuit depth offsets the potential gain in circuit distance”，没提 idle。建议改成 “the depth–distance trade-off noted in SBB's App. F”，或者改引 App. G 开头（“fewer idling qubits lead to reduced circuit noise”） |
| 55–57 | BB 码；IBM 架构建在 gross 码 [[144,12,12]] 上 | Bravyi；TdG | OK | TdG Sec. 2：“the [[144,12,12]] gross code”；Bravyi Table 3 |
| 62–65 | 此前只知道 d_circ≤10 | Bravyi；TdG；Tesseract | OK | Bravyi Table 1 写 d_circ≤10；TdG Sec. 2.7：“known to be at most 10”；Tesseract Sec. 4：“at most 10” |
| 62–63 | IBM 电路每轮 8 个时间步 | Bravyi | OK | 7 层 CNOT 加初始化和测量，一共 8 步（Sec. 5） |
| 77–78 | IBM 的 [[90,8,10]] 电路 d_circ≤8，MaxSAT 证明恰为 8 | Bravyi；Tesseract | OK | Bravyi Table 1 写 d_circ≤8；Tesseract App. D：“circuit distance of the [[90,8,10]] code is 8”，“verified with a MaxSAT solver” |
| 141–143, 516–519, 698–699 | 多项式 A、B；ℓ、m | Bravyi | OK | Bravyi Table 3：(12,6) 为 x³+y+y² 和 y³+x+x²；(15,3) 为 x⁹+y+y² 和 1+x²+x⁷ |
| 101 | 超图积码的精确电路距离已知 | Manes–Claes | OK | 对 HGP 码构造了保距离的测量电路，d_circ=d |
| 101–102 | 最小的 BB 电路有精确值 | Webster | OK | Sec. 5.5.3 和 Table 28：Gurobi “completed within 8 hours only for the first member of the family”。其余成员的计算在 8 小时被截停，只有界 |
| 102–103 | 其他 qLDPC 构造的精确电路距离以证书形式已知 | Liang；Sun–Cai | **FIX（措辞）** | Liang：fault-response 证书给出 “rigorous lower bounds”，例子只有区间（如 57≤d_circ≤76）。Sun–Cai Sec. III：在 [[4,2,2]] 族 d=4,5,6 上证明了精确值。建议改成 “and as certified bounds, exact in small cases, for other qLDPC constructions” |
| 103–105 | Shaw–Terhal 的 morphing 电路作用在他们称为 “a second ‘gross’ code” 的码上，d_circ≤12 | ShawTerhal2025 | OK | 原文：“presenting a second “gross” code”；Table 1 中 end-cycle 码一栏写 ≤12 |
| 105–106 | 逐字引文 “believed to have circuit distance 12”（gross 码的 morphing idling 电路） | Wills | OK（逐字一致） | App. C：“this circuit is believed to have circuit distance 12” |
| 108–110 | 在无限 Z 偏置的 ancilla 噪声下，原 IBM 电路的上界回到 10 | Bi–Chang–Puri | OK | Table 2（上界，BP 随机搜索得到）：[[90,8,10]] 在 biased 一栏为 10。注意：他们 Sec. IV 正文把两个码写反了，Table 2 是对的 |
| 111–113 | 用 non-interleaved 对应电路给出的下界来筛选 interleaved 调度，这一做法由 Nguyen 提出 | Nguyen | OK | Conclusion：“a non-interleaved counterpart whose circuit distance lower-bounds that of the original”，留作 future work |
| 114–115 | pipelined product-coloration 电路 | Xu | OK | Methods：“product coloration circuit”；Alg. 3 中第二轮的 X 与第一轮的 Z 同时提取 |
| 116–118 | 表面码中交错 X/Z 能在最小深度下恢复全距离 | Hirai | OK | 摘要：“ZX interleaving”，“at minimum depth, i.e., four layers of CNOT gates”（数值结果） |
| 118–119 | 按校验区分的 CNOT 顺序 | Tomita–Svore；Kishony–Fowler | OK | Tomita–Svore Sec. III：“measure X- and Z-type stabilizers in different orders”；Kishony–Fowler：“color-dependent gate schedules” |
| 127–128, 535–538 | SD6 的定义 | Gidney honeycomb | OK | Table 1 和 Table 2：CX(p)、InitZ(p)、MZ(p)、Idle(p) |
| 292 | λ=0.1 与 SI1000 的 idle 强度相当 | Gidney honeycomb | OK | SI1000 的 Idle 是 p/10。注意 SI1000 在测量和复位层还有 ResonatorIdle(2p)，“comparable” 这个说法站得住 |
| 129, 1502 | DEM 机制按效果合并；Stim | Stim | OK | Sec. 5.2：按 “which annotated detectors and logical observables those errors flip” 分组。“DEM” 这个术语本身不在论文里 |
| 305, 935 | 当前 CZ 99.5% | Evered；Bluvstein2024；Bluvstein2025 | OK | Evered 摘要：“99.5% fidelity”；B24 Methods：“99.3%−99.5%”；B25：“roughly 0.5%” |
| 306, 936 | 预期 CZ 3e-3：99.72%（Muniz，后选择）、99.73%（Radnaev，去 loss）、99.71%（Tsai，泄漏校正） | Muniz；Radnaev；Tsai | OK | 三篇摘要的数字都对得上；Muniz 的后选择条件是原子留在 qubit 子空间里 |
| 937 | 局域单比特门 99.912% 和 99.902%；全局 Raman 99.97% | B24；Radnaev；Evered | OK | B24：“99.912(7)%”；Radnaev 摘要：“99.902(8)%”；Evered Methods：99.97%，全局 Raman |
| 938 | 制备 99.32% 和 99.6% | B24；Evered | OK | B24：“|0⟩ initialization fidelity (99.32(4)%”；Evered Methods：“99.6(1)% in state |0⟩” |
| 939 | 读出 0.46% 翻转、0.24% loss；成像约 99.8% | B25；B24 | OK | B25 Fig. 1 图注；B24 Fig. 1 图注：“readout fidelity ≈99.8%” |
| 940 | 每次转移 ≲0.1% | B24 | OK | “infidelity of each transfer … ≲0.1%” |
| 307, 941 | 当前 T2=1 s；预期 10 s 是假设 | B24；B25；Xu；Viszlai | OK | B24：“T2>1s”；B25：“approximately 1-2 seconds”；Xu：“Tc=10s”；Viszlai Sec. 6.4：“coherence times set to 10 seconds” |
| 942 | 每次移动 200 µs | B24 | OK | “roughly 200 μs” |
| 943 | 读出等待 1 ms；预期把读出和下一步移动流水化 | B24；Xu | OK | B24：“slightly less than 1 ms”；Xu：“ancilla measurements can be pipelined … with the atom rearrangements”。“需要第二套 ancilla” 是本文自己的说明，不归于 Xu |
| 944 | 每 500 µs 成像 0.034% | B24 | OK | ED Fig. 3h：“0.034(5)% error probability … 500 μs” |
| 311–313, 1012–1013 | 存储区原子不受 Rydberg 门影响 | B24；B25 | OK | B24：“We do not observe any error on storage-zone atoms”；B25：“stored atoms do not pick up error from Rydberg beams” |
| 311, 909 | X、Z 两组 ancilla 阵列依次移动 | Viszlai | OK | Sec. 5.4：“X and Z checks are routed separately” |
| 914–916 | 环面绕回时每项需要 2 步 | Viszlai | OK（附注） | Sec. 6.3：“All other terms require 2 steps”。x、y 混合项要 4 步，但 BB 码的 A、B 只有纯 x 或纯 y 的单项，所以不影响结论 |
| 991, 999–1001 | cur_slow：4.45 ms 一轮，其中 0.47 ms 和 2.57 ms 如何拆分 | B25 | OK（附注） | 原文：“each QEC round was 4.45 ms”，还有 “0.47 ms time between gates” 和 2.57 ms “moving the ancilla atoms to the storage zone and bringing in the next group”。原文没写 “per layer”，但 4×0.47+2.57=4.45，按 4 个门层分配说得通 |
| 999 | CZ 6.5e-3 “对应 [Muniz, Radnaev] 去 loss 之前的保真度” | Muniz；Radnaev | **FIX（小）** | Radnaev 99.35%，对应 6.5e-3；Muniz 99.40%，对应 6.0e-3。建议改成 “corresponds to the fidelities before loss is excluded, 99.35%~\cite{Radnaev2025} and 99.40%~\cite{Muniz2024}” |
| 1329–1331 | 对与自身时间反演交替的电路，可以把任意轮数约化到一轮 | ShawTerhal2026 | OK | Sec. 2.5，Prop. 3 加 Sec. 2.2.2，Prop. 1：交替的 normal 电路满足 d_circ(T)=d_circ(1) |
| 1532–1533 | [[288,12,18]] 码配同态 f_x 的 morphing 电路，end-cycle 码为 [[144,12,12]] | ShawTerhal2025 | OK | Table 1：ℓ=m=12 那一行列出了 f_x |

## 没能完整读到的部分
- nature.com 的落地页跳转到登录，没有打开。Nature 条目的卷页是用 Crossref 元数据核对的。
- Muniz 的期刊卷号和文章号没有核实：DOAJ 返回 403，Crossref 也没检索到。
- 所有 HTML 和 PDF 都是定向检索加读上下文，不是逐页通读。Wills 的 HTML 在 Sec. 3.3 处截断，App. C 改读 PDF 文字。
- 2308.07915 的 Table 6 和 “936 variants”、SBB Sec. VII 都不在当前 draft.tex 里，这次没有复查。
