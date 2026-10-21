# E-031 · VeriPB 证书：原生奇偶行 + 证明内的轨道拆分（d_ext 与逻辑列表完备性）

- 日期：2026-10-21 / 执行者：experimenter / 代码基线：git 53d2049 之后 / 不涉及评估器
- 配置（跑前写的预测）：`experiments/E-031-xor-certificates.yaml`；代码：`search/experiments/e031/`
- 原始结果：`results/E-031-xor-certificates/`（validation/、bb90/、gross/、exactness/、dev/、v1_superseded/；每组 `runs.jsonl`）
- 预算：30 CPU h，≤ 3 个工作进程（另一实验占 8 核，机器负载 15–17，墙钟约为 CPU 的 1.2–1.5 倍）。用量见末尾。

## 一句话结论

[[90]] c16 的 d_ext = 8（两基底）以及 585 个权重 8、16830 个权重 9 扩展逻辑列表的完备性，全部拿到 VeriPB 检查通过的证书；gross Fig. 12 两侧拿到 d_ext ≥ 9 的证书，d_ext = 11 与 4224 列表完备性在本预算内不可行（实测 W=10 每侧 5.0×10^8 个搜索节点，按检查速度约 62 CPU h/侧；W=11 约 400 CPU h/侧），只得到第三套独立实现的未认证确认（W=10 两侧无解）。

## 工具：为什么是 VeriPB 2、为什么没有下载配套求解器

- VeriPB 官方仓库 `gitlab.com/MIAOresearch/software/VeriPB`：主分支（f41ce91，2026-10-15）是 VeriPB 3，Rust 写的，编译要 Rust 工具链和约 190 个 crates.io 依赖。机器上没有 Rust，PI 只批准了 VeriPB 本身与配套求解器，没有批准工具链和 crates，所以**没有编译 VeriPB 3**（只克隆了源码，提交号记在 `tools/VERSIONS.txt`）。
- 用的是同一仓库的官方 `version2` 分支（b0d55dc，Python + C++）。C++ 核心用 clang 直接编译（GMP、zlib 来自已装的 Homebrew，pybind11 头文件是本机已有的文件），没有 pip 下载。包元数据缺失只影响启动横幅里的版本号，由 `veripb_run.py` 补上；检查器代码一行未改。
  自检：官方集成测试 289/289 通过（`tests/test_integration.py`，含 45 个必须被拒绝的错误证明）。
- 配套求解器：RoundingSat / Exact 要 cmake 与 Boost（都没有），而且它们是 CDCL / 割平面求解器，E-027 已经看到 CDCL 在权重 6 就停住；它们也没有高斯消元。Gocht–Nordström 的奇偶推理证明日志（AAAI'21）是嵌在 MiniSat 里的原型，没有找到官方发布。所以**没有下载任何求解器**。证明由我们自己的搜索程序 `pbdfs.c` 写出；它不被信任，所有 UNSAT 结论只靠 VeriPB 的检查。
- 除 VeriPB 仓库外没有下载任何东西。

## 编码（`build.py`）

变量：每个扩展码列一个 x_j；每个检查行 r 的二进制位 a_{r,k}（k < 4）；每条逻辑行一个 q_l 和二进制位 b_{l,k}。约束：

- 检查行：Σ_{j∈N_r} x_j − Σ_k 2^{k+1} a_{r,k} = 0（行和为偶数的原生线性表示，不用 Tseitin）；
- 逻辑行：Σ_{j∈N_l} x_j + q_l − Σ_k 2^{k+1} b_{l,k} = 0（q_l 就是该行的奇偶）；Σ_l q_l ≥ 1；
- 权重：Σ_j x_j ≤ W；阻断：对每个列表中的集合 B，Σ_{j∈B} ¬x_j ≥ 1。

精确性：0/1 点满足全部约束 ⇔ x 满足 H x = 0、存在一条逻辑行为奇、|x| ≤ W、不含阻断集（二进制位能表示每个偶数和：2(2^K − 1) ≥ 行长，脚本断言）。
逻辑行取原 12（[[90]] 为 8）条 L 行在对称群下的全部平移（按扩展码列向量去重）：gross Z 侧 168 条、X 侧 192 条，[[90]] X 侧 225 条、Z 侧 99 条。平移后的逻辑算符仍是逻辑算符，所以在 H x = 0 上“某条平移行为奇”⇔ L x ≠ 0；这样公式在群作用下逐字不变（脚本对全部 24 / 45 个群元做了逐约束核对），证明里的对称步骤才能成立。
另做了**可满足方向的独立核对**（`aux_checks.py models`，直接解析 .opb 文件求值）：发布数据里每个列出的逻辑都扩展成实例的模型——[[90]] X 侧 W=8 的 585/585、Z 侧 W=9 的 16830/16830、gross 两侧 W=11 的 4224/4224。所以编码没有把真解排除掉。

## 证明结构（`pbdfs.c` 写出，VeriPB 检查）

1. `strengthening_to_core on`；对每个轨道 o（代表列 rep_o）和轨道里每个其他列 g，用冗余规则 `red` 加入
   ¬x_g ∨ x_{rep_o} ∨ ⋁_{更早轨道} x，见证是把 rep_o 映到 g 的平移（变量整体换名）。在被否定子句之下，所有证明目标都成立：公式不变，较早加入的对称子句映到含“更早轨道的 ¬x”（那里为假）或含 x_g（那里为真）的子句。**轨道拆分本身在证明里被检查**，不是证明外的假设。
2. 非基逻辑行：由 E_m − Σ E_l − Σ E_r（x 的系数全为偶数）用一次除以 2 的割平面推出 3¬q_m + 3Σ_{l∈基} q_l ≥ 1（即 q_m → 某条基行为奇），再用 RUP 得 Σ_{基} q ≥ 1。这是 Gocht–Nordström 式的 XOR 相加，只做一次。
3. 每个轨道代表一个搜索树。奇偶子句 R(r, T)（T = 已选列与行 r 的交，|T| 为奇）由行等式推出：
   le + 2·((ge + Σ_{T} 2¬x)/2)，结果 Σ_{N∖T} x + 3Σ_T ¬x ≥ 1，传播效果与子句相同。叶子：
   某奇行已无可用列 → 直接用 R；权重用完 → `rup C ; ~ 权重 ge le`（权重约束把其余列置 0 后，行等式的二进制位在传播中自相矛盾：随机 40 例全部通过，见 dev 记录）；计数界（不相交行打包或最大覆盖）→ 一条 `pol`（Σ R + λ·权重）；紧的计数界（松弛 s）还会把“用了就超支”的列在整棵子树中排除，该 `pol` 放进子树内每条 RUP 的提示首位。内部节点：`rup C(S,F) ; ~ 子节点证书… R(r)`，然后删除子节点证书。
4. 代表列的单位子句 ¬x_rep，轨道内其他列的单位子句由对称子句经 RUP 得到；全部列被驳倒后，基逻辑行的奇偶子句给出 q = 0，与 Σ q ≥ 1 矛盾；`conclusion UNSAT : <id>`。
   `certify.py` 只在 VeriPB 返回 0 且同时打印 `s VERIFIED UNSATISFIABLE` 和 `Verification succeeded.` 时记为通过。

开发中的几次关键修正（都在 dev/ 里有记录）：最初直接对 225 条逻辑行分支（零伴随节点 225 路），节点数大 8 倍，改为基行后消除；RUP 提示不包含根层单位子句，所以奇偶子句里已驳倒的列要先用单位子句消掉；冗余目标默认包含派生约束，所以对称子句必须在任何推导之前加入（strengthening_to_core）；叶子改用 RUP 后检查时间约降 5 倍；紧计数界使节点数再降 2.5–3 倍。v1_superseded/ 里是用早期版本跑出的部分结果（同样通过检查），不计入下表。

## 验证（`results/E-031-xor-certificates/validation/`，以及 bb90/、counts/ 中的种植测试）

| 实例 | 预期 | 结果 | 搜索节点 | VeriPB CPU s |
|---|---|---|---|---|
| IBM BB72 扩展码 Z 侧 W=4（E-015：d_ext = 5） | UNSAT | VeriPB 通过 | 2 489 | 23 |
| 同上 X 侧 W=4 | UNSAT | VeriPB 通过 | 3 904 | 45 |
| BB72 Z 侧 W=4，不用对称（逐列拆分，无 red） | UNSAT | VeriPB 通过 | 65 696 | 9 |
| BB72 Z / X 侧 W=5 | 有解 | 找到权重 5 逻辑，独立复算 H x = 0、L x ≠ 0 | 4 622 / 52 | – |
| BB72 Z 侧 W=5，阻断搜索自己列出的全部 36 个权重 5 逻辑 | UNSAT | VeriPB 通过 | 9 375 | 25 |
| 同上，去掉一个轨道（种植） | 有解 | 找到的正是被去掉的那个 | 4 622 | – |
| IBM gross 扩展码，本文 Z 侧（H = HZ）W=7、W=8 | UNSAT | VeriPB 通过（与 E-015 该侧 W=8 无解一致） | 0.75 M / 4.55 M | 335 / 1 460 |
| IBM gross，本文 X 侧 W=7 / W=8 | UNSAT / 有解 | VeriPB 通过 / 找到权重 8 逻辑并复算（与 E-015 一致） | 0.55 M / 0.54 M | 244 / – |
| [[90]] X 侧 W=8，阻断 585 个中去掉一个轨道（种植） | 有解 | 找到的在被去掉的轨道里 | 51 947 | – |
| gross Z 侧 W=11，阻断 4224 个中去掉轨道 0（种植，只计数，不写证明） | 有解 | 找到 {0,4,60,61,62,63,66,68,134,138,318}，正是列表中轨道 0 的成员，复算为合法逻辑 | 6.7 M | – |

说明：IBM gross 那一行最初按 E-015 的“kind”标签写成了 `--expect sat`，实际是标签对应错了（E-015 的 kind X = 本文 Z 侧）。那次运行是 VeriPB 通过的 UNSAT，与 E-015 一致；runs.jsonl 里它的 ok=false 只是预期标错。

篡改测试（`validation/tamper/tamper.json`，对 BB72 Z 侧 W=4 的已验证证明）：去掉一个 RUP 提示、删掉子句中的一个文字、去掉奇偶子句推导中的除法、计数证书去掉权重项、对称步骤的见证换错两个像、删掉一行（之后的编号全部错位）——6 种无效改动全部被拒绝。另一种改动（把计数证书的乘数 λ 减 1）被接受：`pol` 步骤本身总是可靠的，减弱后的约束在那个节点仍然够用，所以这仍是一份正确的证明，不算漏检。

精确性的可满足方向见上一节（585/585、16830/16830、4224/4224 都是模型）。

## 结果：已由 VeriPB 检查的证书

全部为 `s VERIFIED UNSATISFIABLE` + `Verification succeeded.`；“节点”是生成证明的搜索树节点数（证明行数与之同量级）；证明 gz 大小为 gzip -1。

| 实例 | 含义 | 节点 | 生成 CPU s | VeriPB CPU s | 证明 gz |
|---|---|---|---|---|---|
| [[90]] c16 X 侧 W=7 | d_ext ≥ 8 | 726 255 | 5.5 | 311 | 17.8 MB |
| [[90]] c16 Z 侧 W=7 | d_ext ≥ 8 | 540 461 | 3.4 | 230 | 13.0 MB |
| [[90]] X 侧 W=8，阻断 585 个权重 8 逻辑 | 权重 ≤ 8 的扩展逻辑恰为这 585 个 | 5 959 497 | 52 | 2 666 | 143 MB |
| [[90]] Z 侧 W=8，阻断 585 个 | 同上 | 4 764 203 | 34 | 2 167 | 115 MB |
| [[90]] X 侧 W=9，阻断 585 + 16830 个 | 权重 ≤ 9 的扩展逻辑恰为这两张表 | 55 685 407 | 501 | 27 078 | 1.43 GB |
| [[90]] Z 侧 W=9，阻断 585 + 16830 个 | 同上 | 47 047 176 | 356 | 22 778 | 1.21 GB |
| gross Fig. 12 Z 侧 W=5 / 6 / 7 / 8 | d_ext ≥ 9 | 33 877 / 201 942 / 1 460 352 / 9 504 119 | 0.4 / 1.5 / 10 / 73 | 54 / 125 / 606 / 4 232 | 3.9 / 7.2 / 31 / 199 MB |
| gross Fig. 12 X 侧 W=5 / 6 / 7 / 8 | d_ext ≥ 9 | 32 367 / 203 029 / 1 424 185 / 9 238 012 | 0.3 / 1.5 / 10 / 75 | 55 / 126 / 605 / 4 281 | 4.1 / 7.4 / 31 / 198 MB |

列表存在性（上界方向）：585 和 16830 都是发布数据中的合法扩展逻辑（模型核对），所以 [[90]] 的 d_ext = 8 现在两个方向都有证书或直接核验。
证明文件除 BB72 Z 侧 W=4 外检查后删除（`--keep` 未开），记录 sha256 与大小（`runs.jsonl`）；证明由确定性搜索生成，可用 `certify.py` 重生。注意：W≤8 的那些运行里 gzip 头含时间戳，gz 的 sha256 不可复现，解压后的内容可复现（同一实例两次生成，解压后 sha256 相同；重复跑的 [[90]] Z 侧 W=8 节点数逐个相同）；之后已改为 `gzip -n`。W=9 两份证明另记了解压后内容的 sha256（`w9_plain_sha256.txt`）。

## 标度与 gross 的 d_ext = 11、4224 列表：本预算内不可行

同一搜索的只计数运行（不写证明，`counts/`；这本身是第三套独立实现的穷举，不是证书）：

| W | gross Z 侧节点 | gross X 侧节点 | 比值 |
|---|---|---|---|
| 8 | 9.50 M（已证） | 9.24 M（已证） | |
| 9 | 65.9 M | 65.4 M | ×6.9 |
| 10 | 498.7 M（无解） | 497.4 M（无解） | ×7.6 |
| 11 + 阻断 4224 | 未跑；外推约 3.3×10^9 | 同 | ×≈6.5–7 |

两侧 W = 10 的只计数搜索都没有找到逻辑（各约 65 CPU min），与 E-014 的两套 DFS 一致；这是 d_ext = 11 的第三个独立实现的确认，但没有证书。
VeriPB 2 的检查速度在本问题上稳定在每个节点约 0.45 ms（gross W=8：4 232 s / 9.5 M；[[90]] W=8：2 666 s / 6.0 M）。
因此 gross 的 W = 10 证书每侧约需 5×10^8 × 0.45 ms ≈ 2.2×10^5 s ≈ 62 CPU h 检查（另加约 1.5 h 生成、约 10 GB gz 证明），两侧约 125 CPU h；
4224 列表完备性（W = 11）每侧约 400 CPU h。都远超 30 CPU h。
瓶颈是检查器：VeriPB 2 的规则解析与 `pol` 计算在 Python 里，每行约 0.1–0.5 ms。VeriPB 3（Rust）应快得多，但编译需要 Rust 工具链和 crates，未获批准，所以没有测到它的实际速度；是否值得为它申请下载由 PI 决定。
搜索侧已做的削减：基逻辑行分支（×8）、紧计数界排除（×2.5–3）；仍可能有的改进（证书里加入偶数行的“流”约束做 LP 型下界）没有做。

## 结论

- [[90]] c16：d_ext = 8（两个基底）以及 585 个权重 8、16830 个权重 9 扩展逻辑列表的完备性（每个基底），全部有 VeriPB 检查过的证书（W=9 两侧检查各 6–7.5 CPU h）。E-028 定理 14 中“在完整 w8、w9 列表上精确判定”的输入因此不再只靠两套 DFS。
- gross Fig. 12：两侧 d_ext ≥ 9 有证书；d_ext = 11 与 4224 列表完备性仍然没有证书。新增的是一个独立写的第三套穷举（W = 10 两侧无解），以及实测的标度：按本检查器速度，证书约需 125 CPU h（W ≤ 10）与约 800 CPU h（W = 11），本预算内不可行。

## 建议论文措辞

- SM（[[90]]）：“For the [[90,8,10]] circuit we certify $d_{\rm ext}=8$ in both bases and the completeness of the lists of weight-8 (585 per basis) and weight-9 (16830 per basis) extended logicals. Each statement is encoded as a 0–1 linear feasibility problem in which every parity check is a linear equality with binary auxiliary digits, and its infeasibility is established by a pseudo-Boolean proof verified with VeriPB [Gocht–Nordström 2021; Bogaerts et al. 2023]. The reduction to orbit representatives of the translation group is part of the checked proof (redundance steps with the translation as witness).”
- SM（gross）：“For the gross code the same certificates establish $d_{\rm ext}\ge 9$ in both bases. The values $d_{\rm ext}=11$ and the completeness of the 4224 weight-11 lists rest on two independent exhaustive searches (Sec. S4), confirmed by a third, independently written search with different pruning ($5.0\times10^{8}$ nodes per basis at weight 10); they are not certified. At the measured checking rate a certificate for weight $\le 10$ would require about $60$ CPU hours per basis with the checker used here.”
- 不能写：“all computer-assisted steps are certified”；也不要把第三套搜索写成证书。可以写 “every infeasibility claim for the [[90,8,10]] circuit is certified (DRAT for the SAT instances, VeriPB for the extended-code distance and the list completeness)”——前提是 [[90]] 的 lift 实例也已有 DRAT（这一点需 lead 核对，E-027 只覆盖了 gross 的 A/B/C）。

## CPU 用量

| 项 | CPU h |
|---|---|
| 开发探测、早期版本运行（v1_superseded/，被新版本取代）、篡改/精确性/枚举等辅助检查 | 约 2.8（估计） |
| 正式运行 27 条（`*/runs.jsonl` 中 build + 搜索 + VeriPB 之和；其中约 0.7 h 是运行脚本被并发编辑后重复执行的 [[90]] Z 侧 W=8 和 IBM gross X 侧两条，结果一致） | 19.7 |
| 只计数运行（gross W=9、W=10 两侧，gross W=11 种植） | 2.4 |
| 合计 | 约 25（≤ 30） |

其中 [[90]] W=9 两份证书的检查占 13.8 h。

## 与跑前预测的对照

1) 验证（BB72 W=4 两侧证书、W=5 找到逻辑、篡改被拒）：符合。2) 种植测试：符合（BB72、[[90]]、gross 三处）。3) [[90]] W=7 两侧证书、每侧 < 2 CPU h：符合（各约 5 min）。
4) 585 列表完备性：符合，且比预测便宜（各 0.75 h，预测 3–6 h）；16830 列表“预算内不可行（80%）”：**预测错了**，两侧都完成（各 6–7.5 h）。原因是写预测之后又加了基逻辑行分支之外的紧计数界排除，节点数再降约 2.5 倍。
5) gross W ≤ 7 两侧、W = 8 至少一侧：符合（W = 8 两侧都有）；W = 10 / 11 不可行：符合，但外推数字偏大（预测 1.7×10^9 / 1.3×10^10 节点、≥ 200 / ≥ 1500 CPU h；实测 W=10 为 5.0×10^8 节点，折算约 62 CPU h/侧，W=11 外推约 3.3×10^9 节点、约 400 CPU h/侧），同样是算法在写预测后改进的结果。
