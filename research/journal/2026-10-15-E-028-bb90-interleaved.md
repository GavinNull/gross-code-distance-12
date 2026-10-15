# E-028 · [[90,8,10]] 交错单辅助比特电路能否 d_circ = 10（第二个码复现 gross 方法）

- 日期：2026-10-15 / 执行者：experimenter / 代码基线：git 50136bd，配置与预测跑前提交 b241b9d / 评估器只读（公开入口 build_code、build_circuits、add_noise、upper_bound）
- 配置：`experiments/E-028-bb90-interleaved.yaml`；代码：`search/experiments/e028/`；原始结果：`results/E-028-bb90-interleaved/`
- 码：IBM 2308.07915 Table 3 的 [[90,8,10]]，l = 15, m = 3, A = x^9 + y + y^2, B = 1 + x^2 + x^7（与 `search/codes/catalog.py`、评估器任务 bb90-dcirc 一致；`common.table()` 断言逐行支撑与评估器 HX/HZ 相同、45 个平移都是保标签的码自同构）。
- 文献：`research/literature/novelty-distance-preserving-bb.md` 记录 SBB 2603.05481 的 d_circ 数字只针对 gross，未见 [[90]] 的非交错上界；我不能下载，未能再核。所以“非交错 ≤ 9”只是我们 E-005 的结论。

## 结论先说

1. **方法的第一步在 [[90]] 上不成立**：没有任何每校验 CNOT 顺序能让扩展码 d_ext = 9。证明只用到码本身的 558 个权重 10 X 型逻辑：每个逻辑里最多只能有一个“被实现的”钩子对（两个不相交的对钩子 + 6 个数据 = 权重 8 扩展逻辑）。全部陪集着色（指数 1、3、5、9、15）两侧、以及逐校验完全自由的 X 侧都 UNSAT。
   推论（经 Cor. 1）：**可分段单辅助比特电路的 d_circ ≤ 8**（E-005 的 ≤ 9 不紧），且有电路取到 8，所以可分段电路的最优值恰为 8，与 IBM 电路的上界 8 持平。
2. 于是我把 lift 论证往下推一层：d_ext = 8 时，权重 9 的电路逻辑只有两种来源（9 个不同扩展列；或 8 个不同扩展列 + 1 个零像故障，即一次读出翻转）。两种都能精确判定，帧模型也能加上“一次读出翻转”的松弛。
3. **找到并认证（未审计）d_circ = 10 的交错单辅助比特电路** `search/experiments/e028/c16_spec.json`：所有 X 校验同一时序、所有 Z 校验同一时序（完全平移对称），周期 16 的不回绕帧，每个数据比特的循环 X/Z 序列切换 6 次。
   R = 1..12 两基底，两套实现（我的 DP；审计 b3 的 CP-SAT lift 改写版）都没有权重 ≤ 9 的不可检测逻辑；任意 R 前提（分离、周期性）机器核验；权重 10 数据逻辑注入给出上界；评估器 upper_bound（R = 3）两基底只找到 10。
   按委派要求，到此停下等 auditor，没有压周期、没有做经典对照。

## 过程与推理（按时间）

### 0. 单校验扩展码（复现 E-005）
`singles.py`：数据列 + 一个校验的 3 个钩子列。权重 ≤ 9 < d 的扩展逻辑必含钩子列，所以只跑钩子列的轨道情形。两侧都是 36 类 = 8、54 类 ≥ 9，与 E-005（MILP）一致。
值为 8 的正好是 4 个三元组类（与补集合并后）：A1A2B2、A1A2B3、A1A3B2、A1A3B3（及补）。允许的 6 类：A|B、A1A2B1、A1A3B1、A1B1B2、A1B1B3、A1B2B3。所以每侧 54 个“类型”。

### 1. 找 d_ext = 9 的类型赋值
- `dext.py`（e024b dextsat2 的移植：每个陪集一个类型，神谕 = 完整 W = 8 DFS，见证的钩子列连同 45 个平移像写成“不全出现”子句）。
  45 元平移群 Z15×Z3 的子群：指数 3 有 4 个、指数 5、9 各 1 个、指数 15 有 4 个。
  均匀（指数 1）两侧 COMPLETE、0 幸存（26/27 次神谕，复现 E-005 “均匀 ≤ 8”）；指数 3、5、9 全部 COMPLETE、0 幸存；指数 15 的 <(0,1)>、<(5,0)> 两侧 COMPLETE、0 幸存。
  <(5,1)> X 侧在第 1125 次神谕后单次 SAT 求解 30 min 不返回（换 glucose4、maplechrono 重放同一子句集也一样），我按 PID 停掉。瓶颈是 SAT 本身，不是神谕。
- 见证的结构（全部 7000 多个见证）：几乎都是“两个对钩子 + 6 个数据”（即码的权重 10 逻辑里含两个被实现的钩子对），以及权重 12 逻辑里的 4 对、对 + 三元组等。
  这提示把约束直接从码逻辑里“急切地”生成，而不是靠 DFS 一个个撞出来。
- `codelog.py`：数据列的完整 W = 10 DFS（45 元群）→ 每侧恰好 558 个权重 10 逻辑、没有更低权重（顺带直接证明了 d = 10）；W = 12 列表 10848 个（只当子句来源，不要求完整）。
- `eager.py`：对每个码逻辑 l（权重 w）和每组两两不交、分别落在某校验支撑里的标签集合 U_i（|U| = 2..4）且 Σ(|U_i| − 1) ≥ w − 8，钩子列 {(a_i, U_i)} + l 的其余数据比特就是一个权重 ≤ 8 的扩展逻辑，所以这些钩子列不能同时出现。
  只取包含极小的选择。每侧 14715 条子句，`verify_eager.py` 逐条重建扩展逻辑并核对 H 部分为 0、L 部分非 0、列数 ≤ 8（18630 个选择全部通过）。
- **只用权重 10 的子句**：全部 11 个着色（含均匀）两侧 UNSAT，每个 1.1–1.4 s（与懒循环已完成的结果一致；卡住的 <(5,1)>、<(5,2)> 也在 1.4 s 内 UNSAT）。
- **逐校验完全自由（45 色）X 侧**：CaDiCaL 50 min 无结论；局部窗口（a ∈ [0, k) 的 3k 个校验）k ≤ 11 可满足、k = 12 开始变难，说明冲突来自绕环一周；
  禁忌局部搜索 120 s 最好仍违反 14 条。CP-SAT（`eager_cp.py`，同一子句的线性形式，3 线程）**INFEASIBLE，1411 s**。Z 侧同样的 CP-SAT 跑了约 40 min 未结束，我按 PID 停掉（X 侧已经足以推出 d_ext ≤ 8，因为 d_ext 取两侧最小）。
- **结论 1（定理，待审计）**：[[90,8,10]] 任意每校验 CNOT 顺序（任意电路，不论是否交错）的扩展码 X 侧都有权重 ≤ 8 的扩展逻辑，d_ext ≤ 8；全部陪集着色两侧都如此。
  证明依赖：558 个权重 10 逻辑（完整 DFS）、子句的逐条有效性（已核）、54 类型限制（单校验 DFS）、CP-SAT 的 INFEASIBLE（单一求解器，须独立复核）。
- **推论**：Cor. 1 对可分段电路给出 d_circ = d_ext ≤ 8。均匀类型里每侧有 4 个 d_ext 恰为 8（`uniform7.py`：A1A2A3B2B1B3、A1A2A3B3B1B2、A1A3A2B2B1B3、A1A3A2B3B1B2），
  对照电路 `segctl.py`（X 块后 Z 块，周期 16）用这些顺序时精确 lift R = 1、2、3 两基底 585/585 个权重 8 扩展逻辑全部提升 ⇒ 该电路 d_circ = 8。所以**可分段电路的最优 d_circ 恰为 8**（STATE 已确认 1 的 ≤ 9 可加强）。
- 这一步宣告“复刻 gross 方法”的原样路线走不通：gross 是 d_ext = d − 1 = 11、只需排除权重 11；这里最多 d_ext = d − 2 = 8，Prop. 3 只给出 ≥ 8，要到 10 必须排除权重 8 和权重 9 两层。

### 2. 把 lift 推到 d_ext + 1
- 权重 8：与 gross 同理（d_ext = 8 ⇒ 8 个不同非零像组成权重 8 扩展逻辑），用完整权重 8 列表。均匀类 A1A2A3B2B1B3 每侧 585 个（13 个轨道，组成：2 对钩子 90、4 对 90、2 对 + 三元组 180 …；`wlist.py`，W = 7 完整 DFS 0 解证明 d_ext = 8）。
- 权重 9：像的多重集去掉成对相消、去掉零像后是一个权重 ≥ 8 的扩展逻辑，所以只能是 (a) 9 个不同非零像 = 权重 9 扩展逻辑，或 (b) 恰好 1 个零像故障 + 8 个不同非零像 = 权重 8 扩展逻辑 + 1 个零像项。
  (a) 的列表：d_ext = 8 且没有单列逻辑时，每个权重 9 扩展逻辑都是“症状极小”的（真子集症状为 0 只可能是权重 8 逻辑 + 单个逻辑列，或单个零列，都不存在），所以 W = 9 的 DFS 列表完整。每侧 16830 个（360 个是单对钩子 + 8 数据）。
  (b) 判定：同一个前沿 DP，加一个可选组 = {不选} ∪ {支撑落在 8 个组支撑并集内的零像检测器集合}（零像项若翻转并集外的检测器就无法被抵消）。零像项在该基底下就是读出翻转（每轮 45 个）。
  `lift9.py`（DP）与 `cert.py`（审计 b_common.dem_groups + b3 CP-SAT lift 改写，(b) 用“每列恰一项 + 恰一个零像项”的 CP-SAT）。
- 帧模型（`frame.py` 末尾）：(a) 用原模型；(b) 在一个读者配对节点上把两个比特拆成两个节点并加常数边 |H_a − H_b| ≤ 1（两比特在相邻两轮被看到 = 一次读出翻转可抵消）。常数边不带字面量，所以 nogood 的推导不变。

### 3. 时序搜索
- 先只阻断权重 8（`cegar.py`，均匀族 |Hs| = 45，每类型只有一个单元，不回绕 P = 16）：6 轮 34 s 找到候选 u16，R = 1..6 两基底 0/585 ⇒ d_circ ≥ 9。
  但 `lift9.py` 在 R = 1 就找到权重 9（类型 (a)）；评估器 upper_bound（R = 3，Z 基）也独立找到注入验证的权重 9。⇒ u16 的 d_circ = 9（作为对照：说明 (a) 层的阻断是真约束，也说明我的 lift9 与评估器一致）。
- `cegar9.py`（同一族，阻断 w8、w8+读出翻转、w9；建模代表 16 + 198，跳过支撑重叠的 10 + 550 个，留给精确检验）：**P = 16 不回绕，3 轮 28 s 得到候选，精确屏选 R = 1..4 两基底 0** → 存为 c16。
  第 1 轮建模提升 16 + 198，第 2 轮 2 + 4 + 18，第 3 轮 0。

### 4. c16 的认证（未审计）
- 电路：周期 16，所有校验 prep 0、meas 15。X 校验 CNOT：A2@1 A1@3 A3@5 B2@6 B3@8 B1@10（顺序 A2A1A3B2B3B1，属 A1A2A3B2B1B3 的 8 元类：s12 + s56）；
  Z 校验：B1@2 B3@4 B2@6 A3@7 A1@9 A2@12（B1B3B2A3A1A2 = X 顺序的反转）。validate_schedule 0 问题。每个数据比特循环 X/Z 序列切换 6 次（完全交替）。
- 精确：`lift9.py` R = 1..12 两基底，w8 = w8z = w9 = 0（全量计数，`c16_lift9_R1-12.log`）；`cert.py`（审计实现改写）R = 1..12 两基底全部 0，每组断言像集合 = 225 列、bad_obs = 0、telescoping_bad = 0（`cert_c16_{Z,X}.log`，各约 400 s）。
  控制：同一 `cert.py` 在 u16 上 R = 1 Z 基给出 315 个权重 9 提升；segctl 电路 R = 1 全部 585 个权重 8 提升。
- 任意 R（E-021 不回绕帧论证，`anyR.py` 移植，`anyR_c16.log`）：(S) 分离：第 j 轮 CNOT 在 [16j+1, 16j+12]、测量在 16j+15，R = 2、3、6 成立；(T) 周期性：R = 3..14 两基底，(R+1) 轮电路 = R 轮电路插入同一 16 层块，探测器与 observable 对应成立。
  按权重归纳：权重 ≤ 7 对任意 R 不可能（d_ext = 8 + Table I）；权重 8 的不可检测逻辑若中间有空轮可拆成两个更轻的不可检测部分，其一是逻辑 ⇒ 矛盾，所以跨 ≤ 8 个连续轮，删块后落到 R' ≤ 2 + 8 + 1 = 11；
  有了“任意 R 无权重 ≤ 8”，权重 9 同理跨 ≤ 9 轮，R' ≤ 12。R = 1..12 已全部精确检验 ⇒ **任意 R、两基底 d_circ ≥ 10**。
- 上界：最小权重数据逻辑（CP-SAT，权重 10）在数据复位后注入，R = 1、3、6、10 两基底 0 个探测器、observable 翻转（`inject10_c16_spec.json`）⇒ d_circ ≤ 10。
- 评估器 upper_bound（R = 3，1500 次 BP-OSD + stim search + LNS）两基底最好都是 10（低权重直方图 10: 59、11: 60…），与之一致。
- ⇒（待审计）**c16：[[90,8,10]] 的单辅助比特、交错、完全平移对称电路，任意 R、两基底 d_circ = 10 = d**。

## 与预测对比

| 预测 | 结果 |
|---|---|
| 存在 d_ext = 9 的颜色相关赋值（55%），指数 3 就有（35%） | 错：任何赋值（含逐校验自由，X 侧）都没有 |
| 颜色对称族认证 d_circ = 10（条件 55%，总体 30%） | 按原方法不可能；按扩展方法在最对称的均匀族里就找到了 |
| 最小周期 ≤ 16（40%） | 找到的是 16（不回绕帧，未压缩；更小的 P 未搜） |
| 经典对照 0 认证（90%） | 未做（按要求认证后停下） |

## 审计需要盯的地方
1. 扩展 lift 的情形分析（权重 9 = w9 或 w8 + 一个零像项），尤其是零像项的完整性（DEM 中零像且有检测器的项全部收进候选组）。
2. W = 8、W = 9 列表的完整性：只跑钩子列轨道情形（依据：数据列逻辑权重 ≥ 10，codelog 直接证明）；W = 9 的症状极小性论证。最好用独立枚举复核 585 / 16830。
3. d_ext ≤ 8 定理：CP-SAT 单一求解器的 INFEASIBLE（逐校验自由 X 侧）需要独立复核（另一编码或另一求解器）；Z 侧自由情形未完成。
4. 任意 R：归纳顺序（先权重 8 再权重 9），以及 E-021 分离 / 周期性前提在本电路上的核验。
5. “可分段最优恰为 8”依赖 Cor. 1（E-005 审计已确认其在可分段电路上的用法）。

## 未做 / 限定
- 没有压周期（16 层每轮，其中第 11、13、14 层无 CNOT；IBM 深度 8），没有搜 P < 16、没有回绕流水；没有经典对照（同族随机合法电路）；Z 侧逐校验自由的 d_ext ≤ 8 未完成。
- 只有 SD6、CNOT 模板；没有评估有噪逻辑错误率：只能说“电路距离达到 10”，不能说逻辑错误率更低（E-023 的教训：实际解码器下 d_circ 的收益可能很小）。
- 帧模型跳过了支撑重叠的逻辑（w9 有 550 个代表被跳过），所以候选的正确性完全由精确 lift 保证，模型只是搜索工具。

## CPU
约 8 CPU·h（其中卡住的懒 SAT 约 2 h、两次 CP-SAT 自由情形约 2.5 h、认证与评估器上界约 1 h）。最多 5 个计算进程。预算 40。

## 复现命令
```
PYTHONPATH=.:tests uv run python -m search.experiments.e028.singles
search/experiments/e028/run_dext_all.sh                                   # 懒循环（指数 3–15）
PYTHONPATH=.:tests uv run python -m search.experiments.e028.codelog --kind X --W 10   # 及 Z、W 12
PYTHONPATH=.:tests uv run python -m search.experiments.e028.eager --kind X --sub "0,0;5,1" --lazy 0 --W 10
PYTHONPATH=.:tests uv run python -m search.experiments.e028.eager_cp --kind X --sub 0,0 --workers 3
PYTHONPATH=.:tests uv run python -m search.experiments.e028.verify_eager --kind X
PYTHONPATH=.:tests uv run python -m search.experiments.e028.uniform7
PYTHONPATH=.:tests uv run python -m search.experiments.e028.wlist --kind X --orders A1A2A3B2B1B3 --w 8      # 及 --w 9 --dmin 8，Z 侧
PYTHONPATH=.:tests uv run python -m search.experiments.e028.segctl A1A2A3B2B1B3 A1A2A3B2B1B3
PYTHONPATH=.:tests uv run python -m search.experiments.e028.cegar9 --xo A1A2A3B2B1B3 --zo A1A2A3B2B1B3 --hs "0,1;1,0" --P 16 --nowrap 1
PYTHONPATH=.:tests uv run python -m search.experiments.e028.lift9 search/experiments/e028/c16_spec.json --R 1 2 3 4 5 6 7 8 9 10 11 12 --xo A1A2A3B2B1B3 --zo A1A2A3B2B1B3 --all 1
PYTHONPATH=.:tests uv run python -m search.experiments.e028.cert search/experiments/e028/c16_spec.json Z A1A2A3B2B1B3 1 2 3 4 5 6 7 8 9 10 11 12   # 及 X
PYTHONPATH=.:tests uv run python -m search.experiments.e028.anyR search/experiments/e028/c16_spec.json
PYTHONPATH=.:tests uv run python -m search.experiments.e028.inject10 search/experiments/e028/c16_spec.json
PYTHONPATH=.:tests uv run python -m search.experiments.e028.ub search/experiments/e028/c16_spec.json 3 Z 1500 1 1200   # 及 X
```
