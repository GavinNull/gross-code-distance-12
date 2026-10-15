# E-029 · 绕开扩展码的直接交叉验证（第二份外部审读应对）

- 日期：2026-10-15 / 执行者：experimenter / 代码基线：git 50136bd / 不涉及评估器（只用公开入口 build_circuits、add_noise）
- 配置：`experiments/E-029-direct-dcirc.yaml`（预测在运行前提交，dcc0a62）；代码：`search/experiments/e029/`
- 原始结果：`results/E-029-direct-dcirc/`（inst/ 实例与 meta、runs/ 全部运行输出、orbits.json、verify.txt、selftest.txt）
- 预算 40 CPU h、≤ 4 进程；实际用量见末尾。

## 问题与我的判断

审读指出：定理 1 的证明里没有证书的承重输入是 d_ext = 11 和 4224 个权重 11 扩展码逻辑的完备性；引理 2 的证书只说明“列表里的没有一个能提升”。
要回应这一点，需要一条完全不经过扩展码的路线：直接在电路 A 的完整 DEM 上求最小不可检测逻辑的权重。E-021 审计（§4b）用 MaxSAT（7200 s）和
CP-SAT（3600 s）直接求解都没出结论，E-027 证明 SAT 编码在 d_ext 问题上权重 6 就已不可行。所以关键是换一种利用 DEM 稀疏结构的精确算法。

## 外部工具（PI 批准的下载）

- 从论文 arXiv:2603.22532 找到的官方仓库 `https://github.com/m-webster/codeDistancePYPI`，克隆到 `tools/wjh/codeDistancePYPI`，
  提交 `a4afe9c09bbf5790da9ecc05b65c5b62343979ad`（2026-05-28），记入 `tools/VERSIONS.txt`。纯 Python，不需要编译。
- **没有下载 m4riCC**：该仓库的 `dist_m4ri_CC` 只是一个包装器，C 代码在另一个组的仓库 `QEC-pages/dist-m4ri`（Pryadko 等），
  而且要先装 libm4ri。这两者都不是 WJH 的官方仓库，超出了批准范围（“只从作者官方仓库，别的不下载”），所以我停在这里。
  如果 PI 想要 m4riCC 本身的数字，需要另行批准 dist-m4ri 和 libm4ri 两项下载。另外，WJH 自己的基准（仓库内 `paper results/11 qc_BB.xlsx`）
  显示 m4riCC 在他们的 gross 码电路（r = 12）上 8 小时没有结果，在 [[90,8,10]]、[[108,8,10]] 上也没有，只在 [[72,12,6]]（r = 6）上 11 s 给出 6。
  照这个经验，即使批准，m4riCC 对我们的问题大概率也跑不完。
- 实际用到的 WJH 内容：(i) 他们自己的纯 Python 连通簇程序 CCMW（未改动，只把未安装的 gurobipy 做了空桩以便导入）；
  (ii) 他们公开的基准电路 `05_bivariatebicyclecodes/01_r=6,...[[72,12,6]]...stim`（sha256 435cede0…）和基准数字（m4riCC 6、Gurobi 6）。

## 方法：自写的精确分支定界（`ccsearch.c`）

对象是一个一般的奇偶校验问题：列（DEM 机制或扩展码列）各有一个行集合（探测器或校验）和一个 observable 集合，
判定或枚举 |x| ≤ W、行和为 0、observable 和非 0 的列集合 x。完备性的三条论证都写在源码开头：
(a) 最小权重解没有非空真子集的综合征为 0，所以部分集合综合征为 0 且 observable 为 0 时可以剪掉；
(b) 部分集合的综合征非 0 时，剩下的部分一定含有覆盖任一指定未满足行的列，对这一行的可用列逐个分支、每个分支之后对后面的兄弟排除它，
这样各分支划分了解空间；(c) 对称：群作用下每个解可以平移到“含有它最低轨道的代表、不含更低轨道的列”，于是按轨道分根情形。
剪枝只用合法下界：⌈|s|/w_max⌉，以及“两两没有公共覆盖列的未满足行”的贪心打包数；最后一层用综合征查表。行选择取可用覆盖列最少的那一行。

这和 SM S4 的 DFS 属于同一大类（以综合征驱动的分支），但代码完全独立、作用的对象不同（DEM），剪枝也不同（打包下界、最小性剪枝、动态选行）。
对称群不是假设的：`export.py` 在 DEM 上逐个检查 72 个平移，接受条件是每个机制的探测器集合被映到某个机制的探测器集合，
并且 GF(2) 上 rank[D;L] = rank[D;L∘P] = rank[D;L;L∘P]（于是 ker D 与 ker[D;L] 都不变，“不可检测”和“非平凡”都被保持）。
电路 A、Fig. 12 在 R = 1、2 两基底都恰好有 24 个这样的平移，与扩展码的 24 元群相同，在机制上自由作用（轨道全是 24）。
DEM 由评估器公开入口生成：`build_circuits` + `add_noise(sd6, 1e-3)`，stim `detector_error_model(decompose_errors=False)`，故障按 DEM 机制计数（与论文相同）。
电路 A 的 spec（`search/experiments/e024a/cs_P18_H24.json`）与发布包 `circuit_A.json` 规范化后相同。

## 验证（先验证方法，再看电路 A）

| 实例 | 规模（机制 × 探测器，对称） | 结果 | CPU |
|---|---|---|---|
| 随机小实例 vs 暴力枚举（`selftest.py`） | ≤ 30 列，含 2–4 阶循环对称 | 176/176 一致（d−1 判无、d 判有、枚举集合相等） | 秒级 |
| IBM BB72 深度 8，R = 1、2、3，两基底 | R = 1：432 × 72，36 元群 | 6 个实例全部：W = 5 无、W = 6 有 → **6** | < 1 s |
| WJH 基准电路 [[72,12,6]]，r = 6，si1000 | 16 164 × 432（合并了 1080 个完全相同的项），无对称 | W = 5 无（2.7×10⁹ 节点）、W = 6 有 → **6**，与他们 m4riCC、Gurobi 的 6 一致 | 193 s |
| WJH 自己的 CCMW（Python）on IBM BB72 R = 1 Z | 同上 | **6** | 4.6 s |
| Fig. 12，R = 1，Z | 864 × 144，24 元群，36 轨道 | W = 10 无（7.0×10⁹ 节点）、W = 11 有 → **11** | 261 + 68 s |
| Fig. 12，R = 1，X | 同上 | W = 10 无（8.5×10⁹）、W = 11 有 → **11** | 317 + 325 s |

Fig. 12 的 11 与 E-014/E-018 一致；找到的权重 11、权重 12 见证都在重新生成的 DEM 上复核过（`verify.py` → `verify.txt`：互异、探测器全抵消、observable 非 0）。

## (1) 电路 A 的直接计算（不用扩展码、不用列表、不用引理 1/2）

| 基底 | R | W = 11 判定 | 节点 | CPU | W = 12 |
|---|---|---|---|---|---|
| Z | 1 | **无** | 2.66×10¹⁰ | 1277 s | 有（487 s）|
| X | 1 | **无** | 1.27×10¹⁰ | 584 s | 有（314 s）|
| Z | 2 | **无** | 1.01×10¹¹ | 6225 s | 未跑（上界 12 由论文的数据比特注入给出）|
| X | 2 | **无** | 9.47×10¹⁰ | 5669 s | 同上 |

R = 1 的 DEM：864 个机制、144 个探测器、12 个 observable，最大列重 9。**结论：电路 A 在 R = 1 两基底的最小不可检测逻辑权重恰为 12**，
这是一条不依赖 d_ext = 11、不依赖 4224 列表、也不依赖引理 1（模板恒等式 / 像集合）的独立证明（只依赖本程序的正确性和 DEM 上机器核验过的对称性）。
R = 2 的 DEM：1584 个机制、216 个探测器、66 个根情形（轨道全是 24）。两基底 66/66 个根情形全部跑完，没有任何权重 ≤ 11 的解（`runs/A_R2_summary.txt`）。结合论文的权重 12 注入上界，**电路 A 在 R = 2 两基底的最小权重也恰为 12**。Knuth 随机探针的事前估计（R = 1 Z 2.7×10¹⁰、R = 2 Z 1.02×10¹¹、X 9.2×10¹⁰ 节点）与实际节点数都在几个百分点内吻合。R = 3 按同样的增长（每加一轮约 ×4）估计约 4×10¹¹ 节点/基底、约 7 CPU h/基底，在剩余预算内可做，但本实验没有跑（等 lead 决定是否需要）。

## (2) d_ext 与 4224 的第三次计算

扩展码在这里由 Fig. 12 的 CNOT 顺序自己重建（数据列 + 每个 X（Z）校验顺序的全部真后缀，按像合并）：两侧 360 列（列重 3/6/9 各 144/144/72），
每一列都能按 (H, L) 像对上发布包的列，所以列集合相等。24 元平移群也是在这里重新求出的。
- W = 10：两基底都**无**（Z 4.66×10⁹ 节点 162 s，X 4.45×10⁹ 节点 155 s）。论文 SM S4 的 DFS 约 2×10¹⁰ 节点/基底。
- W = 11 枚举（根情形输出 Z 254 条、X 257 条），用 24 元群展开去重：**Z、X 各 4224 个，与发布列表逐个集合相等**（only_new = only_list = 0）。
  CPU：Z 2203 s（4.65×10¹⁰ 节点）、X 2084 s（4.41×10¹⁰ 节点）。
- 这一结果同时是对 ccsearch 枚举完备性的强检验：如果分支或剪枝漏掉任何东西，展开后就不可能恰好等于独立程序得出的 4224 个。
- 真正算法不同的第三方实现（WJH CCMW，Python，没有预算剪枝，没有对称）在扩展码上的代价探针（`wjh_scale.py`，只算根列 0）：
  d = 5、6、7 分别 0.63、17.4、459 s，每层约 ×27。外推到证明“无 ≤ 10”需要约 459·27³ ≈ 9×10⁶ s/根，360 个根，约 10⁹ CPU s（数十 CPU 年），
  所以它不可行，这里只记录规模。

## (3) 轨道一致性（`orbits.py` → `orbits.json`）

在发布的两份列表上（各 4224 个，全部重新核过：11 个互异列、H 和为 0、L 和非 0）：
- 24 个平移在 360 列上自由作用（15 个轨道，每个 24 列）；列表在群作用下封闭；**没有任何一个逻辑被非平凡平移固定**（stabiliser 对数 0）。
- G ≅ Z12 × Z2，共 16 个子群；对每个子群 K 重新数轨道：轨道数都等于 4224/|K|，且全部轨道大小都是 |K|。
  特别地，阶 8 子群 ⟨(3,0),(0,3)⟩：528 个自由轨道；阶 12 的三个子群：各 352；阶 3：1408。两基底相同。
- 简短证明（不需要计算）：若某个 11 元列集合 S 被非平凡平移 g 固定，取 ⟨g⟩ 中素数阶元素 h（阶 2 或 3，因 |G| = 24）。h 也固定 S；
  由于 G 在列上自由作用，h 的列轨道大小都是 p，S 是若干 h-轨道之并，所以 p | 11，矛盾。因此任何 G 不变的权重 11 逻辑集合大小是 24 的倍数，
  4224 = 176 × 24 和各子群的计数是自动成立的。这说明轨道一致性只是一个弱检查（它能发现列表不封闭或记账错误，不能发现整轨道的遗漏）；
  能发现整轨道遗漏的是 (2) 的独立枚举。

## 论文可用措辞（建议）

SM S4 末尾的限制语句可以改为：
> Both $\dext=11$ and the list of 4224 weight-11 logicals were reproduced by a third, independently written exact search
> (a branch-and-bound over the extended-code parity checks with a packing lower bound and the translation symmetry,
> validated against brute force on random instances): no solution of weight $\le10$ in either basis, and its weight-11
> solutions, expanded by the 24 translations, coincide with the published list in both bases. None of these searches
> produces a checkable certificate.

新增一段（建议放在 S6 后或 S12 的 Verification）：
> \emph{Extended-code-free check at small $R$.} Independently of Lemmas 1 and 2, of $\dext$ and of the list, we computed the
> minimum weight of an undetected logical directly on the full SD6 detector error model of circuit A (864 mechanisms and
> 144 detectors per basis at $R=1$; 1584 and 216 at $R=2$) with an exact branch-and-bound search that uses the 24
> translations of the DEM (verified on the DEM itself). For $R=1$ in both bases there is no undetected logical of weight
> $\le 11$, and one of weight 12 is found, so the minimum is 12; at $R=2$ there is again none of weight $\le11$, and the
> weight-12 witness of S7 gives the minimum 12. The same program gives 11 for Fig.~12 at $R=1$, 6 for
> the IBM [[72,12,6]] circuit, and 6 for the [[72,12,6]] benchmark circuit of Webster, Jacob and Higgott, in agreement with their
> reported value. This confirms $\dcirc=12$ at these $R$ without the extended code; for general $R$ the proof still uses
> Lemmas 1–3.

不能写：“d_ext = 11 现在有证书”（没有证书，只是第三次独立计算）；“用 WJH 工具验证了”（只用了他们的 Python CCMW 在 BB72 上，
以及他们的基准数字；m4riCC 没下载）；“三种算法不同的方法”（ccsearch 与 S4 的 DFS 同属综合征驱动的分支搜索，只是独立实现、剪枝不同）；
“任意 R 不依赖扩展码”（直接计算只覆盖 R = 1、2）。

## CPU 用量

| 项目 | CPU s |
|---|---|
| 电路 A R = 1：两基底 W = 11 判定 + W = 12 | 1277 + 584 + 487 + 314 = 2662 |
| 电路 A R = 2：两基底 W = 11（66 根情形 ×2，拆成多进程） | 6225 + 5669 = 11 894 |
| Fig. 12 R = 1：W = 10、W = 11（含一次未存见证的重复） | 261 + 317 + 2×(68 + 325) ≈ 1364 |
| 扩展码：W = 10 判定 + W = 11 枚举 | 162 + 155 + 2203 + 2084 = 4604 |
| WJH 基准电路、IBM BB72、WJH CCMW、CCMW 代价探针 | 193 + 1 + 5 + 480 ≈ 680 |
| Knuth 估计、自检、导出、核验、轨道检查、被按 PID 停掉的进程未完成部分 | ≈ 800 |
| **合计** | **≈ 22 000 s ≈ 6.1 CPU h**（预算 40）|

## 异常与备注

- WJH 的 stim 文件生成的 DEM 有 1080 对完全相同（探测器与 observable 都相同）的项，stim 没有合并；我在导出时合并（同一机制用两次只会抵消）。
  我们自己的 DEM 没有重复项（导出时断言）。
- 运行中一度短时出现 5 个 ccsearch 进程（我误把一个仍在运行的 W = 12 任务当成已结束），发现后立即按 PID 停掉多出的那一个，之后重新启动，结果不受影响。
- R = 2 为缩短墙钟按轨道区间拆成多个进程：Z 为 0–19（原进程，完成轨道 19 后按 PID 停止）、20–39（完成 39 后按 PID 停止）、40–65；X 为 0–14（原进程，完成 14 后按 PID 停止）、15–19、20–65。每个根情形是独立的，`A_R2_summary.txt` 核对两基底都覆盖 66/66 个、0 个解。
