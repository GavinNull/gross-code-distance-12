# 审计：paper/draft.tex 修订 g 的书面证明（SM S5、S7、优化性措辞）

审计员：auditor（红队），2026-10-14。只读被审对象；脚本与输出在 `research/audits/2026-10-14-revg-scripts/`。
复现命令（项目根目录）：

    PYTHONPATH=.:tests uv run python research/audits/2026-10-14-revg-scripts/g1_images.py     # DEM 层面 image 检查
    PYTHONPATH=.:tests uv run python research/audits/2026-10-14-revg-scripts/g2_propagate.py  # 自写 Pauli 帧逐故障传播
    PYTHONPATH=.:tests uv run python research/audits/2026-10-14-revg-scripts/g3_rprime.py     # R' 的每一项
    uv run python research/audits/2026-10-14-revg-scripts/g4_len2only.py                      # Fig.12 重定时障碍只用 len-2 逻辑

## 总结

| 项 | 结论 |
|---|---|
| 1. SM S5（Lemma 1 / Table I 证明） | **CONFIRMED**，两处措辞 FIX（非实质） |
| 2. SM S7（R' = 32） | **CONFIRMED**，两处措辞 FIX（首轮 detector 的理由；正文“from the fourth on”缺上界） |
| 3a. 证明方向的措辞 | **CONFIRMED**，两处 FIX |
| 3b. Fig.12 重定时障碍只用单 len-2 逻辑 | **FIX**：证书本身不是这样；len2-only 重跑在 20/25 个实例 UNSAT，5 个未完成 |

## 1. SM S5

### 逐行核对（模板：`evaluators/candidate.py::memory_circuit`，噪声：`evaluators/noise.py`）
- 门方向：X 校验 RX、`CX(anc→data)`、MX；Z 校验 R、`CX(data→anc)`、M。与 S5 “Gates of the template” 一致。
- 噪声位置：复位后翻转（R 后 X_ERROR，RX 后 Z_ERROR）、每个 CX 后 DEPOLARIZE2、测量前翻转、
  每层未被作用比特 DEPOLARIZE1；数据第 0 层复位、最终读出单独一层。与 S1/S5 一致。
- (a)(b)(c) 三条传播规则：正确，且只用到门方向和“每个辅助比特一个实例内 复位→6 CNOT→测量”，与时序无关
  （流水线下 X_1 的 CNOT 步 16,3,4,5,10,13 按实例内时间顺序就是表中顺序；anyr 检查 dm ≤ D−1，实例不重叠）。
- 五类单故障：全部正确。X_aX_d 在第 k 个 X 校验 CNOT 之后 → 从 q_k 开始的后缀；k=1 给整个校验（image 0）；
  Y 分量按 X 部分处理；Z 校验辅助比特上任何分量（含之后被测量/复位的）→ s=∅。
- Telescoping、“合并不改变”：电路的 OBSERVABLE_INCLUDE 包含 L_Z 全部 k 行，H 部分由 detector 决定，
  所以合并后的机制增广签名唯一。正确。

### 计算交叉核对
- g2（自写反向 Pauli 帧传播，不经 stim DEM）：circuit A 和 Fig. 12，R=1,2,3，两个基底，逐个 SD6 故障位置
  （复位翻转、测量翻转、每个 CX 后控制/目标/两者的帧分量、每层空闲、数据初始化/读出翻转）计算精确的 s：
  **0 个违例**，每个 s 都是 ∅、单个数据比特或某个 hook 校验顺序的后缀。按位置统计与 S5 的分类逐条对应，
  例如 R=2、Z 基底、circuit A：`hookCX_both` → suffix2..6 + single（k=6）各 144，suffix6 即 k=1 整个校验；
  `hookCX_ctrl` 在第 6 个 CNOT 后 → empty；`otherCX_tgt` → empty；`reset_flip_hook`、`meas_flip_hook` → empty。
- g1（增广 H、L 行 observable 的 DEM）：同样的 12 种组合下，每个 DEM 机制的 image 都为 0 或 360 列之一
  （`not_allowed=0`），360 列全部出现，telescoping 与逻辑部分 0 个不符。
- 注：circuit A 里没有“第一个 CNOT 之前的辅助比特空闲”（`idle_hook` 不出现 suffix6）；S5 对这种情况的说法
  仍然正确，只是在 A 中不出现。

### FIX（措辞）
1. S5 第一段 “Only the $X$ components of errors on data qubits affect the $Z$-type detectors …” 字面上不对：
   Z 校验辅助比特上的 X 也会翻 Z 型 detector（只是 image 为 0）。建议：
   > “In a $Z$-basis memory only $X$ components matter. For a fault we track its \emph{data $X$ frame}: …”
2. (c) “is then removed by the $X$-basis measurement and the next preparation”：MX 不移除 X，起作用的是下一次
   RX。建议：“… and is then discarded by the next preparation (the $X$-basis measurement does not see it).”
（可选）“Merging … including the augmented ones introduced below” 补一句理由：
   “(the $H$ parts are fixed by the detectors via the telescoping identity below, and all $k$ rows of $L_Z$ are
   observables of the circuit)”。

## 2. SM S7：R' = 32

g3 自己从 `unroll` 和含噪电路重算（与 `anyr2_cs_P18_H24.json` 逐项一致）：

| 量 | 值 |
|---|---|
| D | 18 |
| 起点 s_q | min 0, max 5 → S = 5（与 R 无关，R=1,2,5,9） |
| Δ_q = dm | 16..17 → Δ = 17 ≤ D−1 |
| 实例内最后一个 CNOT 偏移 | ≤ 16 = D−2（Settling 所需） |
| G = max(2D+Δ−1, D+S+Δ) | max(52, 40) = 52 |
| 跨度 10(G−1) | 510 |
| 插入点（含噪层串直接比较，R=2..8，两基底） | 恰为连续区间 [4, 18(R−1)] |
| 前端：f1 ≤ 4+D−1 | 21 → f11 ≤ 531 |
| 后端 2D−2：18(R−1) < 531+34 = 565 | R−1 ≤ 31 → **R' = 32**（18·31=558 < 565 ≤ 576） |
| 后端 2D−1（anyr.py 实际用的）：< 566 | 同样 **R' = 32** |

逐步论证核对：
- (1) Settling：正确。我还确认 2D−2 是安全的（实际只需 x ≥ f11+2D−3：较短电路在 x 处的在途实例复位于
  ≥ x−D+1 ≥ f11+D−2 > f11，其 CNOT 都在 ≥ f11+D−1，即帧已稳定之后）。
- (2) Splitting：比较 detector 与末轮 detector 的推导正确（END = max 测量层 + 1，已对 R=1,2,5,9 核对）。
  **首轮 detector 并非“analogous”**：已稳定（复位 ≥ a+D−1）的第 0 个实例测得 H_c e，和确定参考值 0 比较，
  仍可能对 F_< 响应。结论仍然成立，但理由不同：(c,0) 要响应 F_>，需要 b ≤ m(c,0) ≤ max_q(s_q+Δ_q) = 21，
  而 a ≥ 0，所以 b−a ≤ 21 < G。
- (3)(4) 删块：插入区间、前端/后端计数、2D−1 变体给出同一个界，全部 CONFIRMED。

### FIX（措辞）
1. S7 (2) “The first-round detectors are analogous” → 建议：
   > “A first-round detector $(c,0)$ responds to $F_>$ only if $b\le s_c+\Delta_c\le 21$ (circuit A), so with
   > $a\ge0$ it responds to both parts only if $b-a\le21<G$.”
   （要写成一般形式：$b-a\le\max_q s_q-\min_q s_q+\Delta+\min_q s_q$；对 A 这就是 21。）
2. 正文 Lemma 3 证明概要 “inserting an 18-layer block at any layer from the fourth on yields the circuit with one
   more round” 缺上界，而且“fourth”与 0 起编号的层 4 差一位。建议：
   > “inserting an 18-layer block at any layer $x$ with $4\le x\le18R$ (layers numbered from 0) turns the
   > $R$-round circuit into the $(R+1)$-round one.”
   （这与 SM 的“$R$ 轮 = $R-1$ 轮在 $x\in[4,18(R-1)]$ 处插块”是同一事实，只是轮数差一。）

## 3. 优化性措辞

### 3a. 哪个方向被证明：措辞基本正确（CONFIRMED + 小 FIX）
正文 “Cost and optimality” 与 SM S9/S10 现在一致地说：证明的是 model-lift ⇒ 真实逻辑错误，只对“十个数据 +
一个 length-2 残差”的逻辑；多残差逻辑只在 991 个抽样中确认；反方向不用。S9 的 Helly 论证我逐步核过：
差分约束 $H_c-H_d\le\lfloor(T_d-T_c)/P\rfloor+1$ 恰好等价于两个开区间相交（合法性保证 $T_c\ne T_d \bmod P$）；
一维 Helly 给出公共点；最晚左端点那个 Z 校验 CNOT 之后的 DEPOLARIZE2 含 $X_w\otimes I$；length-2 残差由
第 4 个 CNOT 后的辅助比特故障（或第 5 个 CNOT 后的 $X_aX_d$，到达时间相同）给出，到达时间固定。正确。

FIX：
1. 正文 “A model lift yields a genuine weight-11 undetected error once the number of rounds is large enough; we
   prove this for …” 第一句是无条件陈述。建议改为：
   > “For logicals of ten data errors and one residual of length two, a model lift yields a genuine weight-11
   > undetected error once the number of rounds is large enough (a one-dimensional Helly argument,
   > SM~\ref{sm:fig12}); for other logicals we confirmed this on the exact detector error model in all 991
   > sampled cases, including logicals with several residual columns.”
2. S9 的 model-liftable 定义（“every check sees each of its errors in the same instance”）比代码
   （`code/sat/frame.py`：一个校验看到 >2 个错误时允许配对，每对同一实例）严格。证明对配对版本同样成立
   （每对在同一实例 ⇒ 每个实例看到偶数个）。建议改为：
   > “… if instance indices can be chosen such that the errors seen by each check can be paired, both errors of a
   > pair being seen in the same instance (so all comparison detectors cancel), and …”
3. （可选，可能升级结论）多残差不是本质障碍：同一实例中、在一个 X 校验全部六个支撑比特的 CNOT 时刻各放一个 X，
   等价于在 $|+\rangle$ 辅助比特第一个 CNOT 之前放 $X_a$，是平凡故障。所以任何残差列（包括 length-4 的列，
   模型把它钉在补集 $V$ 上）的检测效果都等于“$V$ 上的错误、钉在该校验对应 CNOT 时刻”。S9 的构造对任意多个
   残差节点逐字成立（每个残差一个整数实例变量，仍是差分约束）。如果作者同意，可把“proven only for …”扩展到
   所有被建模的逻辑。我没有用注入独立验证这一点，只给作者参考，**不**建议未经复核就改。

### 3b. “Fig. 12 重定时障碍只用到单个 length-2 残差的逻辑”：部分 CONFIRMED，措辞 FIX
发布的编码器（`release/zenodo/code/sat/enc_primary.py`、`enc_second.py` 加 `--pin-fig12`）**并不**只用这类逻辑：
`frame.prepare` 用了全部 4224 个（按轨道取代表），证书里的 nogood 大多来自其他类型。例如 primary P=12：
1657 个 nogood 里 1res_len2 385，1res(length-4) 388，3 残差 696，2/4/5 残差 188；P16 无对称 common frame：
9585 个里 1res_len2 2849。所以 S9 那句 “Blocking every ‘ten data + one residual’ logical then requires a negative
cycle for each, which we encode …” 描述的不是证书。

g4 用同一编码器重跑，只给 frame model 360 个/基底的“十数据 + 一个 length-2 残差”逻辑（按 Fig. 12 顺序判定
length-2：$V$ 等于该校验 Fig.12 顺序的最后两个比特；sym24 下 30 个代表 = 2×360/24，计数吻合）：

| Table S3 行 | 证书 | len2-only 重跑 |
|---|---|---|
| sym24 common frame 任意 P（primary P=38） | UNSAT | **UNSAT**（351 nogood） |
| sym24 pipelined P=8..12（primary） | UNSAT | **UNSAT**（全部 5 个） |
| sym24 pipelined P=8..12（second） | UNSAT | **UNSAT**（全部 5 个） |
| P=9 子群：⟨(1,2)⟩ ⟨(1,5)⟩ ⟨(0,3),(2,1)⟩ ⟨(2,1)⟩ ⟨(2,4)⟩ ⟨(4,5)⟩ ⟨(0,3),(3,0)⟩ ⟨(0,3),(6,0)⟩ ⟨(3,3)⟩ | UNSAT | **UNSAT**（9 个） |
| P=9 子群 ⟨(4,2)⟩ | UNSAT（全部逻辑，我的重跑也 UNSAT） | **未跑完**（负责人因机器过载要求停止） |
| P=10 子群 ⟨(1,2)⟩ ⟨(0,3),(3,0)⟩ ⟨(2,4)⟩ | UNSAT | **未跑** |
| 无对称 common frame P≤16（primary P=16, sub 0,0） | UNSAT（全部逻辑 198 s，我的重跑也 UNSAT） | **>25 min 未结束，我停掉了**；没有给出 UNSAT |

结论：已跑完的 20 个实例中，障碍只靠 length-2 逻辑就成立，因此在 S9 已证明的方向下是定理级陈述（前提是编码器
本身正确完整）。剩下 5 个实例（P9 ⟨(4,2)⟩、三个 P10 子群、无对称 common frame P≤16）**没有**得到 len2-only
的 UNSAT；尤其无对称 P≤16 这个 len2-only 实例在全部逻辑下 198 s 就 UNSAT，只用 len2 却 25 分钟没解出，
不能排除它其实依赖多残差逻辑（即只在模型内成立）。

FIX（任选其一）：
- (A) 补跑剩下 5 个 len2-only 实例：
  `uv run python research/audits/2026-10-14-revg-scripts/g4_len2only.py 4,2 P10_subgroup P16_common_frame_nosym`
  （单进程；P16 的那个可能要几个小时，需要单独预算）。全部 UNSAT 后，S9 改为：
  > “The certificates block every model-liftable logical. Re-running the same encoders with only the 360
  > logicals per basis of the form ten data columns plus one length-2 residual gives UNSAT for every row of
  > Table~\ref{tab:fig12}, so each obstruction rests only on the direction proven above.”
- (B) 不补跑：把表注改成区分两种状态，例如在 caption 加
  > “Rows marked $^\dagger$ were re-solved with only the ten-data-plus-one-length-2-residual logicals and are
  > therefore proven; the others are obstructed within the frame model.”
  并给 P=9 ⟨(4,2)⟩、P=10 三个子群、“no symmetry, common frame, $P\le16$” 不加 $^\dagger$；
  同时把 S9 “Blocking every ‘ten data + one residual’ logical then requires a negative cycle for each, which we
  encode …” 改为 “Blocking a model-liftable logical requires a negative cycle in its constraint graph; we encode
  this for all modelled logicals, for CP-SAT and in a lazy-clause SAT loop.”
- 正文推论后的句子 “every legal circuit of several longer-period families keeping the orders has such an error”
  在 (B) 下应限定为加 $^\dagger$ 的那些族。


## 附带：副作用（需负责人处理）
在 `release/zenodo/` 下用 `uv run` 时，uv 因为该目录有 `pyproject.toml` 新建了 `release/zenodo/.venv/` 和
`release/zenodo/uv.lock`（2026-10-14 10:52，不在 MANIFEST 里）。我尝试删除，被权限系统拒绝。发布前请人工删除这两项。

## 资源
单进程（g4 的 worker 只有 1 个；负责人看到的 PID 10723–10729 是 PID 10573 `search.experiments.e026.direct` 的子进程，
不是本审计的，我没有动它们）。按负责人要求停掉了自己的 g4（PID 10716/10722）。总 CPU 约 1.5 小时。
