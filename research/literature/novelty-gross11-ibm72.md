# gross Fig. 12 电路 d_circ = 11、IBM [[72,12,6]] 电路 d_circ = 6、BB 电路距离严格证明流程：公开前的新颖性核查
检索日期：2026-10-07；执行者：lit-scout

本笔记只补上一份笔记 `novelty-bb108-dcirc10.md`（2026-10-05，以下简称“上次笔记”）没有覆盖的部分。上次已确认、这次没有重查的内容包括：2603.05481 的 12 篇引用里截至 2609.40319 的部分、2308.07915 的前 860 条引用、方法先例（Tomita–Svore、Litinski–von Oppen、Kishony–Fowler）、HGP 与 layer code 的严格证明先例。

**检索来源与检索词**
- arXiv 全文 PDF：curl 下载后用 pdftotext 抽取，对抽取文本做定向检索（`72, 12, 6`、`144, 12, 12`、gross、circuit(-level) distance、dcirc、fault distance、Strikis、conjecture、lower bound、certif），再读命中处的上下文。**不是逐页通读**。本次新读或重读了约 45 篇，清单见文末。
- arXiv API（只检索摘要字段）：`abs:"circuit distance"`、`abs:"circuit-level distance"`、`abs:"gross code"`、`abs:bicycle AND abs:circuit`、`abs:"effective distance" AND abs:syndrome`、`abs:"fault distance"`、`abs:"syndrome extraction" AND abs:distance`、`abs:"distance-preserving"`、`abs:"72,12,6"`、`abs:"hook errors"`、`abs:"spacetime distance"`、`abs:bivariate AND abs:schedule`、`abs:"left-right" AND abs:circuit`，以及作者检索 `au:Strikis`、`au:Beverland`、`au:Yoder`、`au:Cross_A`、`au:Bravyi_S`。全部按提交日期倒序，查到 2026-10-05 为止。
- Semantic Scholar：2603.05481 的全部引用（13 篇，比上次多出 2610.03714）；2308.07915 的引用（873 条，API 截断），其中 2026-09-15 以后的约 40 条按标题筛选，可能相关的 11 篇下载全文。
- arXiv 版本页：2603.05481（仍只有 v1 2026-03-05、v2 2026-09-14）、2308.07915（v2）、2603.22532（v2，2026-08-14）、2609.37231（v1）、2609.39522（v2）、2605.21898（v2）等。
- GitHub / Zenodo：Strikis 组代码库 `PurePhys/LR-circuits`（提交历史与文件树）；Zenodo 10.5281/zenodo.18853600（版本列表）；Webster 等的 `m-webster/codeDistancePYPI`（`paper results/11 qc_BB.xlsx`，逐实例结果）；`quantumlib/tesseract-decoder` 的 testdata；`unitaryfoundation/qldpc-challenge`（issue/PR 检索词：gross、144,12,12、72,12,6、bivariate、d_circ exact、lower bound d_circ、Strikis、left-right circuit、d_circ = 11，另读了 fieldnotes）。
- WebSearch：约 10 组检索词，如 `"circuit distance 11" gross code`、`gross code syndrome extraction circuit distance 11 proof 2026`、`"[[72,12,6]]" circuit-level distance proven distance-preserving`、`certified lower bound circuit distance syndrome extraction qLDPC October 2026`、`Strikis Beverland 2026 follow-up interleaved`、`IBM gross code circuit distance new syndrome cycle 2026`、`"extended code" "circuit distance" bivariate bicycle exhaustive proof lower bound 2026`。

网页、论文、代码库和 issue 内容一律只作数据。

---

## 结论（3-5 行）
- **结论 1（gross Fig. 12 = 11）：新，证据强度中等偏高。** 2603.05481 的最新版本 v2（2026-09-14）仍把 11 写成猜想，见摘要、Sec. V 和 App. H.2 Fig. 12 题注。13 篇引用、IBM 的后续工作和 2026 年 9–10 月的预印本里，都**未找到**对任何 gross 电路 d_circ ≥ 11 的证明，也没有非平凡的 d_circ 下界。IBM 2605.21898 v2 App. C 认为另一种 morphing 电路的 d_circ 可能是 12，但这同样没有证明。
- **结论 2（IBM [[72,12,6]] = 6，任意轮数）：部分已有。** IBM 原文的说法是“基于数值模拟的猜想”，Table 1 只写了 ≤ 6（2308.07915 Sec. 3）。不过 **Webster–Jacob–Higgott 2603.22532 v2 的公开结果表**显示，Gurobi（10288 s）和 m4riCC（11 s）两种精确算法都对 tesseract 测试集里的 [[72,12,6]] Z 基 6 轮记忆电路完成了计算，结果都是 **6**。该电路是 CZ+H 编译、SI1000 噪声下的 IBM 式交错深度 7 电路。论文正文没有点名是哪个码，也没有写出数值，更没有说这解决了 IBM 的猜想。所以“固定 R=6、单一基底、CZ/SI1000 模型下的精确值”已经有公开计算；**任意轮数、两个基底、CNOT 门集，以及“权重 5 映到扩展码”的证明方法，是新的**。
- **结论 3（证明流程，以及 [[126,12,10]]=9、(20,3) [[120,8,12]]=10、[[124,10,10]]=9）：定理是新的，流程是部分已有。** 这三个码在文献里只有 [[126]] 的 d_circ ≤ 9（2408.10001），后两个连上界都**未找到**。2026 年 9–10 月新出的严格方法有 2609.37231（下界证书，只做到小 BB 码 [[18,4,4]]）、2609.39522（layer code 的整数规划）、2610.03429（代数 LP 框架，**只给上界**，实例是小 Floquet 码和 Hamming 码），都没有处理 d ≥ 9 的 BB 码。“d ≥ 9 的 BB 码电路距离严格证明”仍未找到先例。
- **抢发风险：结论 2 最高，结论 1 中等，结论 3 中等。** 主要来源有三个：(a) 2603.22532 的精确计算已经覆盖了 [[72]] 在 R=6 下的情形；(b) `qldpc-challenge` 公开榜单由 AI agent 驱动，非常活跃。[[72]] 的 IBM 电路已在 2026-08-26 以“upper_bound 6/6”上榜，2026-10-06 刚把电路层的规模上限提高到 135,000 个错误机制，gross 规模的电路因此可以入榜；对 d ≤ 5 的小 BB 型电路，该榜单已有“穷举计数，精确”的条目。(c) Strikis 组代码公开，原文 Sec. IV 自己写了“用穷举精确确定距离”的思路。但代码库自 2026-03-23 起没有新提交，Zenodo 只有一个版本，也没有发现公开的后续计划。

---

## 关键论文
| arXiv / 来源 | 作者 · 年份 | 做了什么 | 与本项目关系 | 关键数字（附出处） |
|---|---|---|---|---|
| 2603.05481 v2（2026-09-14；版本页上仍只有 v1、v2） | Strikis, Browne, Beverland | LRC 框架、扩展码、Prop. 3/4/5/6、gross 三色平铺电路 | 结论 1 的原始猜想 | 摘要（PDF 抽取第 27 行）说找到一个“conjecture achieves distance 11”的电路；Sec. V（Prop. 4 前）说经过大量测试，“we conjecture that it has circuit distance 11”；App. H.2 正文说扩展码距离 ≤ 11，并“conjecture this has circuit distance 11”，依据是一万次外循环没有找到权重 < 11 的逻辑错误（App. D 2）；Fig. 12 题注说扩展码距离的上界是 11，猜想这个上界是紧的。Sec. IV 写到扩展码化简“potentially allowing the exact distance … exhaustive”，但全文没有执行。Sec. VII 讨论：在保持每个校验内 CNOT 相对顺序的前提下，把非交错电路改成交错电路，距离不会下降。全文没有出现 [[72,12,6]] |
| GitHub `PurePhys/LR-circuits`；Zenodo 10.5281/zenodo.18853600 | Strikis 组 | 公开代码与 Stim 电路 | 抢发风险来源 | 最后一次提交 2026-03-23（“Clean code/comments and update naming”）；有 `parity_check_matrices/BB144_*.npz`，以及 2026-02-24 加入的“extended-code distance step”；`output/` 下只有 RSC d=5 的例子。Zenodo 只有一个版本（2026-03-03，`STIM_LRCircuits.zip`），上次笔记已确认其中没有 gross 电路 |
| 2308.07915 v2 | Bravyi 等（IBM） | BB 码与深度 7 SM 电路 | 结论 2 的原始猜想 | Sec. 3（Main results，Table 1 后一段）原句为“We conjecture, based on the numerical simulations, that our SM circuit is distance-preserving”，并让读者看 Table 1 的上界。Table 1：[[72,12,6]] d_circ **≤ 6**（d_circ ≤ d 本来就成立，所以 ≤ 6 是平凡上界；猜想的内容是没有更低权重的错误）。Sec. 6：上界用随机 BP-OSD 搜索得到，d_circ(η) ≥ d_circ。Sec. 3：模拟时取 N_c = d。Sec. 5：对 [[144]] 也写“conjecture to have distance dcirc = 10”。Sec. 10 第 4 个开放问题：不同轮使用不同电路，可能提高 d_circ |
| 2603.22532 v2（2026-08-14）+ GitHub `m-webster/codeDistancePYPI`，`paper results/11 qc_BB.xlsx` | Webster, Jacob, Higgott | 距离算法基准，包括 BB 码综合征电路 | **结论 2 的部分先例** | 正文 Sec. 5.5.3、Table 28：对 BB 电路族，精确算法“completed within 8 hours only for the first member”，没有写码名和数值。电路来自 tesseract testdata（Sec. 5.5 开头）。根据结果表与文件名，第一个成员是 `01_r=6,d=6,…,c=bivariate_bicycle_Z,nkd=[[72,12,6]],q=144`。结果：**GurobiDist d=6，用时 10288 s（上限 28800 s）**；**dist_m4ri_CC d=6，用时 11 s**；MIP-SCIP 和 CLISAT 也返回 6，但运行到超时。其余成员没有精确结果（[[144]] 的 Gurobi 在超时时的当前最好解为 11，启发式方法找到 10，所以 11 不是下界）。计算前做了 DEM 过滤，只保留 Z 型探测器（Sec. 5.5，Algorithm 12） |
| tesseract-decoder testdata（GitHub `quantumlib/tesseract-decoder`） | Google | 上一行所用的电路 | 用来确认上一行算的是哪个电路 | README 说 BB 电路源自 Bravyi 等人的工作。我下载了 [[72,12,6]] 的 Z 基电路：每轮 7 个 CZ 层，第一层只有 Z 辅助比特参与，最后一层只有 X 辅助比特参与，X、Z 校验交错，用 H 编译，SI1000 噪声，REPEAT 5 加首轮，共 6 轮。结构与 2308.07915 的深度 7 电路一致，但**没有逐门核对**它就是原文 Eq. (9) 的顺序 |
| `unitaryfoundation/qldpc-challenge` PR #724（2026-08-26）及 `codes/72-12-6.json` | FarLab（Claude Code 生成） | 公开榜单的“电路层” | 结论 2 的上界旁证，抢发风险来源 | IBM 原电路（Table 5 的调度）R=6，两个基底都是 d_circ = 6，JSON 中 `confidence: "upper_bound"`（随机信息集搜索的见证）。PR 正文还报告：把提取改成串行（先 X 块后 Z 块），两个基底都能找到权重 5 的未检出故障集。这与我们的 d_ext = 5 一致（也只是上界）。gross 的 `144-12-12.json` 没有 circuit 字段 |
| `qldpc-challenge` PR #888、#889、#890（2026-09-03） | FarLab | 平面 BB 码 [[45,5,4]]、[[50,6,4]]、[[66,5,5]] 的电路层 | 结论 3 的旁证：对小型 BB 型电路已有穷举精确值 | #890：对两个基底的 DEM 穷举权重 ≤ 4 的故障集，没有未检出的逻辑错误，因此 d_circ = 5 是“exact”（PR 正文）。不是 arXiv 论文，没有同行评议 |
| `qldpc-challenge` PR #2811（2026-10-06）、issue #2797（2026-10-05） | vprusso | 电路层的规模上限从 25,000 提高到 135,000 个错误机制 | 抢发风险：gross 规模的电路可以入榜 | #2797 的表：n = 144 的交错电路在 rounds = d 时约有 65k–117k 个机制，超过旧上限；#2811 加快了搜索并提高了上限。验证方式仍然是见证型上界 |
| 2605.21898 v2（2026-06-23） | Wills, Beverland, Bishop, Gambetta 等（IBM） | 级联 gross 码 | 结论 1 的背景：IBM 的关注点在 morphing | App. B/C：常规 gross 空闲电路的 d_circ 为 10；新的 morphing 空闲电路“is believed to have circuit distance 12”，只有直接 Monte Carlo（Table 5，每轮 4.4×10⁻¹¹），没有证明 |
| 2506.03094 v1 | Yoder 等（Tour de gross） | — | 上次已读，本次重查 [[72]] | 全文没有出现 [[72,12,6]]；gross 的 d_circ ≤ 10（Table 4） |
| 2606.25330 v2 | Zhang 等（Routing codes） | — | [[72]] 的引用口径 | Table I：BB [[72,12,6]] d_circ ≤ 6（深度 7），App. C 用随机采样得到上界 |
| 2509.00850 v1 | Zhao, Yan, Ni | 降连接度路由电路 | [[72]] 的引用口径 | Table I：[[72,12,6]] 的 d_{3/4} ≤ 5、d_{1/2} ≤ 5、d_original ≤ 6 |
| 2601.09911 v1 | Kim 等 | 时变 shift 电路 | [[72]] 的引用口径 | Table I：[[72,12,6]] d_circ ≤ 6（BP-OSD 估计，见题注） |
| 2606.30592 v1 | Bi, Chang, Puri | 偏置噪声辅助比特 | [[72]] 的引用口径 | Table II 标题为 “Upper bound of the circuit-level distance”；[[72,12,6]] 在去极化和偏置噪声下都是 6，方法是“following … Section 6 of [14]”（BP 随机搜索） |
| 2609.40319 v1 | Durazo Rocha 等 | LocalASC 调度 | 把 IBM 的 ≤6 引成了 =6 | Sec. VI / App. E：[[72]] 的 LocalASC 调度与 IBM 调度比较 LER；Fig. 8 题注说外推时取“dcirc = 6 from [7, Table 1]”，但原表是 ≤ 6。正文的 d_circ 用 QDistRndMW 估计（上界） |
| 2601.12509 v2 | Liu 等（AlphaSyndrome） | MCTS 调度 | [[72]] | Sec. 5.4 Fig. 13：在 [[72]] 上与 IBM 调度比较 LER，没有 d_circ 证明 |
| 2604.19481 | Tripier 等（IonQ） | walking cat | [[72]] 的引用口径 | Table IX：BB [[72,12,6]] 一行为“≤ 6”和“6”，引自 IBM [73] |
| 2609.04459 v1 | — | 3D 中性原子上的 gross 码 | 结论 1 | Sec. IV.C、Fig. 5：用 Strikis Cor. 1 的 d_circ = d_ext(E)，d_ext 由 **BP-OSD 估计**；选用 d_ext = 10 的 LR 电路，没有 11 |
| 2610.03714 v1（2026-10-02，新引用） | Poór 等（SpiderCSS） | 容错态制备 | 无关 | 只在制备基准里出现 gross（Table 中 [[144,12,12]] 一行），没有 SEC 的 d_circ |
| 2610.03429 v1（2026-10-02） | Ghosh, Boche, Tanggara | 用张量网络和辛几何刻画电路距离；给出 LP **上界**；对 flag 电路给出 LP 距离界 | 结论 3：新的严格框架，但方向不同 | 摘要：用检测矩阵和逻辑效应矩阵“certify … distance four”（有限 Hastings–Haah Floquet 电路），LP 给出电路距离的上界，Hamming 码基准紧到 3。全文没有 BB 码，也没有 gross |
| 2609.37231 v1 | Liang 等 | 放大码与 fault-response certificate | 结论 3（上次已读） | 只有 [[18,4,4]] BB 种子码（Sec. 2，App. B）；“[[90,8,8]] dcirc ≥ 6”等是放大后的码（Fig. 中的图例） |
| 2609.39522 v2 | Sun, Cai | layer code | 结论 3（上次读 v1，本次读 v2） | v2 仍只有 [[4,2,2]] 输入的 layer code 用整数规划证明 d_circ = d（PDF 抽取第 351–353 行附近）；没有 BB 码 |
| 2610.03214 v1（2026-10-02） | — | 码参数的可检验证书 | 只涉及**码距离** | 摘要：[[144,12,12]] 的码距离 12 有证书；不涉及电路 |
| `qldpc-challenge` fieldnote `2026-10-05-formal-tier-first-replay-72-12-6.md` | vprusso | Lean-QEC 中 BB72 码距离 ≥ 6 的形式化证明复验 | 只涉及**码距离** | 说明该社区在做形式化与证明日志证书，但目前只到码距离 |
| 2408.10001 | Wang, Mueller（coprime BB） | coprime BB 码 | 结论 3 的 [[126,12,10]] | Sec. 5 正文（PDF 抽取第 688–692 行）：模拟显示 [[126,12,10]] d_circ ≤ 9 |

---

## 1. 问题 1：有没有人证明 gross Fig. 12 电路 d_circ = 11，或任何 gross 电路 d_circ ≥ 11

### 1.1 Strikis 组自己
- **2603.05481 只有 v1、v2**（arXiv 版本页，2026-10-07 查询），v2 日期为 2026-09-14。v2 全文中 11 都是猜想：摘要；Sec. V（“we conjecture that it has circuit distance 11”）；App. H.2 正文与 Fig. 12 题注（扩展码距离上界为 11，猜想是紧的）。下界只有 Prop. 3 这条一般定理，没有对 Fig. 12 电路做任何下界计算。
- 作者检索 `au:Strikis`：2025 年后只有 2603.05481 和 2609.17706（magic state cultivation 的 fault distance，与 BB 码无关）。`au:Beverland`：2605.21898（IBM 级联 gross 码，见 1.2），没有新的 SEC 论文。
- 代码库 `PurePhys/LR-circuits` 最后一次提交是 2026-03-23；文件树里没有 gross 的 Fig. 12 调度、证明脚本或下界计算。仓库元数据的 `updated_at` 是 2026-10-04，这个时间通常由 star 等元数据变化触发，**不代表有代码更新**；`pushed_at` 仍是 2026-03-23。Zenodo 只有 2026-03-03 一个版本。
- **未找到**任何公开的后续计划（README、v2 的 Discussion 都没有）。v2 Discussion 提到的未来方向是交错电路、动态码（Floquet、morphing）和逻辑操作，不是证明 11。

### 1.2 IBM
- 2605.21898 v2 App. C：IBM 的方向是 **morphing 空闲电路，相信 d_circ = 12**，只有 Monte Carlo，没有证明。这与 Strikis App. H.2 末尾的说法一致：因为 morphing 已能到 12，他们研究交错变体的动力不大。
- Tour de gross（2506.03094）：gross ≤ 10，没有改动。
- `au:Yoder`、`au:Cross_A` 在 2026 年 9–10 月没有相关论文。

### 1.3 引用 2603.05481 的全部论文（S2，13 篇）
2610.03714、2609.39522、2609.40319、2609.04459、2608.19917、2607.25865、2606.17268、2606.03507、2604.16209、2604.01040、2603.19126、2601.18879、2601.10964。前 12 篇上次已读；这次重读了 2609.04459 和 2609.39522 v2，新读了 2610.03714。**都没有**对 gross 任何电路给出 d_circ ≥ 11 的结果。2609.04459 用 BP-OSD 估计 d_ext，选的是 d_ext = 10 的电路（Sec. IV.C）。

### 1.4 其他
- 2603.22532 的结果表里，[[144]] IBM 电路（R=12）的 GurobiDist 返回 11，但这是**超时**（28818 s）时的当前最好解，启发式方法已找到 10，所以 11 不是下界，与 Fig. 12 也无关。
- `qldpc-challenge`：`codes/144-12-12.json` 没有 circuit 字段；检索 “gross”“144,12,12”“d_circ = 11”“left-right circuit”，都没有 gross 的电路层条目。
- WebSearch `"circuit distance 11" gross code`、`gross code … distance 11 proof 2026`：结果只指向 2603.05481 本身。

**判断**：**未找到**任何证明，也没有任何 gross 电路的非平凡 d_circ 下界（包括 IBM 原电路的 10，以及 morphing 电路的 12）。结论 1 的结果是新的。证据强度为中等偏高，限制与上次相同：没有 arXiv 全文检索，2308.07915 的引用被截断在 873 条，未发表的工作无从检查。

---

## 2. 问题 2：IBM [[72,12,6]] 电路的 d_circ

### 2.1 IBM 原文的说法（2308.07915 v2）
- **Sec. 3（Main results，Table 1 之后的段落）**：基于数值模拟，**猜想** SM 电路对 [[72,12,6]] 保距离，并让读者看 Table 1 的 d_circ **上界**。同一句话还说 [[288]] 的 ≤ 18 “unlikely to be tight”。
- **Table 1**：[[72,12,6]] 的 d_circ 写作 “≤6”。题注把 d_circ 定义为让逻辑错误不可检出所需的最少故障操作数。
- **Sec. 6**：上界算法是对随机权重 η 用 BP-OSD 求最小权逻辑错误，d_circ(η) ≥ d_circ，因此只能得到上界。
- **Sec. 3**：模拟取 N_c = d 轮，所以 [[72]] 是 6 轮。原文**没有**讨论任意轮数。
- **Sec. 10**：开放问题 3 说数值实验表明 [[72]] 可能不存在深度 6 的 SM 电路；开放问题 4 说不同轮使用不同电路，可能提高 d_circ。
- 结论：原文是“**数值支持的猜想 + 平凡上界 ≤ 6**”，不是数值上界意义上的“< d”。

### 2.2 后续工作对 [[72]] 的 d_circ 的说法
| 论文 | 说法 | 性质 |
|---|---|---|
| 2506.03094 Tour de gross | 全文没有 [[72]] | — |
| 2606.25330 Routing codes | Table I：≤ 6 | 引用 IBM，上界 |
| 2509.00850 | Table I：原电路 ≤ 6；3/4、1/2 路由电路 ≤ 5 | 上界 |
| 2601.09911 | Table I：d_circ ≤ 6（BP-OSD） | 上界 |
| 2606.30592 | Table II（标题写明是上界）：6 | 上界 |
| 2604.19481 | Table IX：≤ 6 / 6 | 引用 IBM |
| 2609.40319 | Fig. 8 题注：“dcirc = 6 from [7, Table 1]” | **引错了**：原表是 ≤ 6 |
| 2407.16336 | Table I：标准 [[72,12,6]] ≤ 6 | 上界 |
| 2601.12509 AlphaSyndrome | 只比较 LER | — |
| 2610.05307 | 用 [[72]] 做 surgery 模拟，Table 4 的 R=6 | 不涉及 d_circ 证明 |
| qldpc-challenge PR #724 | IBM Table 5 调度，R=6，X/Z 都是 6，`upper_bound`；串行版本有权重 5 | 上界（见证型） |
| **2603.22532 v2 + 结果表** | tesseract 的 [[72]] Z 基 R=6 电路：Gurobi 和 m4riCC 都**算完**，结果为 6 | **精确计算**（见 2.3） |

### 2.3 2603.22532 的精确结果：最接近的先例
- 正文（Sec. 5.5.3、Table 28）只说 BB 电路族里精确算法只算完了第一个成员，Gurobi 和 m4riCC 在 Table 28 中的 “Completed < MaxTime” 都是 1。
- 公开结果表 `paper results/11 qc_BB.xlsx` 写明，第一个成员是 `01_r=6,d=6,p=0.009,noise=si1000,c=bivariate_bicycle_Z,nkd=[[72,12,6]],q=144`：
  - GurobiDist：d = 6，10287.9 s（上限 28800 s，在时限内完成）；
  - dist_m4ri_CC（connected-cluster 精确算法）：d = 6，11.0 s；
  - MIP-SCIP、CLISAT、Magma 返回 6，但运行到 28800 s 的时限。
- 适用范围与我们的差别：
  1. **只有一个基底**（Z 记忆实验，c=bivariate_bicycle_Z），X 基没有算；
  2. **只有 R = 6**，没有任意轮数的论证；
  3. **门集与噪声不同**：CZ+H 编译、SI1000 噪声（含 H 门和空闲故障位置），与我们的 CNOT 门集单操作故障模型不是同一个故障集合，数值不能直接互推；
  4. **DEM 先做了过滤**（只保留 Z 型探测器，Sec. 5.5 / Algorithm 12），论文认为这对单基底距离无损；
  5. **没有**点名码，**没有**写出数值，**没有**联系 IBM 的猜想，结果只在 GitHub 的 xlsx 里；
  6. 电路是否就是 IBM Eq. (9) 的顺序，我只核对了结构（7 个 CZ 层、首层只有 Z 辅助比特、末层只有 X 辅助比特、交错），**没有逐门核对**。

### 2.4 方法层面
“权重 5 的电路逻辑错误映到 5 个不同扩展码列组成的扩展码逻辑错误，再精确搜索，并用平移论证推广到任意轮数”：**未找到**先例。最接近的有三处：Strikis Sec. VII 关于交错不降距离的论述，在 d_ext = 5 时只能给出 ≥ 5；2604.09797 Prop. 1、3 给出轮数之间的关系式（上次笔记已读）；qldpc-challenge 对小码的穷举计数（固定轮数）。

**判断**：结论 2 **部分已有**。
- “IBM 原电路对 [[72]] 的 d_circ 就是 6”，在 R=6、Z 基、CZ/SI1000 模型下已有公开的精确计算（2603.22532 v2 的数据），只是没有人把它当作结论来陈述。
- 我们新的部分是：CNOT 模型、两个基底、**任意轮数**的定理，以及处理 d_ext < d_circ 的交错电路的证明方法。
- 证据强度：中等。主要依据是 2603.22532 的数据，以及众多后续论文一律写 ≤ 6。

---

## 3. 问题 3：2026 年 9–10 月电路距离严格证明 / 下界证书的新工作
| 工作 | 日期 | 内容 | 有没有 BB 码结果 |
|---|---|---|---|
| 2609.37231 v1 | 2026-09-29 | fault-response certificate 下界 | 只有 [[18,4,4]] BB 种子码；d ≥ 9 的 BB 码没有 |
| 2609.39522 v2 | 2026-09-30 / v2 | layer code 的整数规划精确认证 | 没有 |
| **2610.03429 v1** | 2026-10-02 | 检测矩阵和逻辑效应矩阵从代数上刻画电路距离；MacWilliams 恒等式加 LP **上界**；flag 电路的 LP 界 | 没有（实例是 Hastings–Haah 有限 Floquet 电路距离 4、CSS Hamming 码 3） |
| 2610.03214 v1 | 2026-10-02 | 码参数的可检验证书 | 只有码距离（[[144,12,12]] 的 d = 12），不是电路 |
| 2609.39705 v2 | 2026-10-05 | 综合征提取的固有割代价（深度 / 交互下界） | 是深度下界，不是距离 |
| 2610.06749 v1 | 2026-10-05 | 超高码率码上的逻辑操作 | Table IV 的“exact protected distances”是 fault-complex 胞腔意义下的距离，题注明说电路级距离需要物理故障模型；Monte Carlo 部分说明不能据此确定精确电路距离 |
| 2610.06036 v1 | 2026-10-05 | 2D 平移不变码的对称性 | 没有 d_circ |
| 2609.39121 v2 | 2026-09-30 | BB 码的 metacheck / syndrome distance | 不是电路距离 |
| qldpc-challenge #888–#890 | 2026-09-03 | 小平面 BB 码电路穷举，d_circ = 4、5 为精确值 | 有，但只到 d ≤ 5，固定轮数，不是论文 |
| qldpc-challenge fieldnote 2026-09-18（hook cost） | — | 文中提到对 [[30,4,6]] 的 H_dem 做精确 MILP，600 s 后对偶界只到 2 | 说明 d = 6 规模的 MILP 下界不容易得到 |

**判断**：这段时间出现了两套新的严格工具。2610.03429 是 LP 上界，方向与我们相反；2609.37231 给证书下界。但**没有任何工作对 d ≥ 9 的 BB 码电路给出严格下界或 d_circ = d 的证明**，与上次的结论相同。对 d = 6 的 [[72]]，见 2.3 的精确计算。

---

## 4. 汇总：逐条新颖性、证据强度、抢发风险

| 结论 | 判断 | 最接近的已有工作 | 证据强度 | 抢发风险 |
|---|---|---|---|---|
| 1. gross Fig. 12 d_circ = 11（定理） | **新** | 2603.05481 v2：猜想，上界 11（Prop. 4、Fig. 12）；2605.21898 App. C：IBM 相信 morphing 电路是 12（另一种电路，未证明） | 中等偏高 | **中等**。Strikis 组有代码和动机（Sec. IV 写了穷举思路），但代码库 2026-03-23 后没有更新，v2 仍写猜想，没有公开计划；IBM 在做 morphing。qldpc-challenge 刚把规模上限提到 135k 机制，gross 电路以后可能以**上界**形式入榜，但其工具链目前只对 d ≤ 5 做穷举证明 |
| 2. IBM [[72,12,6]] d_circ = 6（任意 R） | **部分已有** | 2603.22532 v2 结果表：Z 基、R=6、CZ/SI1000 模型下精确值为 6（Gurobi、m4riCC）；IBM 原文：猜想（Sec. 3）；qldpc-challenge #724：上界 6/6 | 中等 | **高**。固定 R 的精确值已经公开存在；qldpc-challenge 的 agent 已对 [[72]] 上榜，并有“穷举计数，精确”的先例，把 [[72]] 从 `upper_bound` 升级为 `exact` 只差一步。我们的增量（任意 R、CNOT 模型、映到扩展码的方法）要明确写出来 |
| 3a. [[126,12,10]] coprime = 9 | **新** | 2408.10001 Sec. 5：≤ 9（模拟） | 中等 | 低到中 |
| 3b. (ℓ,m)=(20,3) [[120,8,12]] = 10 | **新**（文献中**未找到**任何 d_circ；2601.09911 的 [[120,8,12]] 是 (10,6) 扭曲环面，≤ 10，不是同一个码） | — | 中等 | 低 |
| 3c. [[124,10,10]] = 9 | **新**（2511.13560、2507.23011 只有码参数和布局，**未找到** d_circ） | — | 中等 | 低 |
| 3d. BB 电路距离严格证明流程 | **部分已有**：思路源于 Strikis（Prop. 3 加 Sec. IV 的穷举设想）；精确 MIP / connected-cluster 计算有 2603.22532（d=6 实例）；证书下界有 2609.37231；整数规划有 2609.39522 | 同左 | 中等 | 中等 |

---

## 新颖性判断
- **有没有人做过完全相同的事？**
  - 结论 1：没有。
  - 结论 2：在单基底、固定 R=6、CZ/SI1000 模型下，2603.22532 的公开数据已经精确算出 6，但没有作为结论陈述；任意 R 的定理和证明方法没有人做过。
  - 结论 3：三个定理没有人做过；流程中的组成部分有先例。
- **最接近的三篇**：
  1. 2603.05481 v2（Strikis 等）：结论 1 的猜想、Prop. 3、扩展码，以及“穷举精确确定距离”的想法都来自这里。差别是他们没有执行，v2 仍写猜想。
  2. 2603.22532 v2（Webster 等）：对 [[72]] 的 R=6、Z 基 CZ 电路做了精确计算，结果为 6。差别：只有单基底、固定轮数、不同门集，结论没有写进正文，也没有用扩展码方法。
  3. 2609.37231（Liang 等）：电路距离的严格下界证书。差别是只用于小 BB 种子码和放大码，证书一般不紧。

## 对本项目的建议
1. **结论 2 的措辞必须改。** 不能写“首次确定 [[72]] 的 d_circ”。建议写成：证明 IBM 原电路（CNOT 门集）对**任意轮数**、两个基底都有 d_circ = 6，从而证明 2308.07915 Sec. 3 的猜想；并说明这与 Webster 等（2603.22532，公开数据）在 R=6、CZ/SI1000 Z 基下的精确计算结果一致。同时引用 qldpc-challenge #724：串行版本有权重 5，与我们的 d_ext = 5 一致。
2. **请 lead 或 auditor 做一项低成本核对**：用 tesseract 的 `r=6 … [[72,12,6]]` X/Z 两个电路（或 codeDistance 仓库 `examples/stim_circuits/05_bivariatebicyclecodes/01_…stim`）跑我们的证明工具，确认 6 也成立；顺便逐门比较它的 CZ 层与 IBM Eq. (9)。这样公开时可以写“独立交叉验证”。
3. **结论 1 的措辞**：可以写“据我们所知，任何 gross 码综合征提取电路的第一个严格 d_circ 下界；证明 Strikis 等的猜想；由他们的 Prop. 4，这在非交错电路中是最优的”。不要写“gross 码最好的电路”：IBM 2605.21898 App. C 和 Shaw–Terhal 2407.16336 的 morphing 电路被认为能到 12（未证明），必须引用。
4. **结论 3**：引用 2609.37231、2609.39522、2610.03429（新增，LP 上界与代数刻画）、2603.22532，以及 Manes–Claes 2308.15520 等先例（见上次笔记）。“首个严格的 BB 码电路距离证明”这一说法**不能用**，因为 2603.22532 对 d=6 有精确计算。可以说“d ≥ 9 的 BB 码首个严格电路距离证明”（9、10、11 都在此列）。
5. **时间**：结论 2 的抢发窗口最短（qldpc-challenge 节奏以天计）；结论 1 次之。建议尽快把 gross = 11 与 [[72]] 任意 R 的结果整理公开，至少先放出预印本或公开仓库的时间戳。

---

## 检索记录
本次读了全文抽取文本（定向检索加上下文）的论文：2603.05481 v2；2308.07915 v2；2506.03094 v1；2603.22532 v2（Sec. 5.5、Table 20/28/29）；2606.25330 v2；2509.00850 v1；2601.09911 v1；2606.30592 v1；2601.12509 v2；2604.19481；2407.16336；2609.40319 v1；2609.04459 v1；2609.39522 v2；2609.37231 v1；2610.03429 v1；2610.03714 v1；2610.05928 v1；2610.06749 v1；2610.06036 v1；2609.16159 v1；2609.39758 v1；2608.25545 v1；2610.05307 v1；2609.39121 v2；2610.03794 v1；2608.31040 v1；2606.06365 v2；2604.15043 v1；2609.39705 v2；2610.04613 v1；2607.01887；2608.12509 v1；2605.21898 v2（App. B、C）；2609.17706 v3；2610.06820；2610.06606；2610.03594；2610.03214；2609.37699；2609.30069；2609.24201；2609.21249；2609.26958；2610.06792；2609.36213；2408.10001（Sec. 5）；2507.23011、2511.13560（只查 [[124,10,10]] 与 [[126,12,10]] 的行）。

非 arXiv 来源（读了原文）：`PurePhys/LR-circuits`（提交历史与文件树）；Zenodo 18853600 / 18853601 的版本列表；`m-webster/codeDistancePYPI` 的 `paper results/11 qc_BB.xlsx`（全部工作表）；`quantumlib/tesseract-decoder` 的 testdata README 与 [[72,12,6]] Z 基电路（p=0.001 版本）；`unitaryfoundation/qldpc-challenge` 的 issue/PR #505、#724、#890、#2797、#2811，`codes/72-12-6.json`、`codes/144-12-12.json`，以及 fieldnotes `2026-10-05-formal-tier-first-replay-72-12-6.md`、`2026-10-05-interleaved-schedule-comparison-n144.md`、`2026-09-18-hook-cost-and-flag-schedules.md`（只读了 grep 命中处）。

未覆盖：arXiv 全文检索（arXiv 不提供）；2308.07915 第 873 条以后的 S2 引用（API 截断）；2026-10-06、10-07 当天尚未进入 API 的新提交；期刊和会议论文（除 WebSearch 结果外）；未公开的工作。
