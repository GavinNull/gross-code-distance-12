# docs/课题说明.md §9 参考文献逐条核对
检索日期：2026-10-02；检索词：各文献标题/作者 + arXiv abs 页面（WebFetch 读取 arxiv.org/abs/<编号>）。
说明：核对依据是 arXiv abs 页面的标题、作者、提交日期、journal ref 字段。abs 页面由工具摘要后返回，"未核实"表示该字段没读到，不等于不存在。

## 结论（3-5 行）
- §9 的条目绝大多数能在 arXiv 找到并核实（标题/作者/年份/编号见下表）；FunSearch 与 AlphaQubit 未找到 arXiv 版本（只有 Nature DOI）；Lin & Pryadko、Panteleev & Kalachev、Roffe 三条原文只写了人名，已补出具体论文。
- 记错或需修正的地方共 6 处，其中对项目影响最大的是 §3.B：IBM 原文标题数字是"depth-7"（7 层 CNOT，加 init/measure 共 8 个 round），且 IBM 自己的调度 d_circ 只有 ≤10（论文推测 =10），"坏调度才会掉到 10"的说法不准确；§3.B 把"d_circ = 码距离 12"当硬约束，但 2603.05481 证明对非交错单辅助比特电路 d_circ=12 不可达。
- "IBM 2025 年系列工作（tour de gross 等）"只核实到一篇：2506.03094。

## 关键论文（逐条核对）
| # | 原文写法（§9） | 核实后的准确信息 | arXiv / DOI | 状态 |
|---|---|---|---|---|
| 1 | Bravyi, Cross, Gambetta, Maslov, Rall, Yoder. *High-threshold and low-overhead fault-tolerant quantum memory.* Nature 2024 | 标题、6 位作者全部正确。v1 2023-08-15，v2 2024-02-21。Nature 627, 778-782 (2024) | arXiv:2308.07915（abs 页：作者、日期、journal ref） | 正确。注意：§3.B 称"深度-8 调度"，见下"记错之处" |
| 2 | IBM 2025 年 BB 容错架构系列（"tour de gross" 等） | 只核实 1 篇：Yoder, Schoute, Rall, Pritchett, Gambetta, Cross, Carroll, Beverland. *Tour de gross: A modular quantum computer based on bivariate bicycle codes.* 提交 2025-06-03 | arXiv:2506.03094（abs 页）。ECZoo gross 页另列 2510.21600 为"architectural work"，我未读，未核实 | 部分核实；"系列"中其余篇目未核实 |
| 3 | Lin & Pryadko. Two-block group algebra codes 相关工作 | Hsiang-Ku Lin, Leonid P. Pryadko. *Quantum two-block group algebra codes.* 提交 2023-06-28。摘要：枚举权重 ≤8、n≤100（交换群）/ n≤200（非交换群）的最优参数 | arXiv:2306.16400（abs 页）。journal ref 未核实。IBM 原文还引了 Wang-Lin-Pryadko（其 [37,38]），编号未核实 | 论文存在；原文缺具体标题 |
| 3b | （§3.A）coprime BB 码 | 搜索结果出现 *Coprime Bivariate Bicycle Codes and Their Layouts on Cold Atoms*，URL 为 2408.10001v3（NCSU 站点）。作者/期刊未核实 | arXiv:2408.10001（仅来自搜索结果 URL） | 未核实 |
| 4a | Panteleev & Kalachev. Lifted product 码与渐近好的 qLDPC 码 | Pavel Panteleev, Gleb Kalachev. *Asymptotically Good Quantum and Locally Testable Classical LDPC Codes.* v1 2021-11-05，v2 2022-01-21。arXiv 主类别在 abs 页显示为 cs.IT | arXiv:2111.03654（abs 页） | 论文存在；原文未写标题 |
| 4b | （BP-OSD 来源，原文归给 Roffe） | BP-OSD 解码器最早出自 Panteleev & Kalachev. *Degenerate Quantum LDPC Codes With Good Finite Length Performance.* v1 2019-04-04；Quantum 5, 585 (2021)。IBM 原文把 BP-OSD 归给此文（其 [36]），把 Roffe 软件归为实现（其 [51]） | arXiv:1904.02703（abs 页）；IBM 归属见 2308.07915 §3、§6 | §9 把 BP-OSD 记在 Roffe 名下，不准确 |
| 5 | Roffe et al. BP-OSD 解码器与 ldpc 软件包 | Joschka Roffe, David R. White, Simon Burton, Earl T. Campbell. *Decoding Across the Quantum LDPC Code Landscape.* v1 2020-05-14。Phys. Rev. Research 2, 043423 (2020) | arXiv:2005.07016（abs 页） | 论文存在；ldpc 包版本号未核实 |
| 6 | Gidney & Ekerå, Quantum 2021 | 标题完全正确。提交 2019-05-23，修订 2021-04-13。Quantum 5, 433 (2021)。摘要：10^-3 错误率、1 μs 表面码周期 | arXiv:1905.09749（abs 页）。"2000 万"在标题里 | 正确 |
| 7 | Gidney. arXiv 2025 | 标题正确。提交 2025-05-21。摘要：<100 万含噪声比特、不到一周；三项改进为近似剩余算术、yoked surface code、magic state cultivation | arXiv:2505.15917（abs 页） | 正确 |
| 8 | Gidney, Shutty, Jones. *Magic state cultivation...* arXiv 2024 | 标题、作者正确。提交 2024-09-26。摘要：逻辑错误率低至 2e-9（典型噪声）、4e-11（更低噪声），置于一个表面码 patch 内 | arXiv:2409.17595（abs 页） | 正确 |
| 9 | Litinski. *A Game of Surface Codes.* Quantum 2019 | 完整标题为 *A Game of Surface Codes: Large-Scale Quantum Computing with Lattice Surgery*。提交 2018-08-08。Quantum 3, 128 (2019) | arXiv:1808.02892（abs 页） | 正确（标题被截短） |
| 10 | Gidney. *Stim: a fast stabilizer circuit simulator.* Quantum 2021 | 正确。提交 2021-03-03。Quantum 5, 497 (2021) | arXiv:2103.02202（abs 页） | 正确 |
| 11 | Higgott & Gidney. *Sparse Blossom* / PyMatching v2 | 完整标题 *Sparse Blossom: correcting a million errors per core second with minimum-weight matching*。v1 2023-03-28，v2 2025-01-14。Quantum 9, 1600 (2025)。摘要明确说实现发布为 PyMatching v2，两者是同一篇 | arXiv:2303.15933（abs 页） | 正确 |
| 12 | Romera-Paredes et al. FunSearch. Nature 2024 | 标题正确。作者含 Romera-Paredes, Barekatain, Novikov, Balog, Kumar, Dupont, Ruiz, Ellenberg, Wang, Fawzi, Kohli, Fawzi。Nature 625, 468-475 (2024) | DOI 10.1038/s41586-023-06924-6（Nature 页，经搜索结果）。arXiv：未找到 | 正确；无 arXiv |
| 13 | Google DeepMind. *AlphaEvolve.* 2025 | 准确标题 *AlphaEvolve: A coding agent for scientific and algorithmic discovery*，第一作者 Alexander Novikov（共 18 位作者，abs 页）。arXiv 提交 2025-06-16。摘要：4x4 复矩阵乘 48 次标量乘法 | arXiv:2506.13131（abs 页，cs.AI） | 作者归属应改为 Novikov et al.；"2025"正确 |
| 14 | Nautrup et al. *Optimizing quantum error correction codes with RL.* Quantum 2019 | 标题大小写：*Optimizing Quantum Error Correction Codes with Reinforcement Learning*。作者 Hendrik Poulsen Nautrup, Nicolas Delfosse, Vedran Dunjko, Hans J. Briegel, Nicolai Friis。提交 2018-12-20。Quantum 3, 215 (2019) | arXiv:1812.08451（abs 页） | 正确 |
| 15 | Olle et al. 噪声感知 RL 同时发现码和编码电路（2023–2024） | Jan Olle, Remmy Zen, Matteo Puviani, Florian Marquardt. *Simultaneous Discovery of Quantum Error Correction Codes and Encoders with a Noise-Aware Reinforcement Learning Agent.* v1 2023-11-08，v3 2024-04-04。npj Quantum Information，DOI 10.1038/s41534-024-00920-y。规模：最多 20 物理比特、距离 5 | arXiv:2311.04750（abs 页） | 正确 |
| 16 | Bausch et al. AlphaQubit. Nature 2024 | *Learning high-accuracy error decoding for quantum processors*，第一作者 Johannes Bausch。Nature 2024，DOI 10.1038/s41586-024-08148-8。卷/页未核实 | DOI 来自搜索结果；arXiv：未找到 | 正确；无 arXiv |

## 记错 / 需修正的地方
1. **§3.B"IBM 深度-8 调度"**：IBM 原文摘要和 Table 1/3 写 depth-7（7 层 CNOT）。Section 5 写"effectively N_r = 8 rounds"，Table 5 标题为"Depth-8 syndrome measurement cycle circuit"，其中第 8 round 只做 MeasX/InitZ，没有 CNOT。脚注 2：首个 cycle 需要额外 InitZ，深度 9，N_c 个 cycle 总深度 8N_c+1。（arXiv:2308.07915 §5 与脚注 2）。项目里讲"深度"时必须说明口径：CNOT 层数 = 7，含 init/meas 的 time step = 8。第三方也出现两种口径：ASC（2603.21499）说 depth 7，Strikis（2603.05481）说 depth 8。
2. **§3.B"坏调度会让距离从 12 掉到 10 甚至更低"**：IBM 自己的调度在 [[144,12,12]] 上就只有 d_circ ≤ 10（Table 1，并推测 =10）。原文还说用计算机搜出的 935 个深度-7 的备选调度加原调度共 936 个变体，对 [[144,12,12]] 全部 d_circ ≤ 10（§5 末尾）。即"距离掉到 10"是 baseline 本身的状态。
3. **§3.B"d_circ（硬约束 = 码距离）"**：Strikis, Browne, Beverland 证明非交错（non-interleaved）单辅助比特 CNOT 电路对 gross code 不可能 d_circ=12（Proposition 4，Sec. IV.3，arXiv:2603.05481v2）。交错电路是否可能为开放问题（同文 Sec. IV）。硬约束若设为 12，对这类电路族可行域为空。建议改为"d_circ 不低于 baseline 的 10，越高越好"。
4. **§9 把 BP-OSD 归给 Roffe**：见表 4b，算法属 Panteleev & Kalachev，Roffe et al. 是系统评测与软件。
5. **§9 AlphaEvolve 作者**：应为 Novikov et al.（Google DeepMind 团队），非"Google DeepMind"集体署名。
6. **§9 "IBM 2025 年系列工作"**：只核实 2506.03094 一篇；"series"不可当作已核实。

## 新颖性判断
不适用（本笔记是文献核对）。

## 对本项目的建议
- 把 §9 的编号补全（上表第 3、4a、4b、5 行），P0 前把表中"未核实"的字段（Lin–Pryadko journal ref、coprime BB 作者、AlphaQubit 卷页）补查。
- 修正 §3.B 的三处表述（上文 1、2、3 条），否则评估器的"d_circ ≥ 12"阈值和"深度 ≤ 8"的口径会在 P1 出问题。
- 新增必引文献：Strikis–Browne–Beverland 2603.05481（见 `novelty-schedule-search.md`）。
