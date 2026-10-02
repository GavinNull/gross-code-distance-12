# 码 + 电路联合设计：竞争格局
检索日期：2026-10-02；检索词：co-design qLDPC code syndrome extraction circuit；joint search code and schedule circuit-level logical error rate；LLM / evolutionary / RL / Bayesian code discovery qLDPC；bivariate bicycle code search circuit-level；directional codes iSWAP；morphing circuits 2BGA；weight-6 thickness-2 BB new codes；teraquop / footprint 等（WebSearch + arXiv PDF 全文）。

## 读取方式与局限（先看）
- 以下 PDF 我从 arxiv.org/pdf/<编号> 下载到会话临时目录，用 pdftotext 转成全文后阅读。"精读"= 读了正文相关章节，不是逐页逐行。
- 2606.02418 v1：读了摘要、Sec. I–VII（含 Sec. IV.C 实验配置、Sec. VI.E–F 消融、Sec. VII 讨论）；附录只读了与噪声、FOM 相关的部分。
- 2607.25865 v1：PDF 共 12 页，主文全读。**文中反复引用的 Supplementary Information（SI A–D，含各码的 weight/连通度设定、pLER 精确定义 SI C、算力细节）不在这份 PDF 里，我没有读到。** 所以下面关于 OmniQEC 的"约束""算力"只能写主文所见，其余写"主文未给出"。
- 2604.09797 v2：读了摘要、Sec. 1、2.2.2、2.5（Prop. 1/3）、3.3、8 的相关段、App. C.4 与参考文献；Sec. 4–7、App. D–E（颜色码、泄漏、偏置噪声）只浏览了标题，未读。
- 2407.16336 v3：主文（含 Table I、Fig. 3、Outlook）和 App. A 数值方法读了；App. B–E 证明部分未读。
- 2506.03094 v1：读了 Sec. 1、2.1–2.7、4、App. A.7 与 A.10 的相关段；其余附录未读。
- 其它新找到的论文（2507.19430、2607.28795、2608.08996、2608.15754、2606.24808、2601.18562、2609.06572、2605.21898、2406.19151、2603.05481 等）我读了摘要，并对"circuit/schedule/noise/search/thickness/weight"做了全文定向检索和相关段落阅读，没有通读。
- ASC / AlphaSyndrome / PropHunt / FastSched 的数字沿用已有笔记 `novelty-schedule-search.md`、`novelty-interleaved-circuits.md`，今天没有重读。
- 检索靠搜索引擎，不是 arXiv 全库，"未找到"只代表我没搜到。

## 结论（3-5 行）
- **在"权重 ≤6、thickness ≤2、每个校验一个辅助比特的标准电路、以电路级逻辑错误率为目标、码与调度一起搜"这个设定下，我没有找到任何人做过。** 最接近的三条各缺一块：IBM 原文（2308.07915）先用码级代理筛码、只对入围码做电路级评估，调度固定；OmniQEC（2607.25865）以电路级 LER 为目标，但调度固定为边着色、不限 thickness、也没有把比特数按 k 归一；Strikis（2603.05481）只优化固定码的调度。
- 被点名的四篇精读结果：IBM 2606.02418 只搜码，目标是 kd²/n 与码容量噪声，完全没有电路；Shaw–Terhal 2604.09797 在 morphing 范式下搜 2BGA，目标是 end-cycle 码参数，**明确没有算电路距离，更没有算逻辑错误率**；Shaw–Terhal 2407.16336 不是搜索，是把 morphing 套到 IBM 已有的 BB 码列表上；OmniQEC 是唯一用电路级 LER 当目标的，但范式不同（见上）。
- 另有两条"码+电路一起设计"的路线与本设定不重合：Riverlane 的 directional codes（2507.19430，iSWAP 电路与码同时由方向序列定义，SI1000 下 LER 为目标）；Caltech/Oratomic 的 mitten codes（2607.28795，权重 9、thickness 3、非阿贝尔，管线含"码距离 + 电路距离"过滤和无 hook 调度搜索）。二者都不在 thickness ≤2 + 标准单辅助电路里。
- 竞争对手里**没有任何一个**把"每逻辑比特物理比特数"和 LER 一起作为搜索目标并与 gross code 做同口径比较；OmniQEC 的"在 N=240 超过 gross code"没有按 k 归一，其前沿上的码 k 多为 1–8（Fig. 2 标注），每逻辑比特比特数远高于 gross code 的 24，不能读成"省比特"。
- 对 gross code 本身，标准单辅助电路上限已被钉死：非交错电路 d_circ≤11（Strikis），IBM 调度 ≤10。想"超过 gross code"，要么换码（新码上的标准电路），要么换电路范式（morphing / 交错），后者已有 Shaw–Terhal 的 [[144,12,12]]（总比特同为 288，d_circ≤12）作为必须对照的点。

## 关键论文
| arXiv | 作者 · 年份 | 做了什么 | 与本项目关系 | 关键数字（附出处） |
|---|---|---|---|---|
| 2606.02418 | Cruz-Benito, Cross, Kremer, Faro（IBM）· 2026-06 | LLM 引导的进化搜索 BB / perturbed-BB 码；对照随机采样与 GA | 搜码方法对照；**不含电路** | 465 个码、约 1650 次迭代、约 2×10⁵ 候选、约 140 小时、约 400 美元（摘要；Sec. IV.C、Table I）；目标 FOM=kd²/n（Sec. III.C） |
| 2607.25865 | Yan 等 · 2026-07 | OmniQEC：LLM 编排，快环用码级代理、慢环用电路级 LER 反馈 | 唯一以电路级 LER 为搜索目标的竞争者 | N=98 起超过 BB[[72,12,6]]；Claude/GPT 在 N=240 超过 [[144,12,12]]（Sec. III.B，Fig. 2）；p=0.005、BP+OSD（Sec. III.A） |
| 2604.09797 | Shaw, Terhal · 2026（v2 04-20） | morphing 电路范式下搜 Abelian 2BGA 码（权重 5/6） | 最接近"码+电路联合"，但目标是码参数 | 搜索 w=5,n≤128 与 w=6,n≤64（Sec. 3.3）；"we did not check the circuit-level distance"（Sec. 3.3 末、App. C.4） |
| 2407.16336 | Shaw, Terhal · PRL 134, 090602 (2025) | 把 morphing 电路套到 IBM 的 BB 码，度 6→5 | 必须对照的"同总比特、d_circ=12"点 | Table I：[[288,12,18]] 的 end-cycle 码 [[144,12,12]]，d_circ≤12；标准 [[144,12,12]] d_circ≤10 |
| 2506.03094 | Yoder 等（IBM）· 2025-06 | Tour de gross：gross/two-gross 的逻辑指令集与整机资源估计 | 资源口径与外推方法的出处（详见 `resource-metrics.md`） | Table 4：gross d_circ≤10；Table 2 idle 10^-8.8（p=1e-3） |
| 2308.07915 | Bravyi 等（IBM）· 2023（Nature 627, 778） | BB 码、深度-7 单辅助电路、码搜索流程 | 现有"搜码"的最早做法；也是单辅助电路 baseline | Sec. 4–6：dBP 代理筛码→ILP 精确距离；936 个深度-7 变体全 d_circ≤10（Sec. 5） |
| 2507.19430 | Gehér, Byfield, Ruban（Riverlane）· 2025（v3 2026-07） | directional codes：iSWAP 电路同时定义码与测量电路 | 另一类"码+电路联合"，SI1000 下 LER 为准 | 同 LER 下比旋转环面码少用 1/4–1/3 物理比特（摘要，p=1e-3，Tesseract）；约 45 CPU-core-years（App. A 末） |
| 2607.28795 | Bhardwaj, Ma 等（Caltech/Oratomic）· 2026-07 | mitten codes：权重 9、非阿贝尔 LP；含"码距离+电路距离"过滤与 hook-free 调度搜索的发现管线 | 邻近：管线形态与本方向相似，但设定不同 | 权重 9；thickness 恰为 3（Sec. VI，Thm 15）；[[300,60,14]] 在 p=0.1% 下块 LER 9.5e-12/轮（摘要、Fig. 2a 说明） |
| 2603.05481 | Strikis, Browne, Beverland · 2026（v2 09-14） | left-right 电路与"残余错误距离"代理；固定码上优化调度 | gross code 上标准电路的天花板 | 证明非交错电路不能达 12，给出猜想 11 的电路（摘要）；单辅助设计上最多约一个数量级的 LER 改善（摘要） |
| 2608.08996 | Qian, Li · 2026-08 | 多 agent LLM 搜 coset-orbit balanced-product 码，n≤400、w≤10 | 只搜码，码容量噪声 | [[288,16,18]] (w=7)、[[288,18,18]] (w=9)、[[234,28,18]] (w=10)（摘要） |
| 2608.15754 | Sella, Pinsler, Heinis · 2026-08 | PPO 强化学习按固定解码器搜 BB 码 | 只搜码，码容量噪声 | 正文称评估用"simplistic code-capacity noise model"，电路级为"natural extension"（Discussion 段） |
| 2606.24808 | Liu, Marquardt · 2026-06 | LLM 结构化概念进化搜 LP 码 | 只搜码，码容量噪声 | Discussion 把"与电路级目标耦合"列为未来方向 |
| 2601.18562 | Chengyu 等 · 2026-01 | 贝叶斯优化 + 链复形神经嵌入预测 LER，搜 BB 码 | 只搜码，码容量噪声 | 摘要：发现 [[144,16]] 比 gross code 每比特错误率更低（码容量）；Discussion 称电路级为未来工作 |
| 2609.06572 | Lu, Yang, Guo · 2026-09 | 权重 8 BB 码的代数理论与精确距离搜索 | 邻近：权重 8、thickness 3，不在本设定 | [[144,6,d≥15]] 等（摘要）；电路级只做了 gross 对照的伪阈值（Sec. 6.2：约 0.1% vs 0.4%） |
| 2406.19151 | Voss 等 · 2024（v4 2025-02） | 三变量自行车码，权重 5；对 [[30,4,5]] 搜出深度-7、d_circ≤5 的电路 | 邻近：权重 ≤6、双平面、深度-7 电路与码一起给出，但先码后电路，非联合搜索 | 摘要：[[30,4,5]] 码 60 物理比特，深度-7 电路；Sec. II：d_circ≤5 |
| 2603.21499 / 2601.12509 / 2601.17580 / 2609.12020 | ASC / AlphaSyndrome / PropHunt / FastSched | 固定码上搜调度（SMT / MCTS / MaxSAT / RL） | 只搜调度；数字见已有笔记 | 见 `novelty-schedule-search.md` |

## 精读逐篇

### 1. IBM 2606.02418（LLM 搜 BB 码，对照随机 / GA）
- **搜索空间**：生成多项式对 (A,B) 的 Python 程序（ansatz），由 LLM 变异；CSS 三项式 BB（权重 6）、混合单项式与权重 8 的 CSS、以及非 CSS 的 perturbed-BB（PBB，多两个多项式 C,D）。块长 n≤360，格点包括 (12,6)、(12,12)、(15,12)、(24,6)、(30,6)、(16,9)、(18,8) 等（Sec. III、IV.B；摘要）。
- **约束**：权重（权重 6 的三项式、权重 8 的四项式）、n≤360（摘要）。**没有 thickness 约束，没有辅助比特数约束**；Sec. VII.b 只讨论了硬件可行性：König 边着色保证每类校验 6 轮、最坏深度 12，IBM 深度-7 电路来自 2308.07915；"PBB 的容错综合征提取电路仍是开放问题"。
- **目标函数**：FOM = kd²/n（Sec. III.C，动机是 BPT 界）。进化内环用"先算 k（F2 秩，精确），再用 BP-OSD 估计 d"的两级筛选；Campaign 4–5 在环内加了 MILP 精确距离（Sec. IV.B，Fig. 1）。逻辑错误率只在**码容量噪声**（X-only 与去极化，iid）下对少数已选码做 BP-OSD 模拟（Sec. VI 后部、Fig. 3 / Table VII），**没有任何电路级模拟**；Sec. VII.c 自己写明"circuit-level simulations are necessary to assess practical fault-tolerant performance"。
- **最好结果**：CSS 里新增 [[288,16,12]]（d=12 精确、不可分解，FOM=8.0）；再发现了 gross code（Campaign 4 用 6 种混合单项式表示重新发现）；非 CSS [[144,12,12]] PBB 与 gross code 的 FOM 持平（=12.0），并"不超过"（摘要、Sec. I 贡献 2、Sec. VI）。[[288,24,12]] 被 Tanner 图分析证明是两个 gross code 的直和。与本项目最相关的一句：权重 6 的间接结论是"高 k 低 d / 高 d 低 k"的速率–距离折中，作者未证明其为结构性约束（Sec. I）。
- **对照**：消融（Sec. VI.F）只用确定性指标 Σk（各格点最大 k 之和）：随机采样 Σk=299±26，LLM 704，GA-G 1037±22 但全是 d≤2 的码；作者承认没有控制评估次数（21.3 万 vs 1.4 万）。**不是 SA 对照**。
- **算力**：约 140 小时、约 400 美元 LLM 推理；Campaign 1–3 在单台 Apple M4 Max（36GB），Campaign 4–5 在 64 核服务器（251GB）（Sec. IV.C、Table I）。
- **BP-OSD 距离估计的可靠性**：高 k/n>0.1 的码上 BP-OSD 距离估计最多高估 12 倍，147/154 个码的上界被多解码器协议收紧（Sec. VI.E）。**这直接影响本项目：如果我们的搜索用 BP-OSD 估距离做过滤，必须有 MILP 或 sQetch 之类的复核。**

### 2. OmniQEC 2607.25865
- **搜索空间**：四个 qLDPC 族：BB、三变量（TB）、提升积（LP）、广义 LP（GLP）；码由 LLM 生成的"构造程序 + 可调参数 + 20 个随机种子"实例化（Sec. II.B、III.A）。
- **约束**：总物理比特预算 N（数据 + 辅助，N=20 到 288 共 14 档，Sec. III.A）；用户可指定权重上限、连通度、原生门、辅助比特资源（Fig. 1 图注、Sec. II.A），**但主文没有给出实验里用的权重/thickness 数值**，SI 未读到。BB 参照码要求 N=144（[[72,12,6]]）和 N=288（[[144,12,12]]）（Sec. III.A）。
- **目标函数**：快环用 kd²/n 等码级代理筛选；慢环把码编译成综合征电路，用 Stim + BP+OSD 估计**每轮每逻辑比特**的逻辑错误率 pLER，p=0.005 下评估（Sec. II.A、III.A）。直接以电路级 LER 为排序依据（"directly optimizing the circuit-level LER"，Sec. I）。
- **电路 / 调度**：Tanner 图**边着色**得到无冲突层，编译成 Stim 电路；"circuit-synthesis"模块返回深度与双比特门数作为反馈（Sec. II.B）。**调度不是搜索对象**；Discussion 把"自适应调度、flag 比特摆放"列为未来方向。
- **最好结果**：三个 LLM 后端的前沿 pLER 近似随 N 指数下降；所有后端从 N=98 起超过 BB[[72,12,6]]；GPT 与 Claude（Opus 4.8）在 N=240 超过 [[144,12,12]]，DeepSeek 不行（Sec. III.B，Fig. 2）。代表码：[[48,4,8]]（GPT、DeepSeek）、[[58,2,7]]（Claude），LER 缩放指数 Γ=5.20、5.57、5.60，对比 BB[[72,12,6]] 的 Γ=3.79；在 p=0.002 时最强候选比 BB[[72,12,6]] 低 29.23 倍，p=0.01 时低 1.66 倍（Sec. III.C，p∈[0.002,0.01]）。top-5 最终平均 −log10 pLER = 4.61±0.54（Claude）/5.17±0.09（GPT）/4.07±0.28（DeepSeek）（Sec. III.D；对应的 N 与 p 主文未逐一说明）。**N=240 处超过 gross code 的那个码的参数与具体 pLER 数值：主文只画在 Fig. 2 里，文字未给出，未找到。**
- **对本项目的关键细节**：（a）Fig. 2 纵轴是每逻辑比特每轮 pLER，横轴是总比特数 N，**没有把 N 除以 k**；图中标注的前沿码（如 [[48,4,8]]、[[58,2,7]]、[[72,4,10]]、[[144,4,16]]、[[144,8,12]] 等）k 为 1–8，而 gross code k=12，N/k=24。所以"同 N 下 pLER 更低"不等于"每逻辑比特更省"。（b）文中自己指出 Φ=kd²/n 与电路级排序"不总是一致"：N=144 处最佳码的 Φ 仅 2.25 / 5.56 / 3.36，却都在电路级超过 BB 参照（Sec. III.B）。这是支持"用电路级目标"的证据，也说明纯码级 FOM 筛选会漏掉好码。（c）消融（Fig. 3d–f）只比较完整流程、去掉慢环、去掉全部反馈三种，没有随机搜索 / SA 对照。
- **算力**：LLM 侧：每个预算 T=60 轮、每轮 24 个程序、每程序 20 个种子（至多 480 个候选实例/轮）；Fig. 4 的坐标轴显示 token 用量上限约 1.6M、费用上限约 16 美元（只从坐标轴读到，粗略）。电路模拟的 CPU/GPU 时间：**主文未给出**（可能在 SI，未读到）。

### 3. Shaw–Terhal 2604.09797（morphing 范式下联合优化 2BGA 码与电路）
- **搜索空间**：mid-cycle 码取 Abelian 2BGA（含 BB、环面码、颜色码），用格点表示 Λ⊆Z^{w−2} 去重；对每个码再枚举"两轮、同态型、纯收缩的 morphing 电路"（收缩树图，Sec. 3.2–3.3，App. C.3）。搜索范围：权重 5 且 n≤128，权重 6 且 n≤64（Sec. 3.3）。
- **约束**：稳定子权重 w∈{5,6}；morphing 电路连通度为 w−1；用同态型两轮电路（要求群 G 为偶数阶，App. C.3.1 末）；只比较"最小码"（没有 n'<n,k'>k,d'>d 的码）（Sec. 3.3）。
- **目标函数**：**end-cycle 码的 [[n_end,k,d_end]] 与连通度**；物理比特总数为 2n_end（morphing 与 bare-ancilla 同口径）。电路距离只给了上界 d_circ≤min(d,d_end)。原文：「we did not check the circuit-level distance of the bare-ancilla or the morphing circuits. We leave it to future work to investigate particular codes and/or circuits of interest」（App. C.4）；Sec. 3.3 也有同样的说明。**没有 LER 目标，没有电路级模拟。**
- **最好结果**：Fig. 11（k=8）与 Fig. 25–26（k≤12，及 d=3,4 的大 k）显示：权重 w 的 morphing 电路（连通度 w−1）的最小 end-cycle 码参数"consistently beat, or at least match" 同权重 bare-ancilla 码（App. C.4）。**具体数值只在图里，文字没有表格，未找到可引用的单个码参数。** Sec. 1 要点 1 声称"首次系统地证明 morphing 能严格改进码参数"。另一个与本项目相关的结果是 Prop. 1 / Prop. 3：两轮 morphing 与"交替时间反演"电路的 d_circ 可由单轮电路算出，且交替电路 d_circ 不低于非交替（Sec. 2.2.2、2.5）。这些命题的示例只给了环面码/表面码；BB 码上的具体数值我没有在文中找到。
- **算力**：搜索算力：**未找到**。致谢里只写用 DelftBlue 超算"for running the decoding"（Acknowledgements），与颜色码/稳定性实验的模拟有关。
- 作者自己点出的空白：「holy grail」是对给定 mid-cycle 码自动搜索不同连通度的 morphing 电路（Sec. 8）。

### 4. Shaw–Terhal 2407.16336（BB 码的 morphing，度 6→5）
- **不是搜索。** 搜索空间 = IBM Table 3 里的 5 个 BB 码；判据 Criterion 1（是否存在满足条件的同态 f_x/f_y/f_xy）。Table I：[[72,12,6]]、[[144,12,12]]、[[288,12,18]] 对 f_x、f_y、f_xy 都存在；[[108,8,10]] 只有 f_y；[[90,8,10]] 不在该表（我看到的表只有 4 行，注意核对）。
- **约束**：保持双平面布局（biplanar，App. 中证明）、连通度 5（而不是 6）、end-cycle 码稳定子权重变为 9（正文）。
- **目标函数**：无优化目标；报告 end-cycle 码参数、d_circ 的 BP-OSD 上界（p=1e-4，OSD order 100，BP 100 次；见 App. A）和 Fig. 3 的每轮 LER-p 曲线（SD6 型均匀去极化噪声、BP-OSD）。
- **最好结果**：Table I：[[288,12,18]] 的 morphing 电路，end-cycle 码为 [[144,12,12]]，d_circ≤12（对比标准 [[144,12,12]] 的 d_circ≤10）；表注明确"n 在 morphing 下包含数据与辅助比特"，所以总比特 288，与 gross code 相同。Fig. 3 的文字结论：当 BB 码与 end-cycle 码参数一致时两者性能"similar"。正文还说明：该 end-cycle 码是"another gross code"。
- **算力**：DelftBlue 解码，核时**未找到**。
- **逻辑操作**：正文给出了与表面码做逻辑 I/O 的 biplanar 构造（Logical Operations 段），这是 morphing 路线对"逻辑操作"问题的回应；但没有 LPU/测量的资源数字。

### 5. 其它按设定分类的"联合"工作（精读摘要 + 全文检索）
- **Directional codes（2507.19430）**：搜索空间 = 方向序列（长度 4–7 全枚举，加上权重 8 的 N²E⁴N²）与平行四边形 (v1,v2) 决定的扭曲环面；一个方向序列同时给出码和 iSWAP 测量电路（Table 2、App. A）。约束：方格/六角格连通、权重 ≤8。目标：SI1000 噪声、p=1e-3 下用 Tesseract 解码的 LER；用"拟合 log pL 对 √n_ph 的直线，取斜率平方比"换算成与旋转环面码等 LER 所需比特比（App. C.1，式 (55)–(57)）。最好结果：同 LER 只需旋转环面码的 1/4–1/3 物理比特（摘要、Table 1，旋转 N²E³N² 族 29.2%）。算力：约 45 CPU-core-years（App. A 末，含初始探索）。**不在本设定**：iSWAP 电路、环面、不是"每校验一个辅助 + CNOT 标准电路"，但它是"以电路级 LER 与比特数比为目标、码与电路一起定义"的最清楚先例。
- **Mitten codes（2607.28795）**：管线（Sec. VII、App. F）：先用理论界过滤，再用 GPU 距离估计器 sQetch 暴搜；"filters codes by their check weight, code distance, and circuit-level distance"；对幸存码"searching via sQetch for schedules that likely preserve the circuit-level distance"（hook-error-free）；最后才做完整电路级模拟（App. F）。权重 9，thickness 恰为 3（Sec. VI）。所以**调度搜索与码搜索在管线里是串联的，目标是距离而不是 LER**，且不在 thickness ≤2。另：管线要求"square-invertibility"以保证有低权重的规范逻辑基，即**把逻辑操作的可实现性写进了码的筛选条件**（App. F），对本项目的逻辑操作问题有参考价值（见 `resource-metrics.md`）。
- **Strikis 等 2603.05481**：固定码，优化调度（left-right 电路，用"残余错误距离"代理）；对 gross code 证明非交错 d_circ≤11、猜想 11 的电路（摘要）。不搜码。
- **Voss 等 2406.19151**：权重 5 的 TB 码 [[30,4,5]]。先选码；再对电路做了搜索（"We searched for better constructions"，Sec. II）：朴素顺序电路深度 10、d_circ≤4；沿用 IBM 权重 6 电路去掉第六个校验得 d_circ≤4；他们的深度-7 电路 d_circ≤5（作者认为紧，Fig. 1b、Sec. II.A）。这是"权重 ≤6、双平面、深度 7、d_circ=d"的一个小例子，但码在前、调度在后，不是联合搜索，也不以 LER 为目标。

## 竞争格局总表
| 工作 | 搜索空间 | 约束 | 目标 | 最好结果 | 是否联合优化调度 |
|---|---|---|---|---|---|
| IBM 2308.07915 | BB 码 (A,B 三项式)，n=O(100) | 权重 6、thickness ≤2、单辅助、深度 7 | 码级代理 dBP 筛选 → ILP 精确 d；入围码再做电路级 LER（Table 1） | [[144,12,12]] pL(1e-3)=2e-7、[[288,12,18]] 2e-12（Table 1，外推） | 否（调度固定；对 gross code 试了 936 个深度-7 变体，全 ≤10，Sec. 5） |
| IBM 2606.02418 | BB / PBB 码程序（LLM 进化） | 权重 6 / 8，n≤360 | FOM=kd²/n（码级），码容量 LER 事后验证 | [[288,16,12]]；重新发现 gross code；PBB [[144,12,12]] 持平 | 否，完全不涉电路 |
| OmniQEC 2607.25865 | BB/TB/LP/GLP 构造程序 | 总比特 N≤288；权重、thickness 主文未给出 | 电路级 pLER（p=0.005，BP+OSD）；快环 FOM 仅作筛选 | N=98 超 [[72,12,6]]；N=240 超 [[144,12,12]]；k≤8 的小码为主 | 否（边着色，固定） |
| Shaw–Terhal 2604.09797 | Abelian 2BGA 码 × 两轮 morphing 收缩树 | w=5,n≤128；w=6,n≤64；连通度 w−1 | end-cycle 码 [[n,k,d]] 与连通度 | 同权重下参数优于/持平 bare-ancilla（图） | 是（morphing 电路本身随码一起选），但无 LER/d_circ |
| Shaw–Terhal 2407.16336 | IBM 的 BB 码列表 | 双平面、度 5 | 无（报告 d_circ 上界与 LER 曲线） | end-cycle [[144,12,12]]，d_circ≤12，总比特 288 | 电路族不同（morphing），非搜索 |
| Strikis 2603.05481 | 固定码上的左右电路 | 单辅助、非交错 | 残余错误距离等代理 → d_circ / LER | gross code：非交错 ≤11，猜想 11 | 只搜调度，不搜码 |
| ASC / AlphaSyndrome / PropHunt / FastSched | 固定码上的调度 | 深度或 LER | 深度、LER | 见已有笔记 | 只搜调度 |
| Directional codes 2507.19430 | 方向序列 × 平行四边形 | 方格/六角格，权重 ≤8 | SI1000、p=1e-3 的 LER 与"等 LER 比特比" | 比旋转环面码少 3/4–2/3 比特 | 是（码与 iSWAP 电路同源），但不是 CNOT 标准电路 |
| Mitten 2607.28795 | 非阿贝尔 LP 码 | 权重 9，thickness 3 | 距离 + 电路距离过滤；LER 仅做验证 | [[300,60,14]]，块 LER 9.5×10⁻¹²/轮 @p=0.1%（摘要、Sec. III 起的 Fig. 2a 说明） | 是（hook-free 调度搜索，串联） |
| 其它搜码工作（2608.08996、2608.15754、2606.24808、2601.18562、2609.06572） | 各族码 | n≤400、w≤10 等 | 码级参数或码容量 LER | 见上表 | 否 |

## 新颖性判断

**问题：在"权重 ≤6、thickness ≤2、每校验一个辅助比特的标准电路"设定下，以电路级逻辑错误率为目标的码+电路联合搜索，谁做过？**

- **有没有人做过完全相同的事？** 未找到。
- **最接近的几篇，各差在哪：**
  1. IBM 2308.07915：码搜索是"dBP 代理 → ILP 精确距离 → 入围码的电路级模拟"，电路是一个固定深度-7 模板，只对 gross code 试了 936 个同深度变体（Sec. 5、6）。差别：电路级 LER 不是搜索目标，调度不是搜索变量。
  2. OmniQEC 2607.25865：电路级 LER 是目标（p=0.005），但调度固定为边着色（深度远大于 7），权重/thickness 约束主文未给，不按 k 归一。差别：调度非搜索变量；约束集不同；比较口径不同；它的"超过 gross code"在 N 上比、不在 N/k 上比。
  3. Strikis 2603.05481：固定码上做调度优化，已证明 gross code 的非交错上限 11。差别：不搜码，也没有 gross 以外的 BB 码的 d_circ/LER 扫描（据已有笔记）。
  4. Shaw–Terhal 2604.09797：码与（morphing）电路一起搜，但目标是码参数，且明确未算 d_circ；设定不是单辅助 CNOT 电路。
- **做到哪一步：** 码级搜索已经很拥挤（IBM LLM 进化、多 agent、RL、贝叶斯优化、精确枚举）；电路级 LER 当目标只有 OmniQEC 一家；调度搜索已有 MCTS / MaxSAT / SMT / RL 四家（固定码）；"两者一起、在 thickness ≤2 标准电路里"没有人。
- **剩下的空白（按可做程度排）：**
  1. **在权重 6、thickness 2 的 BB（及 coprime / 2BGA）码族里，按 (每逻辑比特物理比特数, 电路级 LER) 做帕累托搜索，并让每个候选码带上自己的好调度**（至少是"左右电路 / 交错 / 深度-7 变体"的小搜索，而不是固定边着色）。目前没有人给出"其它 BB 码在最好调度下 d_circ/LER 如何"的系统扫描（IBM 只报了 5 个码的一个调度）。
  2. **gross 以外的码 d_circ=d 的可能性**：[[288,12,18]] 的标准电路 d_circ≤18（IBM Table 1、Tour de gross Table 4）已经等于码距离，说明 d_circ 缺口并非所有 BB 码都有；缺口大的是 gross（≤10 vs 12）。如果新码本身就带 d_circ=d，则不需要电路创新就能在 (Q, LER) 平面上占点，这是搜码里最可能出结果的地方。
  3. **k 归一与同口径比较**：OmniQEC 没做；directional codes 做了但对象不同。
  4. **跨范式的合理基线**：Shaw–Terhal [[144,12,12]] morphing（Q=24，d_circ≤12）是现成的对手点；Wills 等 2605.21898 App. C 对"用 morphing 的 gross code idle 电路"直接蒙特卡洛得到 4.4×10⁻¹¹/轮（p=1e-3，95% 区间 9.2×10⁻¹²–1.3×10⁻¹⁰，Table 5），对比 Tour de gross Table 2 的 10^-8.8（约 1.6×10⁻⁹）。**两处数字的口径（解码器、归一）是否完全一致我没有核对。** 若成立，这个点比"Strikis d_circ=11 电路"更强，H-003 不能把后者当唯一对照。
- **证据强度：中等偏低。** 理由：靠搜索引擎，不是全库检索；OmniQEC 的 SI 未读（权重/thickness 约束可能在 SI 里）；2604.09797 的 Sec. 4–7 未读；Directional codes 与 Mitten 只读了相关段。

## 对本项目的建议
1. **H-003 的新颖性主张应收窄为**："在 thickness ≤2、权重 ≤6、单辅助标准电路内，按 (Q=总比特/k, 每逻辑比特每轮 LER) 搜索，并报告每个入围码在多种调度下的结果"。不要写成"首个电路级 LER 目标的码搜索"，OmniQEC 已经做了。
2. **必须对照的点（至少四个）**：gross + IBM 深度-7（Tour de gross Table 2）；gross + Strikis 11 电路（E-003 复现）；Shaw–Terhal morphing 的 [[144,12,12]]（Q=24）；[[288,12,18]]（Q=48）。再加 OmniQEC 公布的最好码（如果 SI/代码可得，则同口径重跑）。
3. **码级过滤别只靠 BP-OSD 距离**：IBM 自己的 2606.02418 显示 BP-OSD 对高 k/n 码高估距离最多 12 倍（Sec. VI.E）；至少对入围码用 MILP / 精确法复核。
4. **别拿 OmniQEC 的"同 N"结论当先例**：我们的指标必须按 k 归一，否则 k=2–4 的小码会"赢"。
5. 动手前补读：OmniQEC SI（A–D）；2604.09797 Sec. 4–7；Wills 2605.21898 App. C 的 morphing idle 电路到底用哪个 [[144,12,12]]、总比特多少；Strikis 对 gross 以外的 BB 码（[[72,12,6]]、[[108,8,10]]、[[288,12,18]]）的 d_circ 数字。
