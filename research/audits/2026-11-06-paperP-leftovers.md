# 审计：论文 revision P 中没有直接审计覆盖的 8 处数字/说法

审计员：auditor（新开，2026-11-06）。只用自己的代码（`search/experiments/paperP_audit/`），原始输出在 `results/paperP_audit/`（不进 git）。
读过但没有作为依据的：E-027 日志与审计、theoryA/theoryB 笔记与审计、E-035/E-040/E-044 日志与审计、`paper/claims_map.md`。
CPU 约 12 h（预算 15 h），任何时刻自己的工作进程不超过 4 个。

## 总表

| # | 说法 | 结论 | 论文改动 |
|---|---|---|---|
| 1 | SM：Fig. 12 重定时 "each certified by DRAT" | **CONFIRMED** 50/50（含 len2only 25/25） | 不改 |
| 2 | 两钩子证书 5,400/7,344（u11 w11）、405/585（c11 w8） | **CONFIRMED**，两基底；c11 的 405 个都扛得住一个读出翻转 | 不改 |
| 3 | 三元组 8（[[90]]）、10（gross） | **CONFIRMED**，列表与 theory A 逐个相同 | 不改 |
| 4 | Lemma 3 见证 "replayed in stim (sampled)" | **CONFIRMED**（抽样 [[90]] 20/20，gross 3/3） | 不改 |
| 5 | c11 直接 DEM 搜索 "R ≤ 12" | **INCONCLUSIVE**：只能独立复现 R = 1 两基底（+ theoryB 审计的 R ≤ 2 X） | 表格改为已审计范围 |
| 6 | 读出散射 "3.4e-4 applied for 1 ms" | 数值与来源 CONFIRMED，**"applied for 1 ms" 只对 cur 成立** | 改备注 |
| 7 | Fig. 1 Z58/Z60；周期引理 "最长链 8 步" | **CONFIRMED**（stim 注入 + 暴力枚举） | 不改 |
| 8 | "g10 1.45e-4、u11 3.39e-4，约为 IBM 的 5–10 倍" | **REFUTED（u11 部分）**：按推荐 IBM 值是约 6 与 14 倍 | 改 SM 与正文 Cost 段 |

## 1. Fig. 12 重定时的 DRAT 证书

`item1_fig12_drat.py`：对发布包里全部 50 个 Fig. 12 重定时 CNF（25 个全逻辑族实例 + 25 个 len2only 实例），解压后核对 sha256 与记录一致，再用本地 CaDiCaL（tools/cadical）重新求解并产生 DRAT，用 drat-trim 检查。
结果：**50/50 sha 一致、UNSAT、drat-trim VERIFIED**；len2only 25/25（`results/paperP_audit/item1.log`）。
台账里"25 个 len2only 中审计只重跑了 10 个、其余 15 个只核了记录"这个缺口现在补上了。论文那句 "bulk statements, each certified by DRAT" 指的是这些族的不可行性，正确，不改。
（`release/` 只读，没有在其下运行任何东西；证明写在临时目录，检查后删除。）

## 2. 钩子环证书覆盖

`item2_hookcycles.py`，用已审计的体内模型 `search/theory/B_audit`（`bulk_columns`）。我自己的判定：刚性钩子列（唯一实现是钩子）之间，凡是只被两列触及、每列恰一个项的读者，给出等式 x_g − x_f = o_f(z) − o_g(z)；系统不相容 ⇔ 有非零和乐环 ⇔ 有证书；"扛一个翻转" = 任意一条边 ±1 后仍不相容。

| 电路/基底 | 列表 | 有证书 | 扛一个翻转 | 最短环长度 |
|---|---|---|---|---|
| u11 Z / X | w10（144） | 144 / 144 | 144 / 144 | 全是 2 |
| u11 Z / X | w11（7,344） | **5,400 / 5,400** | 5,184 | 2：4,032，3：432，4：936 |
| c11 X / Z | w8（585） | **405 / 405** | **405 / 405** | 2：315，3：90 |

5,400/7,344 与 405/585 都复现，两基底相同。w11 不需要扛翻转（11 + 1 = 12 = d）；c11 的 w8 需要（8 + 1 < 10），而 405 个全部扛得住，所以论文 "certify … 405 of the 585 weight-8 logicals" 在带翻转的意义下也成立。"(or longer hook-only) cycles" 的措辞也对：u11 w11 有 1,368 个需要长度 3–4 的环。

## 3. 落在权重 d 逻辑里的三元组

`item3_triples.py`：自己由多项式造码（与评估器 HX/HZ 逐元素相等），自己的 GF(2) 核，CP-SAT 判"含该三元组的权重恰为 d 的非平凡逻辑"是否存在，可行解用线性代数复核。

- [[90]]：X、Z 两侧都是 **8/20**：A1A2B2 A1A2B3 A1A3B2 A1A3B3 A2B1B2 A2B1B3 A3B1B2 A3B1B3，其余 12 个 INFEASIBLE。对：两侧 15/15。
- gross（X 侧）：**10/20**：A1A2B1 A1A3B2 A1A3B3 A1B1B3 A1B2B3 A2A3B1 A2A3B2 A2B1B2 A2B1B3 A3B2B3；其余 10 个 INFEASIBLE（A1A3B1 在 900 s 时 UNKNOWN，加长到 5400 s 后 INFEASIBLE，用时 1,132 s）。gross Z 侧只跑了前 5 个（结论与 X 侧相同）就为省预算停掉了；[[90]] 两侧结果完全相同，BB 码 X/Z 两侧对称，我不认为这是缺口。
- 两个列表与 theory A 表 (iii) 逐个相同。

## 4. Lemma 3 见证的 stim 重放

`item4_lemma3_stim.py`（注入器 `inject.py` 只用评估器公开的 `memory_circuit`/`unroll`）。自己随机抽合法的 T(8) 计时向量（自己的合法性条件：X、Z 各 6 个连续时刻、两种数据比特上 mod 8 互异、G_L = G_R；之后评估器 `unroll` 校验，无噪电路采样全 0）。对每个向量、每个基底、两个对钩子（第 4 个 CNOT 后，残余 = 末对；第 2 个 CNOT 后，残余长 4 ≡ 首对），取含该对的权重 d 逻辑，在辅助比特上注入钩子（实例 j），其余 d − 2 个比特的单比特错误放在同一轮间空隙，R = 7。**只扫内部实例 j = 2..4 和内部空隙**，排除边界效应造成的假阳性（第一次只扫全部位置时，所有见证都落在 j = 0 的边界，这不是对体内引理的检验，已弃用）。

- [[90]]：**20/20 个向量都有权重 9 的内部见证**，0 个探测器、observable 翻转；6 个向量只有 4 个候选钩子中的 2 个成立，说明测试能区分平坦与不平坦。
- gross：抽样 3 个向量，**3/3 有权重 11 的内部见证**（其中 1 个只有 4 个候选钩子中的 2 个成立；每个向量约 20 min，为省预算在第 3 个后按 PID 停掉）。
- 阴性对照（`item4_control.py`）：在 c11（d_circ = 10）上用同样构造试 72 次，**0 次**得到未检测逻辑。

论文 "sampled witnesses were replayed in the memory circuit by stim" 成立。

## 5. c11 直接 DEM 搜索 "R ≤ 12"

我先用 CP-SAT（自己的模型，带空间平移对称破缺）判 R = 1、W ≤ 9：900 s UNKNOWN（theoryB 审计也报告过 CP-SAT 90 min 无结论）。改写了自己的 C 穷举（`dfs.c`：按最低未满足探测器分支、兄弟排除、根只从触及校验 0 的机制出发，利用 45 个平移；找到的解在 Python 里按 DEM 异或复核）：

| 基底 | R | W | 结果 | 节点 | 时间 |
|---|---|---|---|---|---|
| X | 1 | ≤ 10 | 找到权重 10（复核通过，阳性对照） | 3.4×10⁷ | 4 s |
| X | 1 | ≤ 9 | **无** | 3.4×10¹⁰ | 674 s |
| Z | 1 | ≤ 10 | 找到权重 10（复核通过） | 8.7×10⁷ | 5 s |
| Z | 1 | ≤ 9 | **无** | 7.0×10¹⁰ | 1,537 s |

R = 2 按节点增长估计每基底要数小时，R ≤ 12 远超预算，所以没有做。已审计的直接搜索范围因此是：**R = 1 两基底（本审计）+ R ≤ 2 X 基底（theoryB 审计 §6）**。E-030 的 ccsearch R ≤ 12 两基底仍无独立复现。这不影响 c11 的结论（下界走的是已认证的提升 R ≤ 25 + 间隙论证），但表格 "direct search" 一栏应只写审计过的范围。

**改动**：`tab:attain` c11 行 "$R\le12$" → "$R=1$ ($X$: $R\le2$)"。若 lead 想保留 R ≤ 12，需要另一次独立运行（我的 `dfs.c` 可以直接用，每个 R、每个基底估计数小时以上）。

## 6. 中性原子读出散射

来源：2312.03982（Bluvstein 2024）ED Fig. 3 的 0.034% / 500 µs 成像（文献核对见 `research/literature/2026-10-24-final-reference-verification.md` 第 99 行与 E-035 审计）。代码：`search/experiments/e035/na_noise.py` 中 cur 的 `p_ro = 6.8e-4`（= 2 × 0.034%，按 1 ms 读出等待），proj 的 `p_ro = 3.4e-4`（= 一次 500 µs 成像，proj 的读出等待是 0）；施加方式是每个中途读出层给未被测量的原子加 DEPOLARIZE1(p_ro)。
所以表中备注 "applied for 1 ms" 对 proj 一列不成立。**改动**：备注改为 "0.034% per 500 μs image [Bluvstein2024], per mid-circuit readout; cur: doubled for the 1 ms readout wait; proj: one image"。

## 7. Fig. 1 例子与周期引理

(a) `item7_fig1.py`：列表第 0 个 w10 逻辑的每一列，我自己从 H、L 算实现（同 key 的数据比特；所有 X 校验后缀长 1–5 的钩子），得到 4 个刚性钩子列 X3(2)、X45(4)、X48(4)、X59(2)；只被两个刚性钩子触及的读者有 8 个，其中 **Z58、Z60 恰好只被 X45 与 X59 触及**。然后在 u11 的 Z 记忆电路（R = 6）里用 stim 单独注入两个钩子（实例 2）：X45（后缀 4）在 Z58 第 2、Z60 第 3 个探测器触发，X59（后缀 2）在 Z58 第 3、Z60 第 2 个触发。相对轮次差 −1 与 +1，**和乐 2**，与图注一致。

(b) `item7_period.py`：不用差分约束求解器，直接暴力枚举 P = 8..13 下所有与 u11（或 c11）同顺序、同 G（差一个常数）的合法计时向量：

| P | 8 | 9 | 10 | 11 | 12 | 13 |
|---|---|---|---|---|---|---|
| u11 实现数 | 0 | 0 | 0 | 2 | 34 | 286 |
| c11 实现数 | 0 | 0 | 0 | 2 | 34 | 286 |

在 P = 11–13 的每一个实现里，X 或 Z 窗口的跨度都至少是 8（最小值恰为 8），即签名强制一个窗口内 8 步的链，P_min = 8 + 3 = 11，P = 8、9、10 不存在。顺便：u11 的 G = (0,−1,−1;…)，c11 的 G 与表 S3 的 δ 差常数，都与论文一致。

## 8. g10/u11 每轮率与 IBM 的倍数

1.45e-4 与 3.39e-4 来自 E-040 电路审计 §7（每基底 15,000 发，R = 12，每轮 Z+X），我按计数重算一致。IBM 用 E-044 审计推荐的每发 Z 1.6e-4（1.4–1.8e-4），X 用合并直接计数 19/171,745 或分层 1.43e-4，每轮 Z+X 为 2.1–2.5×10⁻⁵（`item8_ratio.py`，Jeffreys 蒙特卡洛 95% 区间）：

| IBM 取值 | g10/IBM | u11/IBM |
|---|---|---|
| Z 1.6e-4，X 直接 | 6.5 [4.2, 9.7] | 15.1 [11.0, 20.4] |
| Z 1.6e-4，X 分层 | 5.9 [3.9, 8.4] | 13.6 [10.5, 17.3] |
| Z 1.4e-4 | 7.0 [4.5, 10.6] | 16.3 [11.7, 22.2] |
| Z 1.8e-4 | 6.1 [3.9, 9.0] | 14.1 [10.3, 18.9] |

所以 g10 约 6 倍，u11 约 14 倍，u11 的区间下端在任何 IBM 取值下都 ≥ 10。"5–10 倍"对 u11 不成立。（只有用 E-044 的分层原始点估计 IBM 4.1e-5、而 g10/u11 仍用直接计数，才会得到 3.9/8.0；那是把两种估计混用，审计没有推荐。）STATE 32 / E-044 审计说的"约 5–10 倍"看来是 g10 一类电路的量级，与 u11 的直接数字放在同一句里就不一致了。
**改动**：SM "about 5--10 times IBM's" → "about 6 and 14 times IBM's $2.4\times10^{-5}$ (direct counts, $1.6\times10^{-4}$ per $Z$ shot of 12 rounds)"；正文 Cost 段 "by a factor of about 5--10" → "by a factor of about 6 ($g_{10}$) to 14 ($u_{11}$)"。"g10 比 u11 低约 2.3 倍"仍然一致（14/6）。"down to 1.5e-3 at least about 1.5" 不受影响。

## 编译与字数

`cd paper && tectonic -X compile draft.tex` 无错误；`uv run python paper/scripts/count_words.py`：CORE TOTAL 3670（上限 3750），End Matter 1229 词。

## 复现命令（仓库根目录）

```
uv run python search/experiments/paperP_audit/item1_fig12_drat.py <tmpdir>
PYTHONPATH=.:tests uv run python search/experiments/paperP_audit/item2_hookcycles.py gross search/experiments/e032/u11_spec.json Z results/E-032-gross-short-period/w11_X_all_A1A2A3B3B1B2.pkl
PYTHONPATH=.:tests uv run python search/experiments/paperP_audit/item2_hookcycles.py bb90 search/experiments/e030/c11_spec.json X results/E-028-bb90-interleaved/w8_Z_all_A1A2A3B2B1B3.pkl
uv run python search/experiments/paperP_audit/item3_triples.py {bb90,gross} {X,Z} {pairs,triples} 900
PYTHONPATH=.:tests uv run python search/experiments/paperP_audit/item4_lemma3_stim.py {bb90 20,gross 12} 2026
PYTHONPATH=.:tests uv run python search/experiments/paperP_audit/item4_control.py
cc -O3 -o results/paperP_audit/dfs_bin search/experiments/paperP_audit/dfs.c
PYTHONPATH=.:tests uv run python search/experiments/paperP_audit/item5_dfs.py {X,Z} 1 {9,10}
uv run python search/experiments/paperP_audit/item7_period.py
PYTHONPATH=.:tests uv run python search/experiments/paperP_audit/item7_fig1.py
uv run python search/experiments/paperP_audit/item8_ratio.py
```
