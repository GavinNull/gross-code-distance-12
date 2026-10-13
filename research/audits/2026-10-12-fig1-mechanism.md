# 审计：Fig. 1(b) 与 Key-idea 段落的机制论断（C49）

日期：2026-10-12　审计员：auditor（红队，新开 agent）　对象：`paper/draft.tex` Fig. 1(b) 图注 + Key idea 段；
数据 `paper/figures/fig1_concept_data.json`（`paper/scripts/fig1_concept_data.py`）。设定：Z 基 memory，R = 1，SD6（p = 1e-3，只影响 DEM 结构）。

## 结论

| 论断 | 结论 |
|---|---|
| 1. 例子逻辑算符的机制（Fig. 12 可提升 / P18 不可提升 / 4 检测器冲突环 / 早晚关系） | **CONFIRMED**（附一处措辞细化） |
| 2. 360 个“10 data + 1 hook”逻辑算符的冲突集大小分布 4(128)/5(184)/9(41)/10(7) | 原文“4 to 10” **CONFIRMED**；claims_map 里的具体分布 **REFUTED（作为内禀量）**：它是按检测器编号升序做删除法得到的产物，换顺序就变 |

## 独立实现（不调用 `b_common` 的 DEM/求解代码，不用 CP-SAT 判可行）

`research/audits/2026-10-12-fig1-scripts/`：
- `f_common.py`：电路只用冻结评估器 `build_circuits` + `add_noise("sd6")`；Fig. 12 直接从 `baselines.strikis.strikis_fig12` 生成；
  自建增广 DEM（HZ 行 + LZ 行作为附加 observable，按像分组）；**自写提升判定器**：带分量排序和“死位剪枝”的精确 XOR 状态 DP
  （每列选一个 DEM 项，限制在检测器子集 A 上校验子为 0）；删除法 IIS；最小基数 IIS 用隐式命中集（A 不可行 ⇔ A 与每个选择的校验子相交）。
- 唯一复用的输入数据：E-018 审计的 4224 列表（列键元组），我自己检查了每个都满足 HZ 和为 0、LZ 非零，并自己按 Fig. 12 的后缀权重分类。
- `f1_example.py`（论断 1）、`f2_stats.py`（升序/降序/最小/20 个随机序）、`f3_spread.py`（300 个随机序 + 仅 final 检测器）、
  `f4_exact.py`（全部可达校验子 → 包含极小族 → CP-SAT 求精确最小/最大 IIS 并枚举全部 IIS）、`f5_shape.py`（最小集结构）。
- 输出：`results/fig1-audit/*.log, *.json`。总 CPU 约 1 小时（含一次被我按 PID 终止的慢版本），≤4 进程。

复现：`uv run python research/audits/2026-10-12-fig1-scripts/f1_example.py`（f2…f5 同理，f2 带参数 `20`）。

## 论断 1 逐项

- 逻辑算符：data {0,1,6,12,16,19,74,78,79,91} + {9,25}，HZ 和为 0，翻转 LZ 第 1、4 行。✓
- X7 顺序：Fig. 12 = [82,85,91,8,25,9]（{9,25} 是第 4 个 CNOT 之后的残差）；P18 = [9,25,8,91,82,85]，恰为逆序。✓
  P18 第 2 个 CNOT 之后的残差 {8,91,82,85} 与 {9,25} 同像（相差 X7 稳定子）。✓
- Fig. 12：自写 DP 判定可提升。按文中给出的位置手工注入（data 74@4, 0@6, 1@6, 78@3, 79@4, 6@6, 16@6, 12@7, 91@3, 19@6；
  ancilla 151 在第 9 层 CX(151→8) 即第 4 个 CNOT 之后）：**0 个检测器触发，observable 1、4 翻转**。✓
  hook 沉积 25@10、9@11，晚于 Z6 读 9（4）与 Z15 读 9（6）。✓ 另：360 个全部在 Fig. 12 下可提升。
- P18：自写 DP 判定 **不可提升**。✓ hook 列在 P18 只有 1 个 DEM 项；其全部电路实现（`reduce_to_one_representative_error=False`）
  都是 X7 ancilla 的 X/Y 错，位置在第 2 个 CNOT（层 4）之后、第 3 个 CNOT（层 8）之前（含层 5–7 的空闲噪声和层 8 的 X_anc⊗X_8 等价形式）。
  沉积时刻 8→8, 91→9, 82→10, 85→18。✓（“only by an ancilla fault after the 2nd CNOT”成立，严格说是“第 2 与第 3 个 CNOT 之间”的 ancilla 错，均等价。）
- 冲突集：{Z6, Z12, Z15, Z18 的 final 检测器}（det 78, 84, 87, 90）不可行，任意 3 个可行 ⇒ 是 IIS；它同时是**最小基数**的
  （隐式命中集给出最小 = 4，且就是这 4 个），升序删除也得到同一集合。✓
- 读出时刻（P18）：Z6 读 0@6, 82@13；Z12 读 0@9, 6@2；Z15 读 12@8, 85@15；Z18 读 6@11, 12@3。
  hook 对 Z15 晚（85 沉积 18 > 15），对 Z6 早（82 沉积 10 < 13）；hook DEM 项在四个 final 检测器上的签名 = (Z6,Z12,Z15,Z18) = (0,0,1,0)。
  链：Z15 晚 ⇒ 12 晚于 8 ⇒ 对 Z18（读 3）也晚 ⇒ 6 晚于 11 ⇒ 对 Z12（读 2）也晚 ⇒ 0 晚于 9 ⇒ 对 Z6（读 6）也晚，而 hook 对 Z6 早 ⇒ Z6 奇宇称。
  各 data 列的 DEM 签名与此一致（例如 q12 只有 (0,0,0,0),(0,0,0,1),(0,0,1,1)，没有“对 Z15 晚但对 Z18 早”）。✓
  四个检查各自恰好看到逻辑算符的两个错误（P18 下 Z6 ∋ 0, 82；Z15 ∋ 12, 85；Z12 ∋ 0, 6；Z18 ∋ 6, 12；spread 中的 8、91 不在这四个检查里）。✓

## 论断 2：“极小冲突集”的定义与分布

定义：对逻辑算符 S 的 11 列，检测器子集 A **冲突**（conflicting）指：不存在每列各选一个 DEM 项、使所选项的校验子在 A 上全为 0 的选择。
等价地，A 与每一个可达校验子相交（命中集对偶）。**不可约冲突集（IIS）** = 冲突且去掉任一检测器即不冲突；**最小冲突集** = 基数最小的冲突集。
每个逻辑算符涉及 36 个检测器；可达校验子的包含极小族只有 4–10 个元素，所以全部 IIS 可以精确求出。

| 计算方式 | 4 | 5 | 9 | 10 |
|---|---|---|---|---|
| 升序编号删除法（论文脚本的做法；我用自写 DP 判定器复现） | 128 | 184 | 41 | 7 |
| 降序编号删除法 | 69 | 243 | 23 | 25 |
| **最小基数（精确，与顺序无关）** | **144** | **168** | **48** | 0 |
| 最大不可约（精确） | 24 | 288 | 0 | 48 |

- 论文脚本的分布 128/184/41/7 **被逐数复现**，但它只是“按编号升序删除”这一选择的结果；降序就变成 69/243/23/25。
- 精确结果：每个逻辑算符的全部 IIS 大小 ∈ {4,5,9,10}，(最小,最大) 只有四种：(4,4)×24、(4,5)×120、(5,5)×168、(9,10)×48。
  所以“所有不可约冲突集的大小都在 4 到 10 之间，两端都取到”是精确成立的；若“minimal”读作“最小”，范围是 4 到 9。
- 最小集结构：k 个不同 Z 检查各一个检测器（k = 4, 5, 9），沿 hook 与 k−1 个 data 列成环；
  只有 48/360（含例子）是“每个检查恰好两个错误”的纯环，其余 312 个中 P18 的四比特 spread 还有两个比特落在环上第三个检查里（偶数次，不改变宇称论证）。
  这不影响论文措辞（“exactly two errors”只用于 Fig. 1(b) 的例子），但“Timing thus turns each potential weight-11 logical into a parity cycle”是概括说法。

## 建议措辞

Key idea 段（替换“the minimal conflicting sets have 4 to 10 detectors”）：

> For all 360 logicals of this ``ten data plus one hook'' form, the lift fails at $R=1$, and every irreducible
> conflicting set of detectors (one whose constraints alone forbid the lift, but no proper subset does) has between
> 4 and 10 detectors; the smallest such set has 4, 5 or 9 detectors.

如需给数：最小冲突集 4 (144)、5 (168)、9 (48)。**不要**引用 128/184/41/7（依赖删除顺序）。claims_map C49 应相应修改。
图注与 Key idea 中关于例子的其余表述（第 4/第 2 个 CNOT、沉积时刻、Z15 晚 / Z6 早、Z6 奇宇称、Z6/Z12/Z15/Z18 的 final 检测器）可原样保留。

## 发现的问题

1. claims_map C49 的 4/5/9/10 计数是求解顺序产物（见上表）。论文正文只写“4 to 10”，在“不可约”含义下精确成立。
2. 小措辞：“realisable only by an ancilla fault after the 2nd CNOT” 正确，更精确为“between the second and third CNOT”。
3. 机制分析只覆盖“每列一个 DEM 项”的提升模型（与 Lemma 2 一致）；这是 C49 自述的“解释性”范围，非本审计新问题。
