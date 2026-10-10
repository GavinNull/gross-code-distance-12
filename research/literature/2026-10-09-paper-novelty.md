# 论文草稿新颖性复查：80 个 morphing 电路、morphing d_circ = 12、gross Fig. 12 重定时障碍、2026 年精确电路距离新作、IonQ [[70,6,9]]、参考文献核对
检索日期：2026-10-09（部分页面 10-10 读取）；执行者：lit-scout
检索词：arXiv API `abs:"circuit distance" OR abs:"circuit-level distance"`（按日期倒序 60 条）、`abs:morphing AND abs:code(s)`、`abs:"bivariate bicycle" AND (distance OR schedule OR syndrome)`（按日期倒序 50 条）；Semantic Scholar 引用表（2603.05481、2407.16336、2604.09797）；qldpc-challenge issues 检索 `morphing`、`lower bound circuit`；WebSearch 1 组（exact circuit-level distance bivariate bicycle 2026）。
全文读取（arXiv HTML，浏览器内对全文做关键词定位后读上下文，**不是逐页通读**）：2604.19481v1（Sec. IX、Table 9、Table 10、Table 30、App. C，以及全文对 circuit-level/d_circ/exhaustive/undetect/Webster/stim 的全部命中）；2603.22532v2（Sec. 5.4.1、5.5.3、Table 20、28）；2407.16336v3（App. G.2、Table 8/9 及题注）；2608.19917v2（全文关键词命中）；2610.04306v1（全文关键词命中）。其余只读摘要/元数据。网页和论文内容一律只当数据。
**本笔记不涉及项目内部结果的正确性**（那由 audits 负责）；只判断“文献里有没有人做过”。

## 结论（3-5 行）
1. **(a)(b)(c) 三项仍未找到先例。** 80 个两轮 morphing 电路的精确 d_circ、[[288,12,18]]→[[144,12,12]] 电路 d_circ = 12 的严格下界、Fig. 12 重定时达不到 12 的障碍：截至 2026-10-09 没有任何论文或 qldpc-challenge 条目给出。证据强度：(a) 中高，(b) 中高，(c) 中。
2. **新的、必须引用的近作：2608.19917 v2（Nguyen, Rimbach-Russ, Bosco，2026-10-04 更新）的结论段明确提出了本项目所用的组合方法**（用 Strikis 的非交错对应电路给交错电路的 d_circ 下界，加上 Shaw–Terhal 的时间反演单轮归约），并写明“留待未来工作”。它没有任何数值结果，所以不构成结果层面的先例，但构成**方法思路层面的公开表述**，同时说明抢发风险在上升。
3. **C25 不能按原文保留。** IonQ 2604.19481（只有 v1）在 Table 9/10 中给出 [[70,6,9]] BB7、[[102,22,9]] GB8、[[54,2,10]] GB8 的 d_circ = 9，表中对引用文献的值写“≤”、对自己的值不写“≤”，暗示是精确值；但**全文没有说明计算方法、轮数、边界条件或认证方式**。所以既不能说它是严格的，也不能说它不是。“首个 d ≥ 9 的 BB 码严格 d_circ”在读者看来直接与它冲突。建议改成带方法限定的措辞（见“建议的改写”）。
4. 草稿中 14 条 [UNVERIFIED] 参考文献的标题、作者、编号、年份全部在 arXiv abs 页面核实（表见下）；可以去掉全部 [UNVERIFIED] 标记。另有一处对 2407.16336 Table IX 题注的转述需要改准确（见 (a)）。

## 关键论文
| arXiv | 作者 · 年份 | 做了什么 | 与本项目关系 | 关键数字（附出处） |
|---|---|---|---|---|
| 2604.19481 v1 | Tripier, …, Webster, …, Delfosse（IonQ）· 2026-04-21 | walking cat 离子阱架构；三环（three-ring）码；按调度置换搜索 SEC 电路 | C25 冲突源 | Table 9：[[102,22,9]] GB、[[70,6,9]] BB、[[54,2,10]] GB 的 d_circ 列为 9、9、9（无“≤”）；同表 [[30,4,5]] ≤5、[[48,4,7]] ≤7、[[72,12,6]] ≤6、[[90,8,10]] ≤8、[[144,12,12]] ≤10 均为引用值且带“≤”。Table 10：三个码的调度置换与 d_circ = 9。Sec. IX.2：对调度置换做搜索，使 ⌈d_circ/2⌉ = ⌈d/2⌉。方法：未写（见问题 2） |
| 2603.22532 v2 | Webster, Jacob, Higgott · 2026（v2 08-14） | 码与电路的距离算法基准 | 精确电路距离工具；BB 电路规模上限的证据 | Sec. 5.5.3 与 Table 28：BB 码电路是最难的一类；精确方法里 Gurobi 只在 8 小时内完成了 7 个 BB 电路中最小的一个；Table 20 列出的 BB 电路规模是 n = 144…720 |
| 2608.19917 v2 | Nguyen, Rimbach-Russ, Bosco · 2026（v2 10-04） | 由码的构造“拆解”得到低深度交错校验电路 | 方法思路先例（无数值） | 结论段：可用 Strikis（其 Ref. [28]）的非交错对应电路给交错电路 d_circ 下界做筛选，再用 Shaw–Terhal（其 Ref. [27]）的隔轮时间反演把记忆实验 d_circ 化为单轮，“which we leave to future work” |
| 2407.16336 v3 | M. H. Shaw, B. M. Terhal · PRL 134, 090602 (2025) | morphing BB 电路 | (a)(b) 的对象 | App. G.2 Table 9 只列 (ℓ,m) = (6,6) 与 (12,6) 两组；所有 d̃_circ 均为“≤”（BP-OSD 上界）。题注原意见 (a) |
| 2604.09797 v2 | M. H. Shaw, B. M. Terhal · 2026 | morphing 一般原则、Prop. 1 | (a)(b) 的归约工具 | 见 `morphing-d12-novelty.md`；本次无新版本（仍是 v1 04-10、v2 04-20） |
| 2603.05481 v2 | A. Strikis, D. E. Browne, M. E. Beverland · 2026（v2 09-14） | LR 电路、扩展码、Prop. 4 | (c) 的出发点 | v2 日期 2026-09-14（项目旧笔记读的是 v2，一致） |
| 2606.12724 v1 | Rui Chao · 2026 | morphing 电路的 block algebra | 只认证码距离 | 见旧笔记；无新版本 |
| 2610.04306 v1 | An, Yang · 2026-10-03 | gauged 逻辑测量的四个附加条件；Lean 内精确计算 fault distance | 不构成先例 | 对象是 [[18,4,4]] BB 码上的 gauging 逻辑测量和 [[9,1,3]] Bacon–Shor，**现象学模型**（文中写明 hook 错误只作为配对处理），不是 syndrome 电路的记忆实验 d_circ |
| 2605.16523 v1 | Ehatamm, Lee, Wu, Tao · 2026 | Lean-QEC：码距离的形式化证明 | 不构成先例 | 摘要：[[90,8,10]]、[[70,6,9]] BB 的**码距离**证明，规模到 144 比特；无电路距离 |
| 2609.37231、2609.39522、2610.03429 | Liang 等；Sun–Cai；Ghosh–Boche–Tanggara | 放大 qLDPC 证书；layer code；LP 上界 | 草稿已引 | 非 BB；无新变化（2609.39522 有 v2，10-06） |

## (a) 80 个两轮 morphing 电路的精确 d_circ，包括 8 个 d_circ < d̃ 和层序依赖

**有没有人做过完全相同的事？没有。**
- 2407.16336 的全部 morphing 电路距离都是 BP-OSD 上界（正文 Table I 与 App. G.2 Table 9 都写“≤”；App. A 说明方法是上界）。没有任何电路被给出下界，也没有按 (a₂,a₃)/(b₂,b₃) 四种写法分别计算。
- 2604.09797 v2：明确说未检查 BB morphing 电路的 d_circ（旧笔记已核）。2606.12724：只认证码距离，明说不优化门序。
- 2407.16336、2604.09797 的新引用方（S2，2026-09-15 之后：2610.06036、2609.39758、2609.10666；更早的 2607.21160、2607.15044、2606.22853、2605.19298、2605.15266）按标题/摘要筛查，均不是 morphing 电路距离计算。arXiv `abs:morphing` 最新一条是 2608.25797（√T 态制备，无关）。qldpc-challenge `morphing` 检索 0 条。
- **证据强度：中高。** 限制：arXiv API 只查摘要；新引用方没有读全文。

**关于“与 Table IX 题注矛盾”的措辞（需要改准）。** 2407.16336 v3 App. G.2 Table 9 题注的意思是：对 Table 4 定义的调度，A、B 中元素的顺序“不重要”，理由是 a₁、b₁ 由同态决定，而 end-cycle 码在 a₂↔a₃、b₂↔b₃ 交换下不变（引 Corollary D.3）；并说所得距离与同态的选择无关；对 Table 8 的电路这些不成立，所以列出全部置换。要点：
1. 题注给出的理由是 **end-cycle 码**的不变性；“不重要”是对调度说的，没有单独声称电路距离不变，但读者自然会这样理解，而表中的 d̃_circ 列只给一个值。
2. Table 9 只含 (ℓ,m) = (6,6) 和 (12,6) 两组，**不含 [[108,8,10]]**。草稿 C6 的 6,6,7,7 是 [[108,8,10]] f_y 的 Table 4 电路，所以说“与 Table IX 题注矛盾”时，被反驳的是题注里关于 Table 4 调度的一般说法，而不是 Table 9 中某一行的数字。
3. 草稿第 208–210 行目前写的是 “states that the Table IV circuits are independent of the order of the A and B terms”，比原文更强。建议改写见下。

**[[72,12,8]] 的 d_circ = 6（C7）**：2407.16336 Table 9 中 (12,6) 一行 f_x Table 8 两种置换下 [[72,12,8]] 的 d̃_circ 记为 ≤ 6；f_y 的 [[72,12,7]] 记为 ≤ 7（本次在 HTML 中直接读到）。所以草稿“贡献是证明上界是紧的”这一措辞正确。

## (b) Shaw–Terhal [[288,12,18]] → [[144,12,12]] morphing 电路 d_circ = 12 的严格下界

**有没有人做过？仍然没有（对旧笔记 `morphing-d12-novelty.md` 的更新）。**
- 2026-10-08 以来新出现的相关条目：2610.10731（单次魔术态工厂，引用 2603.05481，摘要与 d_circ 无关）、2608.19917 v2（见下）、2610.04306（不相关，见表）。IBM 2605.21898 仍只有 v1/v2（v2 06-23），App. C 仍是“believed”。2604.09797 无 v3。
- **新增注意事项：2608.19917 v2 的结论段**把“Strikis 非交错对应电路给出 d_circ 下界”与“隔轮时间反演把记忆实验化为单轮 [ST26]”这两步明确组合起来，作为寻找最大 d_circ 调度的方案，并留待未来工作。这与本项目的证明流程（Prop. 1 单轮归约 + 扩展码精确 DFS）在思路上重合。它没有给出任何电路的 d_circ 数值，因此**不影响 C4 的结果新颖性**，但论文的方法部分应当引用它，以免被认为未提及公开的同类思路。
- **证据强度：中高**（同旧笔记的限制：无全文检索，无法排除未公开工作）。
- 抢发风险：由“低到中”上调为**中**。理由：一个与 morphing/Strikis 两条线都有交集的组已经公开把这条路写成下一步。

## (c) 障碍：保持 Fig. 12 每个校验的 CNOT 顺序、只重定时，达不到 d_circ = 12（在声明的电路族内）

**有没有人做过？没有。**
- 2603.05481 v2（2026-09-14）：Prop. 4 只覆盖非交错电路；交错电路能否达到 12 在原文中仍是开放问题（旧笔记 `refs-verified.md` 第 3 条、`novelty-gross11-ibm72.md`）。
- 2603.05481 的全部 S2 引用方（14 条，含 10-07 的 2610.10731）按标题/摘要筛查，无人研究 gross 码交错电路的 d_circ 上界或不可达性。2608.19917 v2 讨论交错电路构造，但无 gross 的 d_circ 结论。2609.40319 只讲深度（摘要：IBM 权重 6 BB 码的 6 层度数下界不可达，这是深度，不是距离）。
- “达到 12”的方向：唯一公开声称 12 的是 morphing（ST 上界、IBM “believed”），与 Fig. 12 重定时不是同一电路族。
- **证据强度：中。** 理由：障碍类负结果通常不会写进摘要，若有人在正文附录里做过有限族的检验，摘要检索查不到；本次也没有读引用方全文。

## (d) 2026 年计算 BB / qLDPC syndrome 电路精确电路距离的新作

| 来源 | 内容 | 是否严格 | 与草稿的关系 |
|---|---|---|---|
| 2604.19481 v1（IonQ） | [[70,6,9]] BB7、[[102,22,9]] GB8、[[54,2,10]] GB8 的 d_circ = 9 | **未说明**（见问题 2） | C20/C25 必须正面处理 |
| 2603.22532 v2（Webster 等） | 精确方法基准；BB 电路只有最小一个在 8 h 内被 Gurobi 完成 | 精确（对完成的实例） | 已在 C21 作为部分先例；可作为“BB 电路精确距离很难”的文献依据 |
| 2609.37231 v1 | 放大 qLDPC 码电路的 fault-response 证书，严格下界 | 严格 | 草稿已引（非 BB） |
| 2609.39522 v2 | layer code SEC 的电路距离证明 | 严格 | 草稿已引（非 BB） |
| 2610.03429 v1 | 检测矩阵与 LP，给电路距离**上界**（flag 电路） | 上界 | 草稿已引 |
| 2610.04306 v1 | gauged 逻辑测量的 fault distance，在 Lean 内精确计算 | 严格，但为现象学模型、[[18,4,4]] | 不构成先例；可不引 |
| 2605.16523 v1 | Lean 形式化**码距离**，含 [[70,6,9]]、[[90,8,10]] | 码距离 | 不构成先例 |
| 2608.19917 v2 | 提出单轮 + 非交错对应电路的组合方案，未执行 | 无数值 | **建议新增引用** |
| 2606.20263（Vine codes） | 摘要称用数值方法“verify circuit distances”，平面 qLDPC | 未核实是否严格（未读全文） | 非 BB；未核实 |
| 2606.02418、2610.06623（Cruz-Benito） | LLM 搜索 BB 码；MILP/精确证书 | 摘要显示是码距离（2610.06623 摘要未明说，按“CSS realizations”的上下文判断为码距离，未读全文） | 不构成先例 |
| qldpc-challenge | `morphing` 0 条；`lower bound circuit` 26 条，无一涉及电路距离的认证下界 | — | 旧笔记结论不变：电路层只收见证型上界 |

## 问题 2：IonQ 2604.19481 的 [[70,6,9]] “d_circ = 9” 是怎么得到的

**读到的事实（2604.19481 v1，arXiv 只有 v1；v2 的 abs 页返回 404）：**
1. Table 9 题注给出定义：d_circ 是 SEC 电路中造成不可检测逻辑错误所需的最少故障操作数。表中自己的三个码写 9、9、9，不带“≤”；引用他人的码全部带“≤”。这种区分**暗示**作者把 9 当作精确值。
2. Table 10 题注重复同一定义，并给出对应的调度置换；正文说“we therefore search over them”（调度置换）以保持主导阶抑制指数，且所选调度满足 ⌈d_circ/2⌉ = ⌈d/2⌉。
3. **全文没有说明 d_circ 怎么算**：对 circuit-level、d_circ、exhaustive、undetect、stim、Webster、qdist 等词的全部命中都读过，计算 d_circ 的方法、工具、轮数、边界条件（含噪/理想初态与读出）、是否双基、是否证明下界，均未出现。唯一写有“exhaustive enumeration”的地方是 App. C Table 30 题注，那针对的是**码距离** d（没有“≤”的 d 为穷举精确值，带“≤”的为 QDistRnd 上界）。另一处“exhaustive computational search”（Sec. XV，Heuristic 3）是对魔术态注入小电路的单故障枚举，与 SEC 的 d_circ 无关。
4. 间接线索：共同作者 Mark Webster 是 2603.22532（精确电路距离算法基准，含 Gurobi/SAT/MIP）的第一作者，IonQ 文献 [216] 就是该文（在 Sec. XIV.1 用于逻辑算符减重）。这让“用精确求解器算过”有可能，但**原文没有这样写**。另外 2603.22532 v2 报告 BB 电路的精确求解只完成了最小实例，[[70,6,9]] 电路（140 比特，权重 7）是否在其能力内无从判断。
5. 注意 Table 9 里 [[54,2,10]] GB8 的 d_circ = 9 < d = 10。

**判断：** “d_circ = 9”**是一个未附方法的声明**。它可能是精确计算（暗示：不带“≤”；Webster 在作者中），也可能是启发式搜索未找到更低权重（同一表里对 [[144,12,12]] 写的 ≤ 10 也来自启发式，作者对“≤”的使用说明他们在意区分，但没有给出依据）。**不能当作严格结果引用，也不能当作“非严格”而忽略。** 证据强度：事实部分高（已在原文中定位），推断部分低。

**C25 的结论：不能保留原文“first rigorous circuit distances for BB codes with d ≥ 9”。** 理由：读者会拿 IonQ 的 [[70,6,9]] = 9 反驳；我们无法证明它不严格。
另外，C20 的“first rigorous circuit distance for a BB code with d ≥ 10”也受影响：IonQ 的 [[54,2,10]] 是 GB 码（Table 30 中 (ℓ,m) = (27,1)），IonQ 自己把 GB 码视为 a = 2 三环码的特例、与 BB 同一框架（Sec. IX.2：“exactly the BB codes (and therefore also GB …)”）。如果把 GB 算作 BB，C20 也会被同样反驳；如果按 Bravyi 等 ℓ,m ≥ 2 的通常 BB 定义，C20 不受影响。建议 C20 也加一句说明。

## 问题 3：参考文献核对（arXiv abs 页面元数据，2026-10-10 读取）

| bib key | arXiv（最新版） | 标题（abs 页） | 作者（abs 页） | 年份 / 期刊 | 草稿现状 → 应改为 |
|---|---|---|---|---|---|
| Strikis2026 | 2603.05481 v2（v1 2026-03-05，v2 2026-09-14） | High-performance syndrome extraction circuits for quantum codes | Armands Strikis, Dan E. Browne, Michael E. Beverland | 2026，预印本 | 缺标题与名 → 补全，去掉 [UNVERIFIED] |
| ShawTerhal2025 | 2407.16336 v3（2025-03-26） | Lowering Connectivity Requirements For Bivariate Bicycle Codes Using Morphing Circuits | Mackenzie H. Shaw, Barbara M. Terhal | Phys. Rev. Lett. 134, 090602 (2025)，DOI 10.1103/PhysRevLett.134.090602 | 缺标题 → 补全；期刊信息正确 |
| ShawTerhal2026 | 2604.09797 v2（v1 04-10，v2 04-20） | Optimising Quantum Error Correction Using Morphing Circuits | Mackenzie H. Shaw, Barbara M. Terhal | 2026，预印本 | 缺标题 → 补全 |
| Wills2026 | 2605.21898 v2（v1 05-21，v2 06-23） | Concatenating Algebraic Codes over High-Rate Quantum LDPC Codes | Adam Wills, Michael E. Beverland, Lev S. Bishop, Jay M. Gambetta, Patrick Rall, Vikesh Siddhu, Andrew W. Cross | 2026，预印本 | 缺标题与名 → 补全；作者顺序与草稿一致 |
| Webster2026 | 2603.22532 v2（v1 03-23，v2 08-14） | Distance-Finding Algorithms for Quantum Codes and Circuits | Mark Webster, Abraham Jacob, Oscar Higgott | 2026，预印本 | 缺标题 → 补全 |
| WangMueller | 2408.10001 v7（v1 2024-08-19，最新 2026-03-10） | Coprime Bivariate Bicycle Codes and Their Layouts on Cold Atoms | Ming Wang, Frank Mueller | Quantum 10, 2009 (2026)，DOI 10.22331/q-2026-02-23-2009 | 原注“只来自搜索 URL” → 已核实；补期刊 |
| ManesClaes | 2308.15520 v2 | Distance-preserving stabilizer measurements in hypergraph product codes | Argyris Giannisis Manes, Jahan Claes | Quantum 9, 1618 (2025)，DOI 10.22331/q-2025-01-30-1618 | 缺标题与卷 → 补全 |
| Liang2026 | 2609.37231 v1（09-29） | Ultra-high-distance quantum memories from amplified qLDPC codes | Zijian Liang, Boren Gu, Yu-An Chen, Jens Eisert, Zongyuan Wang | 2026，预印本 | 缺标题与名 → 补全；作者与草稿一致 |
| SunCai2026 | 2609.39522 v2（v1 09-30，v2 10-06） | Layer codes as quantum memories: syndrome extraction, thresholds and idle robustness | Zhu Sun, Zhenyu Cai | 2026，预印本 | 缺标题与名 → 补全 |
| TomitaSvore | 1404.3747 v3 | Low-distance Surface Codes under Realistic Quantum Noise | Yu Tomita, Krysta M. Svore | Phys. Rev. A 90, 062320 (2014)，DOI 10.1103/PhysRevA.90.062320 | 缺标题 → 补全；卷页正确 |
| KishonyFowler | 2603.28852 v1（03-30） | Color code off-the-hook: avoiding hook errors with a single auxiliary per plaquette | Gilad Kishony, Austin Fowler | 2026，预印本 | 缺标题与名 → 补全 |
| Ghosh2026 | 2610.03429 v1（10-02） | Fault tolerance of quantum circuits with tensor networks and symplectic geometry | Soham Ghosh, Holger Boche, Andrew Tanggara | 2026，预印本 | 缺标题与名 → 补全 |
| Tripier2026 | 2604.19481 v1（04-21，唯一版本） | Fault-Tolerant Quantum Computing with Trapped Ions: The Walking Cat Architecture | Felix Tripier, Woo Chang Chung, Jacob Young, Safwan Alam, Bryce Bjork, Aharon Brodutch, Finn Lasse Buessen, Nolan J. Coble, Thomas Dellaert, Dmitri Maslov, Martin Roetteler, Edwin Tham, Mark Webster, Min Ye, John Gamble, Andrii Maksymov, J. P. Marceaux, Nicolas Delfosse | 2026，预印本 | 缺标题与作者 → 补全（可写 “F. Tripier *et al.*”） |
| Chao2026 | 2606.12724 v1（06-10） | Block algebra for morphing circuits | Rui Chao | 2026，预印本 | 缺标题 → 补全 |
| （新增建议）Nguyen2026 | 2608.19917 v2（v2 10-04） | Disassembling qLDPC codes for depth-optimal parity-check circuits | Minh T. P. Nguyen, Maximilian Rimbach-Russ, Stefano Bosco | 2026，预印本 | 新增 |

草稿已标为已核实的条目复核：2308.07915（Bravyi, Cross, Gambetta, Maslov, Rall, Yoder；Nature 627, 778–782 (2024)，DOI 10.1038/s41586-024-07107-7）与 2506.03094（Yoder, Schoute, Rall, Pritchett, Gambetta, Cross, Carroll, Beverland；2025-06-03）元数据一致。2103.02202、2108.10457 本次未重查（`refs-verified.md`、`noise-models.md` 已核）。

## 新颖性判断
- (a) 80 个电路精确 d_circ：**没有人做过**。最接近：2407.16336 Table I/Table 9（同一批电路的 BP-OSD 上界）；2604.09797（归约工具，明说未查 BB d_circ）；2606.12724（码距离）。差别：首次给出精确值并发现 8 个低于 end-cycle 距离、以及 Table 4 电路的 d_circ 随项序变化。
- (b) d_circ = 12：**没有人做过**。最接近：2407.16336（上界 12）、2605.21898 App. C（believed 12）、2608.19917 v2（提出同类方法、未执行）。
- (c) 重定时障碍：**没有人做过**。最接近：2603.05481 Prop. 4（非交错不可达 12），交错情形原文开放。
- (d) BB 码电路的精确 d_circ：除本项目外，只有 2603.22532 的公开数据（BB72，单基，R = 6，已在 C21 承认）和 IonQ 2604.19481 未附方法的 d_circ = 9（d = 9/10 的 BB/GB 码）。其余 2026 年严格结果都不是 BB。
- “声称”与“复现”：IonQ 的 9 只是声称，没有独立复现，也没有方法；本项目没有复算它（可以作为可选的旁证实验，见建议 3）。

## 建议的改写（只列建议，不改草稿）
1. **C25（draft.tex 第 326–328 行）** 现文：“To our knowledge these are the first rigorous circuit distances for BB codes with $d\ge9$ (but see the caveat …)”。建议改为：
   “To our knowledge these are the first circuit distances for BB codes with $d\ge10$ that come with a stated, reproducible proof; Ref.~\cite{Tripier2026} reports $\dcirc=9$ for $\code{70,6,9}$ and $\code{102,22,9}$ BB/GB codes and for a $\code{54,2,10}$ GB code without describing how these values were obtained.”
   如果不想保留“first”，替代方案：“Exact circuit distances for BB codes with $d\ge9$ are scarce: Ref.~\cite{Tripier2026} lists $\dcirc=9$ for three $d=9$–$10$ BB/GB codes without stating the method, and Ref.~\cite{Webster2026} reports that exact solvers completed only the smallest BB circuit in its benchmark.”
2. **C20（第 307–308 行）** “the first rigorous circuit distance for a BB code with $d\ge10$” 后加限定：“(here BB means $\ell,m\ge2$; Ref.~\cite{Tripier2026} lists $\dcirc=9$, method unstated, for a $\code{54,2,10}$ generalized-bicycle code)”。或者统一采用第 1 条的“with a stated, reproducible proof”措辞。
3. **SM 新颖性小节第 727–730 行（C25 条）**：把“the method is not stated in the parts read”改为“the method is not stated anywhere in the paper (v1, the only version; Tables 9–10 and Sec. IX.2 define $\dcirc$ and list the schedules, and $\le$ is used only for values quoted from other works)”，并去掉 [UNVERIFIED]。
4. **Table IX 题注的转述（第 208–211 行）** 现文：“The caption of Table~IX in Ref.~\cite{ShawTerhal2025} states that the Table~IV circuits are independent of the order of the $A$ and $B$ terms; this holds for the end-cycle codes, but not for the circuit distance”。建议改为：
   “The caption of Table~IX of Ref.~\cite{ShawTerhal2025} states that the ordering of the elements of $A$ and $B$ is not important for the Table~IV schedules, on the grounds that the end-cycle codes are invariant under $a_2\leftrightarrow a_3$, $b_2\leftrightarrow b_3$. The end-cycle codes are indeed invariant, but the circuit distance is not.”
   摘要/引言中如有“contradicting”字样，建议改为“refines”或“shows that … does not extend to the circuit distance”。
5. **SM 新颖性小节最后一条（第 731–735 行）** “The 80-circuit study (C5–C9) and the gross obstruction (C13–C17) have not had a dedicated literature check [UNVERIFIED]” → 改为 “A dedicated search (2026-10-09) found no prior exact circuit distance for any morphing circuit and no prior result on retimings of the Fig.~12 circuit; Ref.~\cite{Nguyen2026} proposes combining the non-interleaved lower bound of Ref.~\cite{Strikis2026} with the single-round reduction of Ref.~\cite{ShawTerhal2026} as future work.”
6. **方法部分新增引用 2608.19917 v2**，放在介绍 Prop. 1 单轮归约与 Strikis 下界组合的地方，一句话说明对方提出了该组合但未执行。
7. **参考文献**：按上表补全标题、全名、期刊，删除全部 `\unverified`；2408.10001 应写 Quantum 10, 2009 (2026)。

## 对本项目的建议
1. C25 和 C20 在任何公开版本里都要按上面第 1–2 条改写；这是本次唯一会影响结论措辞的发现。
2. 是否向 IonQ（Webster 或 Delfosse）询问 [[70,6,9]] d_circ = 9 的计算方法，需要 PI 决定（对外发信）。
3. 可选的旁证实验（交给 lead 决定）：用本项目的扩展码 + DFS 流程独立计算 IonQ Table 10 给出的 [[70,6,9]] 调度的 d_circ。若得 9，可以在论文里写“独立确认”，C25 改为“与 Ref. [Tripier] 一致并给出证明”；若低于 9，则是又一个上界被否定的例子。Table 10 给出了调度置换，Table 30 给出了 A、B 多项式（Q70 一行：(ℓ,m) = (7,5)，A = y² + x² + x³ + x⁴，B = y + x + x³；这是从 HTML 文本抽取读出的，单项式边界有歧义，使用前须对照 PDF 核对），但三环电路的初始对齐与运输细节需要按 Sec. IX.2 和 Algorithm 1 重建，本笔记没有核对这些细节是否足以唯一确定电路。
4. 抢发风险上调为中（2608.19917 v2）：如果 PI 打算公开，建议不要再拖太久。
5. 下次复查：2608.19917 是否出 v3 或后续论文；2604.19481 是否出 v2（可能补充方法）；Shaw/Terhal 的新作。

## 检索记录与未覆盖
- 读取：2604.19481v1 HTML（关键词全文定位，读 Sec. IX、Table 9、10、30 与 App. C 题注）；2603.22532v2 HTML（Sec. 5.4.1、5.5.3、Table 20、28）；2407.16336v3 HTML（App. G.2、Table 9 与题注）；2608.19917v2 HTML（关键词命中）；2610.04306v1 HTML（关键词命中）；arXiv abs 页元数据 16 篇。
- arXiv API 只检索标题/摘要，不是全文；Semantic Scholar 引用表有索引滞后；qldpc-challenge 只做了 issues 检索；新引用方大多只读了标题或摘要。
- 2606.20263（Vine codes）的“verifies circuit distances”未读全文，严格与否未核实（非 BB，不影响结论）。
- 未向任何作者求证。
