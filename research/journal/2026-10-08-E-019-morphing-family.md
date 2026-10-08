# E-019 · Shaw–Terhal morphing 电路族的电路距离（H-006：morphing 是否普遍保距离）

- 日期：2026-10-08 / 执行者：experimenter / 评估器未冻结，只读使用 `evaluators/noise.py`（sd6）
- 假设：H-006
- 配置与事先预测：`experiments/E-019-morphing-family.yaml`（commit f5b76b0，先于任何计算）
- 代码：`search/experiments/e019/`；原始结果：`results/E-019-morphing-family/`

## 进行中（阶段记录，按时间）

### 阶段 0 · 电路族清单（文献 + 仓库，只读）

来源：2407.16336v3 Table I、App. G、Table VIII（本地文本副本）；仓库 `Mac-Shaw/morphing_qec_circuits/bb_params.py`
（WebFetch 只读，未运行）：`get_standard_morphing_specification`（Table II/IV）、`get_swap2_morphing_specification`
（docstring “as in Table VIII” = App. G.2“反转第 2 轮 CNOT”）、`get_three_round_morphing_specification`（Z_3 同态）。

| 母码（2308.07915 记号） | l, m | 合法同态 | 论文报的端点码 / d̃_circ 上界（Table I，BP-OSD） |
|---|---|---|---|
| [[72,12,6]] | 6, 6 | f_x, f_y, f_xy | [[36,12,3]] / ≤ 3 |
| [[108,8,10]] | 9, 6 | f_y | [[54,8,8]] / **≤ 7** |
| [[144,12,12]]（gross） | 12, 6 | f_x, f_y, f_xy | [[72,12,6]] / ≤ 6 |
| [[288,12,18]] | 12, 12 | f_x, f_y, f_xy | [[144,12,12]] / ≤ 12 |

Table I 其余码（如 [[90,8,10]]，l = 15、m = 3 均为奇数）没有合法同态。App. G.2 / Fig.（App. G）另报 Table VIII 电路
[[36,12,4]]（f_xy）与 [[72,12,7]]（f_y），称“有三个”端点码距离更大的电路，第三个未点名。App. C 另有两个非阿贝尔、权重 8 的 2BGA 码
（[[96,8,12]]、[[96,12,10]]），没有电路距离数据，需要 Table III 的一般电路（本实验未做，见“范围”）。
三轮（Z_3）morphing 只在仓库里出现；2604.09797 Prop. 1 只对两轮电路成立，不在本实验的证明方法范围内。

**一个规格上的自由度（本实验发现）**：Table II 与 Table VIII 都按 A、B 的项顺序 a1, a2, a3 / b1, b2, b3 写；
a1、b1 由同态唯一确定（“与另两项奇偶不同”的那一项），但 (a2, a3)、(b2, b3) 的先后是输入多项式的书写约定。
Table II 下交换两对等价于交换第 0、1 层（“论文序” = 仓库序两对都交换）；只交换一对得到另外两个合法电路（std01、std10）。
Table VIII 中 a2、b2 与 a3、b3 的角色不对称，四种顺序给出**不同的端点码**。所以电路族 = 10 个（码, 同态）× 8 个变体
（repo、paper、std01、std10；swap2 = 仓库输入顺序、sw01、sw10、sw11）= **80 个电路**。

### 阶段 1 · 构造（`common.py`、`construct.py`，约 2 CPU s）

- 推广了 E-017 auditor 的独立构造（任意 l, m, A, B）；加入 Table VIII（swap2），并按论文 Table VIII 逐项核对门与测量。
- 80/80：每层是完美匹配；收缩性质由 Pauli 传播**推导**（不假设）：每个 mid-cycle 稳定子恰在一个收缩轮收缩到单个、正确基底的被测右比特；
  扩张稳定子的右侧支撑只落在同基底测量上；端点码 k = mid-cycle k（12 或 8）；连接度 5。
- [[288]] 的 repo / paper 两种层序 × 三个同态：与 E-017 `morph.py`（Morph，swap23）逐层门集合、测量集合完全相同。
- 端点码校验权重：std 全部 9；swap2 类 9 或 11（论文 App. G.2 说“至多 11”）。

### 阶段 2 · 端点码精确距离（`endcycle.py`，adfs 穷举 + 平移轨道，合计 < 1 CPU min）

每个电路两个端点码（c = 0, 1）× 两种错误类型都算，四者总是相等：

| 母码 | std 四个变体（全部同态） | Table VIII 变体（swap2 / sw01 / sw10 / sw11） |
|---|---|---|
| [[72,12,6]] | 3 | f_x: 3/4/4/3；f_y: 3/4/4/3；f_xy: 4/3/3/4 |
| [[108,8,10]] f_y | 8 | 8/7/8/7 |
| [[144,12,12]] | 6 | f_x: 6/**8**/**8**/6；f_y: 5/7/7/6；f_xy: 6/6/5/6 |
| [[288,12,18]] | 12 | f_x: 10/12/12/10；f_y: 10/12/12/10；f_xy: 12/10/10/12 |

与论文一致：[[36,12,3]]、[[54,8,8]]、[[72,12,6]]、[[144,12,12]]；Table VIII 的 [[36,12,4]] f_xy（swap2/sw11）与 [[72,12,7]] f_y（sw01/sw10）。
新发现：[[144,12,12]] 母码、f_x、sw01/sw10 给出端点码 **[[72,12,8]]**（权重 11 校验）——论文的“第三个”可能就是它或 [[54]]/[[288]] 的某个，未核实。
