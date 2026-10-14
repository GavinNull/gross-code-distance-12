# E-027 · 证书升级：DRAT 证明 + drat-trim / cake_lpr 检查（外部审读应对）

- 日期：2026-10-14 / 执行者：experimenter / 代码基线：git ad7522a / 不涉及评估器
- 配置：`experiments/E-027-certificates.yaml`；代码：`search/experiments/e027/`、`scripts/zenodo/build_proofs.py`、`release/zenodo/code/proofs/`
- 原始结果：`results/E-027-certificates/`（part3/、lift_{A,B,C}/、lift_fig12/、control.txt、tamper/、dext_dev/）
- 预算：25 CPU h，≤ 3 个工作进程（E-026 模拟占其余核；机器负载 27–28，墙钟约为 CPU 的 2 倍）。实际用量约 13.3 CPU h（明细见末尾）。

## 工具（PI 批准下载）

`search/experiments/e027/build_tools.sh` 从官方仓库克隆并编译到 `tools/`（已加入 .gitignore），提交号记在 `tools/VERSIONS.txt`：
- CaDiCaL 3.0.1，`c60730422e758ef1cebe7aeddf2dda31c996bf04`
- drat-trim，`2e3b2dc0ecf938addbd779d42877b6ed69d9a985`（同时编译了 lrat-check，未使用）
- cake_lpr（CakeML 验证过的 LRAT/LPR 检查器，预编译汇编），`a36874a8b750b43fe4b385b8ddbf5b033e46a3fa`，`cake_lpr_arm8.S` 一次编译成功。

流程（`certify.py`）：CaDiCaL 解原始 DIMACS、写二进制 DRAT → drat-trim 后向检查（默认选项、-t 7200）并写出 LRAT 核心 → cake_lpr 检查该 LRAT。
记录 CNF / DRAT / LRAT 的 sha256、大小、判定、各步 CPU 秒。

流程自检（`results/E-027-certificates/tamper/`，P09_pipelined）：完整证明 VERIFIED；只保留前一半引理 → NOT VERIFIED；
完整证明配上去掉 CEGAR nogood 的 CNF（可满足）→ NOT VERIFIED。另：去掉最后的空子句 drat-trim 仍 VERIFIED（单元传播已冲突，属正常行为）。

## (3) 已有 104 个 UNSAT 证书（SM S10）——第一批，共 129 = 104 + 25（第二批见下节）

`results/E-027-certificates/part3/results.jsonl`。**104/104 CaDiCaL UNSAT，104/104 drat-trim `s VERIFIED`，104/104 cake_lpr `s VERIFIED UNSAT`，无超时。**
CPU 2.67 h（求解 1.08、drat-trim 1.36、cake_lpr 0.23）。DRAT 合计 5.68 GB；> 100 MB 的 13 个，最大 `less_symmetry/P11_subgroup_1_2`
（1569 MB DRAT、5.2 GB LRAT；求解 1881 s、drat-trim 2622 s、cake_lpr 350 s）。其余最大：primary P17 508 MB（418 s 检查）、P16 426 MB、
P08_subgroup_6_3 395 MB、6_0 384 MB、P15 314 MB、P16 common-frame nosym 287 MB、P10_subgroup_1_2 252 MB、P14 227 MB、P13 151 MB、
P08_subgroup_0_3 134 MB、4_2 119 MB、window Z2 108 MB。各组：uniqueness 48 个最大 0.3 MB；second encoding 最大 70 MB；fig12_retimings 最大 287 MB。
发布：≤ 100 MB 的 91 个证明以 xz 打包（810 MB → 195 MB），13 个大证明只给 sha256 + `check_proofs.py --regenerate unshipped`（约 2.5 CPU h）。

## (3b) 追加（lead 要求）：Table S3 只用长度 2 残余逻辑的 25 个实例——第二批

lead 的复核脚本 `research/audits/2026-10-14-revg-scripts/g4_len2only.py` 把 Table S3 的 CEGAR 帧模型限制在每侧 360 个
“十个数据列 + 一个长度 2 残余”逻辑上（SM S9 证明了这类逻辑的“模型提升 ⇒ 电路权重 11 不可检测”方向），25 行全部 UNSAT。
我写了发布包内的 `code/sat/len2only.py`（只包装 frame.prepare 过滤记录，CEGAR 驱动不动；过滤条件独立重写：恰一个残余且等于该校验最后两个 CNOT 目标），
`scripts/zenodo/build_len2only.py` 生成 `release/zenodo/certificates/fig12_retimings_len2only/`（25 × cnf.gz + log.json）。
- 25/25 CEGAR UNSAT，迭代数与保留记录数逐行等于 lead 独立运行（g4_len2only*.json）；生成共 12 CPU min（nosym 10 min）。
- 25/25 CaDiCaL UNSAT、drat-trim VERIFIED、cake_lpr VERIFIED UNSAT；0.5 CPU h；DRAT 合计 0.89 GB；最大 primary_P16_common_frame_nosym
  （619 781 子句，640 MB，求解 769 s、drat-trim 669 s、cake 65 s，不随包发，只给 sha256），其余 24 个 ≤ 80 MB 随包发。
- `code/check_certificates.py --family` 对该目录（≤ 200k 子句）全部 PASS、family alone SAT；快测加了 `len2only.py primary_P10_pipelined`（逐字节相同）。
- 合计：129/129 UNSAT，129/129 drat-trim VERIFIED，129/129 cake_lpr VERIFIED UNSAT，无超时；3.2 CPU h；DRAT 6.6 GB；随包 115 个（256 MB xz），14 个只给 sha256。
- 复现性：3 个不随包的大证明（P08_subgroup_0_3、4_2、window Z2）重新生成后 sha256 与记录相同；快测 4 个 lift 批也相同。

## (2) Lemma 2：lift 实例的 DRAT 证书

编码（`lift_cnf.py`）：与 SM S6 的 CP-SAT 模型相同——11 个像组的每个 DEM 机制一个变量，每组恰一（至少一子句 + 两两 / 梯子至多一），
每个被这些机制触及的探测器一条 XOR = 0（Tseitin 链，每段 ≤ 5 个文字）。同一 (电路, 基底, R) 的实例用选择子拼成析取：
`(t_1 ∨ … ∨ t_m)`，实例 i 的每条子句加 `¬t_i`，变量互不相交 ⇒ 批 CNF UNSAT ⇔ 批内无一提升。批数 K = max(1, ⌈R/2⌉)（每批 ≤ 2.65 M 子句）。
DEM 组用发布包里同一份 `gross12/ext.dem_groups`（含模板恒等式、像集 = 扩展码的检查）。

结果（全部 UNSAT、drat-trim VERIFIED、cake_lpr VERIFIED UNSAT）：
| 电路 | R | 基底 | 批 CNF | 实例 | CPU（解+两检查） | DRAT 合计 |
|---|---|---|---|---|---|---|
| A（定理 1） | 1–32 | Z, X | 544 | 270 336 = 4224×32×2 | 4.80 h | 40.7 GB |
| B | 1–24 | Z, X | 312 | 202 752 | 2.16 h | 22.7 GB |
| C | 1–14, 16 | Z, X | 128 | 126 720 | 0.95 h | 9.5 GB |
单个批证明 ≤ 87 MB，但总量 73 GB，只发 sha256（`lift_circuit_{A,B,C}.jsonl`）+ 重生脚本；快测重跑 A 的 R = 1, 2 四个批：CNF 与证明 sha256 都与记录**逐字节相同**（CaDiCaL 确定性）。
对照（`lift_control.py`）：Fig. 12、R = 1、两基底，4224/4224 单实例 CNF SAT，且每个模型解码出“每组一个机制、所有探测器和为零”的合法提升；
同一脚本对电路 A（Z、R = 1）给 0/4224 SAT。Fig. 12 R = 1 的批 CNF 也为 SAT（`lift_fig12/`）。
注意：证书只证明 CNF 不可满足；“CNF = lift 问题”依赖编码正确（对照 + 与 CP-SAT 同构）与 DEM 构造（Stim，SM S5 的检查）。

## (1) d_ext = 11 与 4224 列表的第三种方法：**SAT/DRAT 不可行（如实报告）**

编码（`dext_cnf.py`）：x_j（360 列），H 行 XOR = 0（Tseitin 链），L x ≠ 0（12 个奇偶定义 + 一条或子句），|x| ≤ w（Sinz 计数器）；
可选按轨道分情形（`--case K`，未使用）与阻断子句。第二种形式 `--data`：e = M x（每数据比特 = 覆盖它的列的 XOR），用码本身权重 6 的校验
（先核验 H_ext = H·M、L_ext = L·M：两基底 360/360 列成立；列支撑大小 1/2/3/4 各 144/72/72/72）。
CaDiCaL 标度（单核，Z 侧，墙钟）：
| w | 扩展码形式 | 数据比特形式 |
|---|---|---|
| 3 | 5.0 s | — |
| 4 | 39 s | 21 s |
| 5 | 182 s | 127 s |
| 6 | > 600 s（9 CPU min 未完，按 PID 停） | > 600 s |
每加一权重约 ×5–7 ⇒ w = 10 约 10^6–10^7 CPU 秒；按 24 元轨道分 15 种情形最多省 ~24 倍，仍远超 25 CPU h；DRAT 证明规模也会是 TB 级
（DFS 本身 2×10^10 节点）。CP-SAT（1 worker，`dext_cpsat.py`）w = 5 在 600 s 墙钟（384 CPU s）内 UNKNOWN。
w = 11 的“枚举 + 阻断 + 最终 UNSAT”更难，未尝试。**结论：d_ext = 11 与 4224 列表完备性仍只由两套独立 DFS（SM S4）支撑，没有 DRAT 证书；第三种方法本实验没有给出。**
可能的出路（未做）：带高斯消元 / BDD 证明的检查链（如 FRAT-XOR、pgbdd），需另批下载。

## 发布包修订（lead 第二条要求）

- “accompanied by a DRAT proof” 在 README 中精确定义：CNF 随包（lift 批由确定性编码器重生成并记 sha256）；≤ 100 MB 的证明随包，其余记 sha256/大小并可用脚本重生；所有检查日志随包（lift 984 批的日志合成 `logs/lift_circuit_{A,B,C}_logs.txt.gz`）。
- certify.py：cake_lpr 不存在时记录 `"cake_lpr": {"verdict": "not run"}`、输出 SKIP，不再当作通过；判定只看输出行 `s VERIFIED UNSAT`（cake_lpr 失败时退出码也是 0）。
  测试：不存在 → not run；假 cake（只打印注释、exit 0）→ FAILED、整体 FAIL；真 cake → VERIFIED UNSAT。run_quick 在缺 cake_lpr 时打印 SKIP 行。
- release/zenodo 下出现一个不属于发布设计的 `uv.lock`（20:04 生成，非我的命令所建，泄漏扫描因其中的日期失败），移到 scratchpad（未删）。

## 发布包（release/zenodo，`make_archive.sh` 泄漏扫描通过，tar.gz 230 MB、685 个文件）

- `code/proofs/`：certify.py、lift_cnf.py、run_lift_certs.py（`--compare` 比对 sha256）、lift_control.py、check_proofs.py（`--regenerate unshipped|all|NAME`）、build_tools.sh（固定提交号）。
- `certificates/proofs/`：certificates_proofs.jsonl、drat/*.drat.xz（91 个）、logs/（drat-trim、cake_lpr 输出）、lift_circuit_{A,B,C}.jsonl、lift_control.txt、TOOLS.txt。
- run_quick.sh：工具在则加跑 ≤ 2 MB 证明的 drat-trim 检查（68 个）、A 的 R = 1, 2 批、Fig. 12 对照；无工具打印 SKIP。重跑：**ALL PASS**，约 9 CPU min，输出存为 expected_output_quick.txt。
- run_full.sh：默认加 DRAT 段（约 12 CPU h，NO_PROOFS=1 跳过；缺工具时调用 build_tools.sh 下载编译）。
- README：§1 工具要求、§3 新增 `certificates/proofs/` 小节（覆盖表、最大证明表、(c) d_ext 不可行的说明）、§4/§5 脚本与耗时。MANIFEST.sha256 已重写。

## 建议论文措辞（供 lead 取舍）

- SM S10：“Every unsatisfiable clause set in the data set (129: the 104 optimality/uniqueness instances and the 25 Table S3 instances restricted
  to the proven direction) is accompanied by a DRAT proof produced by CaDiCaL 3.0.1 and verified with drat-trim; the LRAT core emitted by
  drat-trim was additionally verified with the formally verified checker cake_lpr (129/129, no timeouts).”
- SM S6：“For circuits A ($R\le32$), B ($R\le24$) and C ($R\le14$ and $16$), both bases and all 4224 logicals, the lift instances were encoded as CNF
  and refuted by CaDiCaL; each refutation is a DRAT proof verified with drat-trim (LRAT core verified with cake_lpr).”
- SM S4 / S11 必须保留限定：“$d_{\rm ext}=11$ and the completeness of the list rest on two independent exhaustive searches; we did not obtain a
  checkable proof certificate for them (a direct CNF encoding is beyond the reach of CDCL solvers already at weight 6).”
- 不能写“every computer-assisted step is DRAT-certified”；可写 “every infeasibility claim decided by a SAT or CP solver is accompanied by a DRAT proof verified with drat-trim”。

## CPU 用量（约）

part 3：2.67 h；lift 求解 + 检查：7.91 h；lift CNF 生成（Python，约 6.5 s/批 × 984 批）：约 1.8 h；d_ext 探测：约 0.55 h；
对照、篡改测试、工具编译、xz 打包、快测：约 0.4 h。合计约 13.3 CPU h；追加 len2-only 与修订约 1.0 CPU h，总计约 14.3 CPU h（≤ 25）。
