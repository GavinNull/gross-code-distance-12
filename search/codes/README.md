# search/codes：码族枚举与快速筛选

H-003（码 + 电路联合设计）中“码”这一半的基础设施。只读依赖 `evaluators.codes.CSSCode`（公开接口）、
`baselines.schedule.bb_term_schedule` 与 `baselines.circuit`（噪声为 0 的确定性检查），不修改它们。

## 模块

| 文件 | 内容 |
|---|---|
| `groups.py` | 有限群（乘法表）；`abelian_group(l,m)`（x^i y^j ↦ i·m+j，与 IBM/`baselines` 的 Kronecker 约定一致）；`dihedral_group(r)`（非阿贝尔示例）；阿贝尔群的不变因子同构、全部自同构 |
| `construct.py` | `GroupAlgebraCode`（BB 与 2BGA 共用）；`bb_code(l,m,"x^3+y+y^2","y^3+x+x^2")`；`coprime_bb_code`（π=xy 的指数）；`two_bga_code(group,a,b)`；`.to_css()` → `CSSCode`；`.k`（位集 GF(2) 秩，约 0.1 ms）；`to_baseline_bbcode` |
| `constraints.py` | 权重、Tanner 图连通性、thickness ≤ 2 判定 |
| `distance.py` | BP-OSD 随机上界（次数 + 时间预算）；MILP 精确距离（HiGHS，带时限，超时给 [下界, 上界]） |
| `equivalence.py` | 阿贝尔群码的规范键（对称性去重） |
| `enumerate.py` | `ibm` 族与 `general` 族的枚举器 |
| `screen.py` | `screen_code(code, ...)`：单码完整筛选，输出 n、k、约束、d（exact/upper）、k·d²/n 等 |
| `schedule.py` | `default_schedule(code, sX=None, sZ=None)`、`check_schedule(code, sched)` |
| `catalog.py` | 文献中的权重 6 BB 码（IBM 表 3、Wang–Mueller 表 1/2），带 arXiv 出处 |
| `reproduce_ibm.py` | IBM 表 3 复现脚本 |
| `pilot.py` | n ≤ 150 的试运行 |

## 构造约定

群 G、a = a1+a2+a3、b = b1+b2+b3 ∈ F2[G]。项矩阵 `A_t[g, a_t·g] = 1`（左乘）、`B_t[g, g·b_t] = 1`（右乘），
HX = [A|B]，HZ = [Bᵀ|Aᵀ]。左乘与右乘可交换，所以任何群都有 HX·HZᵀ = AB + BA = 0。

- BB（arXiv:2308.07915 式 (1)(2)）：G = Z_l×Z_m。对表 3 的码，HX、HZ 与 `baselines/bb_code.py` 逐元素相同（有测试）。
- 2BGA（arXiv:2306.16400）：同一公式，换成任意有限群。阿贝尔群上的 2BGA 就是“单项式可以是 x^i y^j 混合项的 BB 码”。
  左乘/右乘的约定是我按“两者必须可交换”的要求定的，**没有逐字对照 2306.16400 第 II 节**；对阿贝尔群没有区别。
  非阿贝尔群目前只有 `dihedral_group` 示例和通用乘法表接口，**没有做等价去重**。

## 约束检查

- 权重：HX/HZ 的最大行重、每个比特的度（HX 列重 + HZ 列重），`weight_ok = 行重 ≤ 6`。
- 连通性：Tanner 图连通分量数（scipy csgraph）。不连通 = 若干份小码的直和，枚举时直接丢弃。
- thickness ≤ 2：Tanner 图的每条边都带项标签 t ∈ {A1,A2,A3,B1,B2,B3}（每个项矩阵在 X 侧、Z 侧各给一个完美匹配）。
  对 6 个标签的全部 31 种二分 (S, Sᶜ) 用 `networkx.check_planarity` 检查两个子图是否都是平面图；找到一组就判
  `le2`，同时记录是哪组分法（例如 gross 码是 `A1,A2,B1 | A3,B2,B3`）；31 种都不行就判 `unknown`（不按标签分的
  分法仍可能可行）。Tanner 图是二部图，E = 12|G| > 2V − 4，所以本身不是平面图，`le2` 实际就是厚度恰为 2。
  **说明**：IBM 论文第 4 节引理 2 用的是“由项矩阵分成两个平面子图”这一类论证，但本会话里没能读到论文原文，
  无法确认它具体用哪一组分法，因此我没有硬编码，而是把所有按标签的分法都试一遍；这是充分条件，带平面嵌入证书。
  表 3 的 7 个码全部判为 `le2`，与引理 2 一致。

## 距离

| 方法 | 结果类型 | 说明 |
|---|---|---|
| `distance_upper_bound_bposd` | 上界 | 2308.07915 第 6 节式 (11) 的做法（同 E-002）：随机取对偶类型的逻辑组合 η，用 BP-OSD（min-sum，OSD-CS order 7，先验错误率每次在 [0.01, 0.1] 随机）解 min\|ξ\|，s.t. Hξ=0、η·ξ=1。每个解都经过验证，是真实的逻辑算符，所以是严格上界。按次数或墙钟预算停止。 |
| `distance_exact_milp` | 精确，或 [下界, 上界] | min Σξ，s.t. Hξ − 2s = 0，L ξ − 2t − y = 0，Σy ≥ 1（L 是配对的对偶逻辑基）；HiGHS 证明最优才标 exact，超时则返回 incumbent（上界）和 dual bound（下界）。可加入已知上界 Σξ ≤ ub 剪枝。阿贝尔群码在两块同时平移下不变，平移在 L、R 上各自可迁，所以可加 ξ_L0 + ξ_R0 ≥ 1 破对称。 |

阿贝尔群码 d_X = d_Z（逆元自同构把 (A,B) 映为 (Aᵀ,Bᵀ)，它的 HX 正是块交换后的 HZ），只算 Z 型；非阿贝尔群两种都算。
实测（单核）：[[72,12,6]] MILP 0.04 s，[[90,8,10]] 4 s，[[108,8,10]] 7 s，[[144,12,12]] 33 s；BP-OSD 每次约 2–6 ms（n ≤ 144）。

## 对称性去重（`equivalence.py`）

用到的等价关系（都只是比特/校验的置换，有时外加 X↔Z 互换，n、k、d 与 Tanner 图结构都不变）：

1. **平移** A → gA、B → hB（g、h 独立）：HX 的列置换，HZ 的行列置换。据此每个多项式都可以规范为含 1。
2. **群自同构** φ ∈ Aut(G) 同时作用于 A、B：包括单位变换 x→x^u、y→y^v、l=m 时 x↔y、剪切 x→x·y^c 等，
   以及取逆 g→g⁻¹（即 (A,B)→(Aᵀ,Bᵀ)，X/Z 对偶）。
3. **交换 A/B**：HX、HZ 的左右块互换。
4. **群同构**：每个 Z_l×Z_m 先显式同构到不变因子形式 Z_d1×Z_d2（d1 | d2），所以 (15,2)、(10,3)、(6,5) 都归到 Z_30，
   (l,m) 与 (m,l) 也自动合并。

规范键 = 在 Z_d1×Z_d2 中，对 Aut(G) × 平移 × 交换 的轨道取字典序最小的 (sorted A, sorted B)，numpy 向量化，
每个码约 30–300 µs（取决于 |Aut|，Z_8×Z_8 时 |Aut| = 1536）。键相同 ⇒ 等价；键不同**不保证**不等价
（只用了上面这些已知的等价，是可靠但不完备的约简）。测试里用随机自同构/平移/交换验证了键不变。

## 默认调度（联合搜索接口）

`GroupAlgebraCode` 提供与 `BBCode` 同义的 `n2`、`x_check_neighbor(t,i)`、`z_check_neighbor(t,i)`，所以
`baselines.schedule.bb_term_schedule(code, sX, sZ, name)` 可以直接用在任何枚举出来的码上（BB 的混合单项式、2BGA
任意群都行）。`default_schedule(code)` = IBM 深度 8 顺序（IBM_SX/IBM_SZ，2308.07915 表 5）。在表 3 的码上，它与
`baselines.schedule.ibm_depth8` 逐层相同（有测试）。`check_schedule` 做结构校验，再在无噪声 stim 记忆电路上
（两种基、两种探测器）检查确定性。注意：IBM 顺序依赖项矩阵的交换性；非阿贝尔 2BGA 不保证成立，要逐码检查
（D6 上随机抽的 6 个 k>0 码都通过了，这只是抽查，不是证明）。

```python
from search.codes.construct import bb_code
from search.codes.screen import screen_code
from search.codes.schedule import default_schedule, check_schedule
c = bb_code(12, 6, "x^3+y+y^2", "y^3+x+x^2")
rec = screen_code(c, bposd_trials=200, exact_max_n=150)     # n, k, d, d_kind, kd2_n, thickness...
sched = default_schedule(c)                                 # baselines.schedule.Schedule
check_schedule(c, sched)                                    # {'valid_structure': True, 'deterministic': True, ...}
css = c.to_css()                                            # evaluators.codes.CSSCode
```

## 命令

```bash
uv run pytest tests -q -k codes_search
uv run python -m search.codes.reproduce_ibm --workers 3        # IBM 表 3 复现 -> results/codes-screen-pilot/ibm_table3_check.*
uv run python -m search.codes.pilot --n-max 150 --workers 3 --time-cap 3600 --seed 0
```

## 试运行（pilot）流程

见 `pilot.py` 文件头。阶段 0 枚举 + 去重 + 求 k + 连通性；阶段 1–3 逐级加大 BP-OSD 次数，只把排名靠前的码送入下一级；
阶段 3 对入选码跑 MILP。最终按 k·d²/n 排序（d 为证明了的精确值，否则为最好上界）。输出：`top20.csv`、
`top20_polynomials.txt`、`all_classes_kpos.csv`（全部 k>0 且连通的等价类及其粗上界）、`run_log.json`。

## 局限

- 排名用的是上界：上界偏松的码会被高估，阶段 2/3 加大次数并跑 MILP 来纠正；阶段 1 只有十几次试验，排名靠后
  的码不会再被细查（因为上界只会变小，所以排名靠后的码真实分数也只会更低，这一步不会漏掉好码；可能被挤掉的是
  阶段 2 截断线附近的码）。
- 等价约简不完备；非阿贝尔群没有约简。
- thickness 判定只覆盖按项标签的分法。
- `ibm` 族只覆盖“一个 x 幂 + 两个 y 幂 / 一个 y 幂 + 两个 x 幂”的形式；混合单项式（如 coprime 码）要用 `general` 族，
  它的规模是 C(|G|−1,2)²，n ≤ 150 时不可能穷举，pilot 里只做随机抽样。

## 已跑结果（2026-10-02，试运行，非正式实验）

- IBM 表 3 复现（`results/codes-screen-pilot/ibm_table3_check.*`）：7 个码 n、k 全部一致；BP-OSD 上界全部 ≥ 论文值
  （72/90/108/144/288/360 的上界等于论文值，756 码 2000 次只到 38 > 34，偏松但不矛盾）；n ≤ 144 的 4 个码 MILP 证明精确距离
  6/10/10/12；288 码 MILP 1800 s 内只得到 [11, 18]。全部 thickness 判为 le2，IBM 默认调度与 `ibm_depth8` 逐层相同，且确定性检查通过（n ≤ 288）。
- Pilot（`results/codes-screen-pilot/top20.csv` 等）：枚举 2,306,118 个候选（ibm 族在全部 l ≥ m ≥ 2、2lm ≤ 150 上穷举，
  加上每个形状 2000 个随机 general 样本），去重后 156,467 类，其中 k>0 且连通的 5,018 类；墙钟 2210 s，3 个 worker。
  第一名是 gross 码本身；没有找到 k·d²/n ≥ 12 的其他码。
