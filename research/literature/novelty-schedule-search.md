# 用搜索/优化/ML/LLM 设计 syndrome 提取调度：2023 年至今的新颖性检索
检索日期：2026-10-02；检索词（WebSearch + arXiv abs/html/pdf 读取）：syndrome extraction schedule optimization bivariate bicycle circuit-level distance；LLM evolutionary search QEC syndrome extraction AlphaEvolve FunSearch；coloration circuits hook errors；reinforcement learning syndrome measurement scheduling qLDPC；simulated annealing / genetic algorithm syndrome extraction gross code；gross code circuit distance 12 等。
局限：检索靠搜索引擎 + arXiv 页面，不是 arXiv 全库检索，可能漏文；摘要由工具转述，凡"未读全文"的均已标注。2026 年论文的编号和日期按 arXiv abs 页所示，我无法独立复核。

## 结论（3-5 行）
- **H-001 基本已被人做过（在 d_circ 指标上）**：Strikis–Browne–Beverland（arXiv:2603.05481，2026-03）给出一个 gross code 的单辅助比特、深度 8（与 IBM 原电路摊销后相同）的电路，猜想 d_circ=11，对比 IBM 的 ≤10；并证明任何非交错电路 d_circ≤11（Prop. 4）。该电路是"猜想"，只有 BP-OSD 上界搜索支持，未见独立复现。
- **H-002（LLM 进化 vs 同算力模拟退火，用于调度）没有找到完全相同的工作**。最近的是：AlphaSyndrome（MCTS，2601.12509）、PropHunt（MaxSAT，2601.17580）、FastSched（RL，2609.12020）、OmniQEC（LLM 总控，2607.25865，但调度用边着色）、qcode-discovery（LLM 进化 vs 随机/GA，但搜的是码不是调度，2606.02418）。这些里没有一篇对调度问题做"LLM 进化 vs SA"对照，也没有 AlphaEvolve/FunSearch 直接用于调度的报告（未找到）。
- 剩余空间：H-001 在 d_circ 上基本被占，剩下的是（a）gross code 在电路噪声下的逻辑错误率最优（d_circ 之外），（b）交错/多辅助比特/非单辅助比特/跨 cycle 交替电路，（c）独立复现与验证 Strikis 电路。H-002 的空间较完整，但"LLM 优于 SA"需要在一个未被 d_circ=11 饱和的指标上做。
- 深度地板：ASC（2603.21499）声称对 IBM 原文的所有 BB 码求得最小深度 7，并"certifies that no depth-6 circuit exists"；所以"同深度或更低深度"对单辅助比特调度，深度 <7 不可行（论文声称，未独立复现）。

## 关键论文
| arXiv | 作者 · 年份 | 做了什么 | 与本项目关系 | 关键数字（附出处） |
|---|---|---|---|---|
| 2603.05481 | Strikis, Browne, Beverland · 2026-03（v2 2026-09-14） | left-right circuits 框架 + residual error/extended-code distance 代理指标；对 gross code 证明非交错电路 d_circ≤11，并给出 d_circ=11 的猜想电路 | **H-001 的最近邻（最重要）**：已给出 gross code 超过 IBM d_circ 的调度 | 摘要："no non-interleaving SEC can achieve circuit distance 12 for the gross code ... explicit circuit that we conjecture achieves distance 11"。Prop. 4（Sec. IV.3）：d_circ≤11，证明里 90 种单检查 CNOT 顺序中 45 种已推出 ≤10。Prop. 5（App. H）：均匀平铺的非交错电路 ≤10。Prop. 6（App. H）：三色平铺的 90^3=729000 种组合里只剩 3 种（互为颜色循环置换）残差模式的上界为 11，其余 728997 种上界 ≤10（Fig. 11 说明）；Fig. 12 给出深度-8 的 3 色左右电路（"matching the original gross-code circuit"）。证据强度：对该电路"ten thousand outer loops"的最小权重逻辑算符搜索没有找到 <11 的（App. H 末尾引 App. D.2），属上界搜索，非证明 |
| 2601.12509 | Liu, Ping, Zhou, ..., Javadi-Abhari, Iancu, Li · 2026-01-18 | AlphaSyndrome：MCTS 搜索 syndrome 测量调度，译码器反馈引导 | H-002 的方法近邻（搜索 + 评估器，但不是 LLM，也无 SA 对照） | 摘要：相对 depth-optimal baseline 平均降低逻辑错误率 80.6%（最高 96.2%）。BB 码只测了 [[72,12,6]]：BP-OSD 下相对 IBM 调度降 44%，Unionfind 降 10%（Fig. 13）。MCTS 每步 4000–8000 次迭代；噪声为 IBM Brisbane 校准（CNOT p=0.0074，idle p=0.0052）；"typically generates ... greater depth than the lowest-depth baseline"。码规模范围 [[7,1,3]] 到 [[80,18,5]]，**未测 gross code** |
| 2601.17580 | Viszlai, Maurya, Tannu, Martonosi, Chong · 2026-01-24 | PropHunt：用 MaxSAT 迭代消除"歧义子图"、改进 CNOT 顺序，从 coloration 电路出发 | 近邻（优化 d_eff/逻辑错误率，非 LLM） | 方法：Z3 + Loandra MaxSAT，超时 360 s，最多 25 次迭代、每次 500 样本（Sec. 5.2、6.1）。评测码：表面码 [[9,1,3]]–[[81,1,9]]、LP [[39,3,3]]、随机量子 Tanner [[60,2,6]] 等（Table 1，Sec. 6）；**未评 BB 码** |
| 2603.21499 | Zhang, Gao, Yang, Zhou, Liu, Ji, Chen · 2026-03-23 | ASC：用 SMT/CP-SAT 对任意 qLDPC 码求深度最优的 syndrome 提取电路 | 给出深度下界证据：BB 码深度-7 最优 | Table II：[[144,12,12]] 深度 7，编译 <5 分钟；覆盖 [[72,12,6]]–[[756,16,≤34]] 共 7 个码；摘要："certifies that no depth-6 syndrome extraction circuit exists" 对 IBM 工作中的所有 BB 码实例；相对 ASAP/coloration 平均 7x–8x 逻辑错误率抑制（均为论文自称）。**只优化深度，未见 d_circ 数字**（我读到的片段中未找到） |
| 2609.12020 | Ye, Pabla, Palsberg · 2026-09-10 | FastSched：PPO 强化学习 + 重要性采样评估调度 | 近邻（RL，对 H-002 的 RL 对照；是 AlphaSyndrome/PropHunt 之后的新对手） | 相对 AlphaSyndrome 平均降 25.9%（11 个电路），相对 PropHunt 降 71.7%（8 个电路），表面码 d=15 降 97.8%（3 vs 126 次失败）（Table 1、Fig. 11）；搜索时限 10 分钟（d≤9）/30 分钟；**无 BB/gross code，无随机搜索、无 SA 对照** |
| 2607.25865 | Yan, Li, Ma, Zhang, Ma, Wang, Hsieh, Du · 2026-07-28 | OmniQEC：LLM 总控的"AI scientist"，含代码生成、码筛选、syndrome-extraction 合成、译码器评估 | H-002 的近邻（LLM 参与），但调度由边着色产生 | Sec. II.2：双比特相互作用用 Tanner 图边着色得到无冲突层；评测噪声 p=0.005、BP+OSD；发现的码在 N=98 和 N=240 物理比特预算下优于 [[72,12,6]] 和 [[144,12,12]]（摘要）。消融只比 full / fast-loop-only / no-feedback（Fig. 3d-f, Sec. III.4）；**无 IBM 调度对比、无 SA/随机搜索对照、未见 d_circ 数字** |
| 2606.02418 | Cruz-Benito, Cross, Kremer, Faro · 2026-06-01（IBM） | LLM 引导的进化搜索 BB / perturbed BB 码（OpenEvolve），约 1650 次迭代、约 20 万候选、约 140 小时、约 400 美元 LLM 费用 | H-002 的方法论近邻：有 LLM vs 随机 vs GA 的消融，但对象是码，不是调度 | 465 个候选码（块长 ≤360）；GitHub qiskit-community/qcode-discovery 的 README 称：随机采样（10000 样本/格点）Σk=299±26，LLM 引导 704，GA 在 d≤2 处一直失败；仓库**不**优化 syndrome 提取调度（README 转述） |
| 2606.24808 | Z. Liu, Marquardt · 2026-06-23 | SCE：LLM + 代数变异语法搜索 lifted-product 码族（GPT-5.4-mini/nano） | 码搜索侧近邻；不涉及调度（摘要未提） | 摘要：code-capacity 去极化噪声 + BP+OSD；未读全文，基线对照情况未知 |
| 2606.25870 | Heitritter, Brown, Hardikar（qBraid 博客）· 2026-06-24 | AlphaEvolve 搜 fermion-to-qubit 编码 | 证明 AlphaEvolve 已被用于 QEC 相关评估器，但不是调度 | 距离 5 的编码、数据比特少 4.2–5.0x（博客，约 1500 个候选程序） |
| 2109.14609 | Tremblay, Delfosse, Beverland · 2021-09-29；PRL 129, 050504 (2022) | coloration circuit：对任意度 δ 的 CSS 码构造深度 ≤2δ+2 的 syndrome 电路 | 经典 baseline（IBM 原文说 7 比 14=2·6+2 少，§5） | 摘要（经搜索结果）：深度至多 (2δ+2)；该文**不**优化 d_circ |
| 2308.15520 | Manes, Claes · 2023-08（Quantum 9, 1618 (2025)） | 证明超图乘积码上任何 syndrome 电路都保持有效距离（distance-robustness） | 说明 hook error 问题是"BB/LP 码特有"，HGP 无此问题 | 摘要（abs 页）；对 BB 码不适用 |
| 2407.16336 | Shaw, Terhal · 2024-07（PRL 134, 090602 (2025)） | morphing circuits：度 5 连通的 BB 奇偶校验电路 | 用不同的电路范式绕开 d_circ 问题，但对象是"end-cycle 码" | Table I：[[288,12,18]] BB 码的 morphing 电路，end-cycle 码为 [[144,12,12]]，d_circ≤12；标准 [[144,12,12]]：d_circ≤10。注意这是另一个 [[144,12,12]]，不是 gross code 本身的调度。Strikis 称其"same number of physical and logical qubits as the gross code, but circuit distance twelve"（2603.05481 App. H）|
| 2604.09797 | Shaw, Terhal · 2026-04-10 | 用 morphing 电路统一优化连通性/门类型/比特数 | 同上，探索"码+电路"的联合设计 | 只读了摘要，细节未核实 |
| 2603.22532 | Webster, Jacob, Higgott · 2026-03-23（v2 2026-08-14） | 距离计算算法（SAT、MIP、QDistEvol）与 codeDistance 包，含电路距离 | 评估器工具：电路距离上界/精确算法 | 摘要：算电路距离比算码距离难得多；我读到的片段中没找到 gross 码的 d_circ 数字（未找到） |
| 2603.00228 | Jacoby, Retzker, Pastawski · 2026-02-27 | Stairway codes：把 BB 码 Floquet 化 | 不同硬件范式，仅供参考 | 摘要："fewer than 300 physical qubits" 达到需 1300+ 比特的性能 |
| 2504.21200 | Pacenti, Pradhan, Borah, Vasic · 2025-04-29 | 用 trellis 均衡器在解码端处理 hook error（BB 码） | 另一条路：解码端补偿 hook，而非调度端 | 摘要；未读全文 |
| 2601.09911 | Kim, Gicev, Sevior, Usman · 2026-01-14 | 时间动态电路实现 shift 自同构 | 重述 gross code d_circ ≤10 | 摘要转述："circuit distance is estimated as d_circ ≤ 10" |
| 2308.07915 | Bravyi et al. · 2023 | IBM 原始调度 | baseline | d_circ ≤10；936 个变体都 ≤10（§5）；Open question 4："it may be possible to improve the circuit-level distance by using different SM circuits in different syndrome cycles"（§10） |
| 2501.09622 | （作者未核实）· 2025 | 搜索结果标题：用随机游走、SA、RL 优化超图乘积码 | 说明"SA vs RL"对照在**码**搜索中有先例 | 只见标题，未读（未核实）|
| 2608.08996 | （未核实）· 2026 | 搜索结果标题 *Multi-agent discovery of practical quantum LDPC codes* | 码搜索的 LLM 多智能体 | 只见标题，未读（未核实）|

## 新颖性判断

### H-001：gross code 存在比 IBM 深度-8 调度更好的调度
- **有没有人做过完全相同的事？** 就 d_circ 指标，是：2603.05481 已给出同深度（8 个 time step，摊销后与 IBM 相同）、d_circ 猜想=11 > IBM 的 ≤10 的电路（Fig. 12）。"更好"若定义为 d_circ 更大，H-001 已被他人在 2026-03 先报告，并且他们还证明了非交错电路的上界 11（Prop. 4），所以单辅助比特非交错调度的 d_circ 最多再提升 1。
- **证据强度**：该电路 d_circ=11 是猜想：只有 BP-OSD 找最小权逻辑算符，一万次外循环没找到 <11（App. H 末尾引 App. D.2），没有证明下界，也没有看到独立复现。本项目如果用精确方法（如 MIP/SAT，参见 2603.22532 的工具）验证它，是一个有价值的独立复核；这一条本身是否"新"取决于是否有人已做（未找到）。
- **该文没做的**：（a）我未在全文中找到该电路在电路噪声下对 gross code 的逻辑错误率模拟（未找到）；他们自己说 d_circ 与 N_fail 的改进不一定直接转化为"真实解码器和错误率下"的更好性能（App. 中对 FB126 的讨论）。（b）交错电路（interleaved）：论文明确说开放问题。（c）多辅助比特/flag 方案、跨 cycle 交替使用不同电路（IBM 原文 §10 Open question 4 的想法）：未找到已有结果。（d）非 gross 的其他 BB 码（[[72,12,6]]、[[90,8,10]]、[[108,8,10]]、[[288,12,18]]）：我没找到系统结果；AlphaSyndrome 只测了 [[72,12,6]]。
- **深度方向**：深度 <7 对 BB 码单辅助比特电路被 ASC 声称不可能（2603.05481 之外的另一篇，独立方法 SMT）。所以"同等深度下降低错误率"可行，"更低深度"在该电路范式下不可行（论文自称）。

### H-002：LLM 进化搜索优于同算力模拟退火
- **有没有人做过完全相同的事？** 没有找到。对调度问题：
  - 搜索类方法已有：MCTS（AlphaSyndrome）、MaxSAT（PropHunt）、SMT（ASC，只管深度）、PPO RL（FastSched）；这四篇两两之间相互比较过（FastSched 对 AlphaSyndrome、PropHunt），但没有一篇含 SA 或随机搜索对照（FastSched 读到的片段明确写 "No random search or simulated annealing comparison"），也没有 LLM。
  - LLM + 进化：对象都是码或编码（2606.02418 BB 码；2606.24808 LP 码；qBraid 的 2606.25870 编码），不是调度。OmniQEC（2607.25865）里 LLM 协调整个流程，但调度生成是边着色，无 SA 对照。
  - 最像 H-002 的"LLM vs 经典启发式"对照是 2606.02418 的消融（LLM 704 vs 随机 299±26 vs GA 失败），说明这类设计在码搜索上已有，**但对象与本项目不同，且对照物是随机采样与 GA，不是 SA**。
- **AlphaEvolve/FunSearch 用于调度**：未找到。
- **差别**：本项目的差别是（1）对象为调度；（2）对照为同算力 SA；（3）baseline 为 IBM gross code 的 Table 5 调度。

### 还剩多少空间
- H-001：在"d_circ"上只剩独立复核与交错/多辅助/跨 cycle 的构造空间；在"电路噪声下 gross code 的逻辑错误率"上空间较大（我没有找到已有的 gross code 调度对比数字）。建议把 H-001 的目标改写为"在固定深度（7 层 CNOT）下，同一噪声模型、同一解码器，p=1e-3 附近 pL 低于 IBM 调度，且 d_circ ≥10"，并明确把 Strikis 的 d_circ=11 电路作为第二个对照。
- H-002：空间较完整，但要有足够强的对照，需要同时报告 SA、随机搜索，最好再加 AlphaSyndrome/FastSched 风格的 MCTS 或 RL 作参照。如果搜索目标仍是 gross code 上的 d_circ，Strikis 的非交错上界 11 会让所有方法在 11 处饱和，难以区分 LLM 与 SA；若指标改为 N_fail（最小权故障数）或 p=1e-3 处的逻辑错误率，则区分度更大。

## 对本项目的建议
1. **把 2603.05481 当作 H-001 的头号对手**，先让 experimenter 复现其 Fig. 12 电路（需要从论文图中读出 8 个 time step 的标号，我在笔记里没有转录，避免出错），用与 IBM 调度相同的评估器比较 d_circ 和 pL。
2. H-001 的成功标准不应只用"d_circ 超过 10"，因为已被占；建议用 pL 或最小权故障数 N_fail 与 d_circ 联合排序，并在 hypotheses.md 里记下"非交错电路 d_circ ≤11"的理论上限。
3. H-002 的实验设计：同算力的 SA、随机搜索必做；MCTS（AlphaSyndrome 风格）可作为加分对照。注意 FastSched 报告它搜索时限仅 10–30 分钟，说明经典方法在小问题上很快，gross code 上的评估成本（BP-OSD）才是算力瓶颈。
4. 引用时别遗漏：2603.05481、2603.21499、2601.12509、2601.17580、2609.12020、2606.02418、2407.16336。
5. 以上 2026 年论文的编号、日期、数字均来自 arXiv abs 页或工具转述，**未经独立复现**；凡写进论文或 STATE.md 的数字，请再读原文核对。
6. 未读全文、需要补查的：2603.21499 的 d_circ 讨论、2601.17580 是否含 BB 码附录、2609.12020 的 qLDPC 结果、2607.25865 的 syndrome 合成细节、2606.24808 是否涉及电路。
