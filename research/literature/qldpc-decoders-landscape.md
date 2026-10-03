# qLDPC / BB 码电路级解码器竞争格局（H-005 新颖性与切入点）
检索日期：2026-10-03；检索词：Relay-BP、BP+LSD、ambiguity clustering、BP+OTF、decision-tree decoder、beam search decoder、Tesseract、Cascade、AlphaQubit 2、neural decoder bivariate bicycle、BP-OSD vs maximum likelihood、AlphaEvolve / FunSearch / OpenEvolve decoder、evolutionary BP、RL BP scheduling。

读取范围声明：以下论文我把 PDF 转成文本后读了正文相关段落（不是只看摘要）：2506.01779、2510.21600、2406.18655（BB 码部分、附录 C.3/C.4）、2406.14527（摘要与性能对比段）、2409.01440（BB 码与计时段）、2504.13043、2604.08358、2503.10988（摘要、结果段、附录 A）、2502.16408（引言与结果概述，未读第 5、6 节细节）、2512.07057（引言与结果段）、2607.28795（telescoping 解码器相关节与附录 I 的对比段）、2502.19971 与 2509.22347（BB 码结果段）、2511.13281（引言与实验设定，未读结果图表）、2512.18273 与 2607.20130（摘要、噪声设定、结论）。**只读到摘要或搜索摘要的**：2408.07038（Astra）、HAMLD（PRResearch，找不到 arXiv 编号）、2606.14455、2605.17230、2603.19062；BP-GD / SI 等只是在 2512.07057 引言里被提及，未读原文。原 AlphaQubit（Nature 2024，DOI 10.1038/s41586-024-08148-8）正文未读。WebFetch 对 PDF 不直接返回正文，我用的是工具落盘的 PDF 加 pdftotext；图中曲线上的数值没有提取，凡只在图里的数字一律写“图中，未提取”。

## 结论（3-5 行）
- **BB 码电路级解码的 SOTA 已经不是 BP-OSD。** 2026 年中期最强的两条线是：（a）BP/Relay-BP 多级级联、末级用整数规划精确求最可能错误（telescoping，2607.28795）；（b）卷积神经解码器 Cascade（2604.08358）。二者在 gross code、p=0.1% 下都落在约 1e-10 量级（telescoping 6.7e-11 每轮每逻辑比特），与 Tesseract（近似最可能错误解码）在误差棒内一致。Cascade 自报比 BP-OSD 低约 4000 倍、比 Relay-BP 低约 17 倍。以上都是预印本自报，我没有找到独立复现。
- **“离近最优多远”已被量化，但量化是零散的、而且口径不一。** Tesseract 论文（2503.10988）明确说此前没人详细研究过 BP-OSD 相对近最优解码的差距，并报告 BB 码上差一到两个数量级；Cascade 与 telescoping 把 p=0.1% 下的差距推到 gross code 的真实量级。差距随 p 减小而变大。**尚未找到“真正最大似然（含简并）”在 gross code 电路级噪声下的结果**，现有“近最优”都是最可能错误（MLE）而不是 ML。
- **AI 发现解码启发式（LLM / AlphaEvolve / FunSearch 写解码算法）：未找到。** 最近的是：差分进化优化 BP 权重（2512.18273，仅码容量噪声）、强化学习学 BP 调度（2607.20130，仅去极化信道）、IBM 的 OpenEvolve（2606.02418）和 OmniQEC（2607.25865），后两者进化的是码而不是解码器。
- **空白与风险并存。** 空白是“在电路级噪声下，用搜索自动发现可硬件化的 BP 类启发式”。但这个位置已经被两股力量夹住：IBM Relay-BP 已经把“人工设计 BP 变体”做到了 FPGA，神经解码器已经把精度推到近最优。要有影响力，AI 发现的启发式必须在精度上追近 Tesseract 级、同时保持 BP 级速度，否则打不过 telescoping。

## 关键论文

### 1. 现有 qLDPC 电路级解码器（BB 码，电路级噪声）
“相对 BP-OSD”一列的基线设置各论文不同，已注明。LER 一列只写正文给出的数；只在图里的写“图中”。

| arXiv | 作者 · 年份 | 做了什么 | 关键数字（附出处） | 相对 BP-OSD | 速度 | 开源 |
|---|---|---|---|---|---|---|
| 1904.02703；2005.07016 | Panteleev-Kalachev 2019；Roffe et al. 2020 | BP-OSD 及软件实现，基线 | 本笔记不重复；IBM 原文 gross code p=1e-3 每块 LER 2e-7（外推），见 `resource-metrics.md` 第 16 行，本次未重读 2308.07915 | 基线 | OSD 全局矩阵求逆，最坏立方复杂度（2406.18655 附录 C.3） | 是（ldpc 包） |
| 2406.18655 | Hillmann, Berent, …, Roffe · 2024（Nat. Commun. 16, 8214 per 搜索结果） | BP+LSD：BP 软信息引导的并行局部聚类，按簇做在线 PLU 求解 | BB 码 [[72,12,6]]、[[108,8,10]]、[[144,12,12]]、[[288,12,18]]，d 轮、全历史一次解码，电路级噪声，Fig. 6；BP+LSD-0 与 IBM 文中 BP+OSD-CS-7 “comparable”，最多 30 次 BP 迭代 vs 10000（附录 C.3）。具体 LER 在图中，未提取 | 精度持平，无提升（2512.07057 引言也如此评价） | 次阈值区 LSD 后处理远比 OSD 便宜；p=0.1% 下 [[144,12,12]] 计时见 Fig. 8、9，具体倍数未提取；尾部延迟可到均值两个数量级以上（2512.07057 引言引 Fig. 9 of 2406.18655） | 正文称原型开源实现（附录 C.4），仓库地址未核实 |
| 2406.14527 | Wolanski, Barber（Riverlane）· 2024，v2 2025-01 | BP+AC：BP 后把数据分成可独立解码的簇，簇内做最大似然搜索 | 配置到与 IBM 文中 BP-OSD 数据精度匹配（Fig. 3，p=0.3%，[[288,12,18]] 用 0.35%）；gross code 135 µs/轮，单核 M2（摘要、Performance comparison 段） | 精度持平 | 比 BP-OSD 快 6× 到 27×，gross code 25×（同上，Roffe 的 BP-OSD 为基准） | C++ 实现，开源与否正文未说明，未找到 |
| 2409.01440 | iOlius, Martinez, Roffe, Martinez · 2024，v3 2026-06 | BP+OTF：在稀疏化后的有序 Tanner 森林上做后处理，近线性复杂度 | BB 码 [[72,12,6]] 到 [[360,12,24]]，Fig. 3：与 BP+OSD-0 持平；最多 617 次 BP 迭代；p=0.003、0.004 的平均每轮时间 Fig. 4，Sec. IV.A | 持平 | >10×（均值，BP 实现是串行的，作者称实际复杂度为二次） | 是，github.com/Ima96/BPOTF（Code availability 段；集成版尚未放出） |
| 2506.01779 | Müller, …, Johnson（IBM）· 2025，v2 2025-08 | Relay-BP：多段 BP，各段用不同的“无序记忆强度”（含负值），段间传递边缘信息 | gross code、two-gross [[288,12,18]]，d 个噪声轮加 1 个完美轮，p/15 双比特去极化电路噪声（附录）；p=3e-3：Relay-BP-5（XZ 解码）约低 1 个数量级，XYZ-Relay-BP-5 约低 2 个数量级（Fig. 2 说明文字与正文）。Ensemble 对照：Relay 7±1e-6，独立重启 1.4±0.2e-5（正文）。**没有 [[72,12,6]] 结果** | 10× 到 100×，基线是 BP+OSD+CS-10、10000 次 BP（Fig. 2 段） | 30 次迭代内 Relay-BP-1 比“高资源”BP+OSD+CS-10 低约 3×（Fig. 3 段）；估计 20 ns/迭代下约 600 次迭代可实时（Real-time decoding 段） | 是，github.com/trmue/relay（参考文献 [45]） |
| 2510.21600 | Maurer, …, Johnson（IBM）· 2025 | Relay-BP 的 FPGA 原型，gross code XZ 解码 | AMD VU19P，int4，24 ns/迭代，占用一半以上 LUT（摘要、资源段）。平均迭代数：引言写 p<1e-3 时 <10 次（12 周期窗口 <240 ns），结论写 p=1e-3 时约 20 次（窗口 480 ns，每周期 40 ns）。**两处口径不一致，我没有查清原因** | 精度与浮点 Relay-BP 一致（摘要） | 摘要：p≤3e-3 时平均每周期 <1 µs | 参考实现 github.com/trmue/relay（脚注） |
| 2502.16408 | Ott, Hetényi, Beverland（IBM）· 2025 | Decision-tree decoders：可证明最小权重版（height-bound DTD）与启发式 BP-DTD | gross code p=1e-3，截止时间曲线 Fig. 3：中间时间段 BP-DTD 的 LER 明显低于 BP-OSD，数值在图中。height-bound DTD 对权重 w 的故障中位数只探索 w 个节点（Fig. 2） | “显著更低”（时限敏感场景） | 时限敏感场景更快，倍数未给 | 正文未见代码链接，未找到 |
| 2512.07057 | Ye, Wecker, Delfosse（IonQ）· 2025 | BP 引导的束搜索解码器 | gross code，p=1e-3，电路级：最强配置 beam64_32res 比 BP-OSD LER 低 17×；beam32 低 5.6×；beam8 LER 持平（摘要，Fig. 2 段）。p=5e-4 beam32：平均 270 µs/轮，99.9 分位 940 µs（引言） | 最高 17×。基线弱于 IBM：30 次 min-sum BP 加 CS-10 OSD（Results 段） | beam8 同精度下 99.9 分位快 26.2×、均值快 4.6×；单核 Apple M3 Pro（Tables II、III） | 是，github.com/ionq-publications/BeamSearchDecoder |
| 2511.13281 | Valentini, …, Chiani · 2025 | Restart Belief：按最小 LLR 分支重启 BP | 自称“最快且最准”的 QLDPC 解码器（摘要）。我读到的实验图是去极化信道，没有看到电路级模拟，**判断为码容量级别，未核实**；正文未读结果表 | 未核实 | 未核实 | github.com/DiegoForlivesi/QBelief（参考文献 [20]） |
| 2607.28795 | Bhardwaj, Ma, …, Huang（Caltech/Oratomic）· 2026 | telescoping 解码器：GPU 上多级 BP 与 Relay-BP，CPU 上串行 BP/Relay，最后一级用整数规划（Gurobi）精确求 MLE | gross code，uniform 去极化电路噪声，p=0.1%：每轮每逻辑比特 6.7(+3.3,−2.4)e-11（95% CI），p=0.2%：1.3(+0.4,−0.3)e-8（附录 I.2，Fig. 9，Table IX）。与 Tesseract 在误差棒内一致、低于 Cascade | 本文未直接比 BP-OSD，借用 2604.08358 的数据，对比段称“match or improve” | 5.5 至 6.2 µs 每周期（H100 加单 CPU 核，同上） | 正文未见代码链接，未找到 |

### 2. 神经网络解码器（BB 码）

| arXiv | 作者 · 年份 | 做了什么 | 关键数字（附出处） | 相对 BP-OSD | 速度 | 开源 |
|---|---|---|---|---|---|---|
| 2504.13043 | Blue, …, Chuang（MIT）· 2025，Quantum 2026 录用 | 循环 transformer，code-aware 自注意力，自回归输出逻辑类 | [[72,12,6]]，6 个噪声轮，p=0.1%：LER 比 BP-OSD-3 低约 4.5×，比最可能错误（整数规划，Tesseract 论文的 IP 解码器）高 5.4×（Sec. 1.3，Fig. 1a）。[[144,12,12]]：p=0.3% 到 0.7% 与 BP-OSD-3 相近，p=0.1% 时 LER 约高 7×（Sec. 1.3，Fig. 3a） | 72 码好 4.5×；144 码在低 p 差 7× | 与 BP-OSD-0 均值相当，比其最坏情况快一个数量级（72 码）；144 码 p=0.1% 比 BP-OSD-0 均值快一个数量级以上，A100，batch 1（Fig. 1b、3b） | 正文未见代码链接，未找到 |
| 2502.19971 | Hu, …, Zhong · 2025 | GraphQEC，在扩展 Tanner 图上的时序图分类，号称码无关 | BB [[72,12,6]]、[[144,12,12]]，uniform 去极化电路级模拟，p=0.005：相对 BP-OSD 最多低 94.6%（Table 1，未区分是哪个码）；144 码在更低 p 下压制率“超过 99%”（Fig. 2C 段） | 见左 | 线性复杂度，相对 BP-OSD 快（Fig. 4，倍数未提取） | 是，github.com/Fadelis98/graphqecpaper（脚注） |
| 2509.22347 | Liu, Gong, Clark · 2025 | 掩码扩散解码器 | [[72,12,6]]、[[144,12,12]]，d 轮电路级：LER 总体低于 BP-OSD，但 144 码在 p=0.001 “effectively tied”；BP-OSD 用 CUDA-Q、1000 次迭代（Sec. 总结与附录） | 持平到略好 | 最坏情况始终远快于 BP-OSD | 未找到 |
| 2604.08358 | Gu, Bonilla Ataides, Lukin, Yelin（Harvard）· 2026 | Cascade：利用 BB 码环面平移对称的卷积网络，学习式消息传递 | gross code，电路级去极化，R=d 轮，p=0.1%：比 BP-OSD 低约 4000×，比 Relay 低约 17×，与 Tesseract 精度相当；p=0.1% 时约 1e-10，最低测到 2e-11；p=0.2% 时 [[288,12,18]] 约 1e-10（正文 Error suppression 段，Fig. 1b、2）。拟合：BP-OSD 约 p^5.4；Cascade 陡峭项约 p^10.8，距离限制项约 p^6.4（Fig. 1b 说明）。基线设置：BP-OSD 为 stimbposd 默认（30 次迭代、CS-60），Relay 按作者推荐调参，Tesseract 用 short-beam（参考 [44]） | 4000×（基线较弱：30 次迭代） | 单次延迟约 40 µs/周期（H200）；批处理摊销后吞吐比单线程 CPU 解码器高 3000 到 100000×；达不到超导 1 µs 要求（Speed 段） | 数据“按需提供”，未见代码链接（Data Availability） |

### 3. 其他相关
- AlphaQubit 2（2512.07737，Senior et al. 2026，Google DeepMind）：摘要只涉及 surface code 与 color code，近最优、可 <1 µs/周期实时。正文相关工作段把 qLDPC 神经解码列为他人工作（Sec. 3.1，引 [13,20]）。**结论：AlphaQubit 系列没有用于 qLDPC（据我读到的部分）**。原 AlphaQubit（Nature 2024）正文未读，此点对原版是依据本项目 `refs-verified.md` 与背景知识，未重新核对。
- Astra（2408.07038，Maan, Paler；npj QI 2025）：GNN 学消息传递，摘要称“无后处理即优于 BP+OSD”，BB 码训练到 d=18；**只读到摘要，噪声模型（码容量还是电路级）未核实，不能作为电路级证据**。仓库 github.com/arshpreetmaan/astra（来自搜索结果摘要，未核实）。
- HAMLD（Phys. Rev. Research，2026-05-20，搜索摘要）：近似 ML 解码，电路级噪声，BB 码平均 LER 降低 74.4%（相对 BP+OSD 等）。**arXiv 编号未找到，只有搜索结果摘要，我没读正文，数字不可引用到论文级别。**
- 实时硬件：目前只有 Relay-BP 的 FPGA 原型（2510.21600）。LSD、AC、OTF 都只有 CPU 软件计时；Cascade 是 GPU。

## 问题 2：“离最优还有多远”是否已被量化

**已有工作与结论（全部是 BB 码电路级，口径不同，不可直接拼成一条曲线）：**

1. **Tesseract（2503.10988，Beni, Higgott, Shutty，Google，Results 段与摘要）**：明确写“据我们所知，BP+OSD 相对近最优解码在非拓扑 qLDPC 码上的表现此前没有被详细研究过”。结论：Tesseract 与整数规划解码器（精确 MLE）的 LER 比 BP+OSD 低一到两个数量级（Fig. 2，SI1000 噪声，具体 p 区间在图中未提取）。同文在 SI1000 噪声下的资源比较：gross code（电路距离至多 10，即 [[288,12,10]]）用 BP+OSD 相当于约 10 倍省比特，用 Tesseract 是 14 到 19 倍；长程耦合器噪声 10 倍时分别降到约 2 倍和 4 倍（摘要，Fig. 3）。附录 A 指出：不相关（X 与 Z 分开）BP+OSD 反而比相关 BP+OSD 准，原因是 Y 错误在双基底 Tanner 图里造成 4-圈（附录 A，Fig. 5，[[72,12,6]]，6 轮）。注意 Tesseract 是 MLE 不是 ML，忽略简并。
2. **Blue et al.（2504.13043，Sec. 1.3，Fig. 1a）**：[[72,12,6]]，p=0.1%，BP-OSD-3 比整数规划 MLE 解码器差约 4.5×5.4≈24 倍（**这是我把文中两个倍数相乘得到的，不是论文直接给的**）。且差距随 p 减小而变大（“this difference grows as the physical error rate gets smaller”，针对神经解码器与 BP-OSD 之差）。口径问题：BP-OSD 只用 X 检测器，IP 与神经网络用 X+Z 检测器（Sec. 1.3 脚注 2）。
3. **Cascade（2604.08358）**：gross code，p=0.1%，BP-OSD 比 Cascade/Tesseract 约高 4000×，Relay 约高 17×。文中说明 p^5.4（BP-OSD）与 p^10.8（Cascade 陡峭项）的指数差，意味着**差距随 p 降低而扩大，直到 Cascade 的距离限制项（约 p^6.4）接管**。该文自己的解释：BP-OSD 在太多低权重错误上失败，从而看不到“瀑布区”（Fig. 1b 说明）。
4. **telescoping（2607.28795，附录 I.2）**：以含精确 MLE 末级的级联在 gross code p=0.1%、0.2% 给出 6.7e-11、1.3e-8，与 Tesseract 在误差棒内一致。这等于独立于 Cascade 的第二个“近最优参照点”，且完全由 BP 系加 MLE 兜底实现。
5. **简并（ML 与 MLE 之差）很小或未知**：2609.03928（AMLD，只读摘要与前言）报告在 [[144,12,12]] 的比特翻转问题上，p=0.05（明显不是电路级工作点），AMLD 相对 MWD 只降 13% 的 LER；2603.19062（擦除信道，只有搜索摘要）称 BP-OSD 达到 ML 的 97.6%。**两者都不是电路级噪声，仅作旁证。**

**提升空间随 p 的变化**：方向一致——p 越低差距越大（Cascade：p=0.1% 时 4000×；Blue：72 码上随 p 降低差距拉大）。BP-OSD 与 Relay-BP 的差距也有 p 依赖：Relay 论文只在 p=3e-3 给出 10× 到 100×（Fig. 2），Cascade 给出 p=0.1% 时 Relay 仍比近最优差 17×。这与本项目 E-003 的审计发现（p≈0.005 下约 90% 的逻辑失败属于解码器次优）方向一致，但**还没有人在同一管线里，把 BP-OSD、Relay-BP、MLE 三条线在 p∈[5e-4, 5e-3] 上画在一起并分解失败的最低权重**——Cascade 的图最接近，但它的 BP-OSD 基线偏弱（30 次迭代）。

**一个值得跟进的疑点（我的观察，不是论文的说法）**：Cascade 把距离限制项写成 p^6.4≈p^⌊(d+1)/2⌋，取 d=12；而 Tesseract 论文和本项目 `refs-verified.md` 都指出 IBM 电路的电路距离至多 10（对应最小失败权重 5）。若按电路距离 10，距离限制指数应为 5 附近。这对 E-006 判断“失败最低权重是否低于 ⌈d_circ/2⌉”有直接意义，建议 E-006 不要直接套用 Cascade 的指数解释。

## 问题 3：用 AI 设计解码算法的工作

**完全相同的事（LLM / AlphaEvolve / FunSearch / 进化搜索去发现解码算法或启发式规则，在电路级 qLDPC 噪声下）：未找到。** 搜了 “AlphaEvolve decoder quantum error correction”“LLM evolutionary search decoder qLDPC”“OpenEvolve decoder” 等，返回的全是码或编码的发现。

最接近的几类，及与本项目的差别：

| arXiv | 做了什么 | 与“AI 发现解码启发式”的差别 |
|---|---|---|
| 2512.18273（Kwak et al. 2025，v2 2026-05） | 用差分进化（DE）端到端优化 BP 的边权重，与 OSD 联合，多目标压低复杂度；BB 码 [[72,12,6]]、[[90,8,10]]、[[144,12,12]]（Sec. IV.A）。结论：QLDPC 阈值提升 2.9% 到 3.9%，复杂度降最多 62%（Conclusion） | **搜的是 BP 的一组数值权重，不是算法结构**；噪声是去极化信道的码容量级别（阈值 15% 量级，我判断不是电路级，未逐行核对）；没有 LLM |
| 2607.20130（Moradi et al. 2026） | 强化学习（Q-learning）学 BP 变量节点调度，扩展到按簇调度 | 学的是调度策略；噪声为去极化信道（Fig. 5，[[288,12,18]]），非电路级；原始 RL-S 论文编号未找到 |
| 2506.01779 | Relay-BP 的记忆强度区间用“gradient-free optimization”选取（Fig. 2 说明） | 是调参，不是发现 |
| 2604.08358；2408.07038 | 神经网络“学习消息传递规则”（Cascade 原文即这样表述） | 端到端训练网络，不产出可读的启发式规则；不在“发现算法”范畴 |
| 2606.02418（IBM，Cruz-Benito, Cross 等）、2606.24808、2607.25865（OmniQEC）、2608.08996、2608.15754（RL 联合设计码与解码器） | LLM 引导的进化 / AI scientist，发现 BB 码、qLDPC 码、码与综合电路 | 进化对象是**码或电路**，解码器是评估环节里的固定组件（2608.15754 是固定解码器结构后用 PPO 搜码）。IBM 论文用 OpenEvolve 类框架，说明工具链已经成熟 |
| qBraid 与 Google Cloud AlphaEvolve（博客，qbraid.com） | 用 AlphaEvolve 找费米子到量子比特编码 | 只有新闻页，未读论文；与解码器无关 |

**判断**：LLM/程序进化已经被用于 QEC 的“码”侧（IBM、NTU、Caltech/Oratomic 等），而“解码启发式”侧只有数值权重级别的进化和调度级别的 RL，且都停留在码容量噪声。

## 新颖性判断
- **有没有人做过完全相同的事？** 没有找到。限定条件是：“用 LLM 或程序进化去发现 BB / qLDPC 码电路级解码算法的结构（不是调参、不是端到端网络）”。
- **最接近的几篇**：2512.18273（进化优化 BP 权重，码容量）、2607.20130（RL 学调度，码容量）、2606.02418（同一工具链，进化码而非解码器）。差别在于它们要么对象是数值、要么噪声不是电路级、要么搜的是码。
- **未验证的风险**：我的检索是 WebSearch 加有限的 arXiv 阅读，AI 实验室（Google DeepMind、IBM）内部可能已有未发表工作；我没有办法排除。另外 2026 年 6 到 9 月的预印本数量很大，我只覆盖了搜索引擎排前面的结果。

## 问题 4：结论与本项目建议

### 4.1 当前 BB 码电路级解码 SOTA 与相对 BP-OSD 的提升
| 维度 | SOTA（自报，未见独立复现） | 相对 BP-OSD |
|---|---|---|
| 精度，gross code，p=0.1% | telescoping 6.7e-11；Cascade 约 1e-10；Tesseract 同量级（2607.28795 Fig. 9；2604.08358） | Cascade 称约 4000×（弱 BP-OSD 基线）；Relay 比 Cascade 差约 17× |
| 精度，gross code，p=1e-3 | beam search 17×（2512.07057，基线 30 次迭代 CS-10） | 17× |
| 精度，gross code，p=3e-3 | XYZ-Relay-BP-5 约 100×（2506.01779） | 约 100× |
| 速度 | AC 比 BP-OSD 快 6 至 27× 且精度持平；Relay-BP FPGA 24 ns/迭代；telescoping 5.5–6.2 µs/周期（GPU） | 见表 |
| 最小 BP 类实时硬件 | 只有 Relay-BP FPGA（2510.21600） | — |

注意几个口径陷阱：（1）各文 BP-OSD 基线强度不同：IBM 用 10000 次迭代，2512.07057 与 2604.08358 用 30 次迭代，倍数不能互比；（2）“每块”“每轮”“每轮每逻辑比特”的 LER 归一化不同；（3）XZ 解码与 XYZ 解码的差别可达约 2× 到一个数量级（2512.07057 的 Fig. 3 段、2506.01779 附录 Fig. 5 段）。

### 4.2 空白与最强对手
**空白**：
1. 电路级噪声下，**用搜索自动发现 BP 类启发式的结构**（更新规则、记忆强度分布、重启策略、级联调度、排序规则）。目前这一步全靠人（Relay-BP 的负记忆强度，作者自己也说“为什么负值重要”没有答案，2506.01779 Discussion）。
2. **在同一管线里分解 BP-OSD、Relay、MLE 的失败权重谱**（见问题 2）。E-006 做的就是这件事，现有文献没有给出。
3. **BP 速度、近 MLE 精度二者兼顾**：telescoping 是靠级联和 MLE 兜底达成的，吞吐随 p 增大而下降（2607.28795 附录 I.2 自述）；Cascade 要 GPU 且达不到 1 µs。能在 FPGA 友好的纯消息传递里逼近近最优，目前没人做到。

**最强对手（按威胁排序）**：
1. **IBM Relay-BP 团队**（Müller、Beverland 等）：算法、FPGA、开源齐全，Ott-Beverland 又做了可证明最小权重的 DTD；他们还有 OpenEvolve 类工具（IBM 的 2606.02418 作者是 Cross 等）。**最可能把“进化搜索 Relay 类启发式”做出来的就是他们**，这是我的推测，没有证据。
2. **Harvard Cascade 团队与 Caltech/Oratomic telescoping**：已经把精度推到近最优，对“AI 解码器精度更高”的叙事形成压制；telescoping 还证明纯 BP 系 + MLE 兜底即可达到该精度。
3. **Google（Tesseract + AlphaQubit 2）**：Tesseract 是近最优参照，AlphaQubit 2 在 surface/color 上近最优，若扩到 qLDPC 将是强对手；也拥有 AlphaEvolve。
4. IonQ 的 beam search、Riverlane 的 AC：提供 CPU 上的实用点，影响力偏工程。

### 4.3 “有影响力”的解码器标准（根据上述文献的比较习惯归纳）
- **精度**：在 gross code（至少）与 [[72,12,6]]、[[288,12,18]] 上，p∈[1e-3, 3e-3] 乃至 5e-4 的每轮 LER；必须**同时报告与近最优参照（Tesseract 或 IP-MLE）的差距**，并说明 BP-OSD 基线的迭代数和 OSD 阶；必须说明 XZ 还是 XYZ 解码、噪声模型与归一化（每块 / 每轮 / 每逻辑比特）。
- **速度**：均值与 99.9 分位延迟都要报（2512.07057 的做法，因 OSD 类解码器尾部很长）；每轮微秒数；BP-OSD、Relay-BP、Tesseract 同机对比。
- **可实时**：能否映射到 FPGA/ASIC（并行消息传递是门槛）；每周期预算超导约 1 µs，中性原子 / 离子约 1 ms（2604.08358 Speed 段）；滑窗解码下的表现（2510.21600）。
- **可推广性**：跨码（BB 的 72、90、108、144、288）、跨噪声（SI1000、NLR、uniform）、跨任务（存储以外的逻辑操作，Relay 论文自己列为未解问题）；训练型方法要报告对未见 p 的泛化（Cascade 在 0.55% 训练，评估到 0.06%）。
- **可复现**：开源（Relay、OTF、beam、GraphQEC 开源；Cascade、AC 我未找到代码）；独立复现目前几乎没有。

## 对本项目的建议
1. **E-006 的最低要求**：同一管线，同一 DEM，报告 BP-OSD（至少两种设置：10000 次迭代 CS-10 和 30 次迭代）、Relay-BP（官方仓库 trmue/relay，XZ 与 XYZ）、Tesseract 或 IP-MLE，p∈{5e-4, 1e-3, 2e-3, 3e-3}，并分解失败的最低权重。这样才能回答 H-005 的关键未知，也才是文献里确实缺的数据。
2. **预期结果已部分被文献暗示**：在 p=0.1% 下，Relay 距近最优仍有约 17 倍（2604.08358，自报）。E-006 若复现这个数，H-005 的“提升空间”前半句成立；但“AI 能兑现”必须对着 Relay-BP、telescoping、beam search 这些强基线，而不是 BP-OSD。
3. **“AI 发现的启发式”要想有影响力，应把目标定在“用搜索得到的 FPGA 友好 BP 变体，逼近 Tesseract 级精度”**，并把 Relay-BP 作为必须击败的基线；搜索空间建议从 Relay 的结构（段数、记忆强度分布、重启 / 分支规则、段间信息传递）出发，评估走项目现有评估器。必须同时报告同算力随机搜索 / 模拟退火对照（CLAUDE.md 铁律 5）。这与 2512.18273（DE 调权重）的差别要在论文里说清：对象应是算法结构，且在电路级噪声下评估。
4. **风险**：IBM 与 Google 都有 AlphaEvolve/OpenEvolve 类工具并且在做同一方向；若 H-005 的提升空间只剩“追近 Cascade/telescoping 已达到的精度”，新颖性主要在“自动发现”这一方法论，而不是精度。建议 PI 在决定投入前看 E-006 数据，并考虑把方法论贡献（H-002 方向）与解码器结果分开写。
5. **待核实项**（引用前必须补）：Relay-BP 与 2510.21600 的平均迭代数不一致；HAMLD 的 arXiv 编号与正文；Astra 噪声模型；Restart Belief 是否做了电路级模拟；DTD 的开源状态；Cascade 与 telescoping 的独立复现；LSD 的具体速度倍数（2406.18655 Fig. 8、9）；Tesseract 的 BB 码对比图中的具体 p 区间与数值。
