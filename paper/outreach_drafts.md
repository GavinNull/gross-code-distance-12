# 挂 arXiv 前的联系信稿（PI 审阅后由 PI 本人发送）

PI 决定（2026-10-14）：先写信，再挂 arXiv。附件是论文 PDF（`paper/draft.pdf`）。仓库已公开：https://github.com/GavinNull/gross-code-distance-12。收件人邮箱请从对方论文或主页核对后再填。

---

## 致 Strikis、Browne、Beverland（arXiv:2603.05481 作者）

**Subject:** Interleaved single-ancilla circuits reaching distance 12 for the gross code and 10 for [[90,8,10]]

Dear Dr. Strikis, Prof. Browne and Dr. Beverland,

In "High-performance syndrome extraction circuits for quantum codes" (arXiv:2603.05481) you ask whether any interleaved circuit can achieve circuit distance 12 for the gross code. I have an affirmative answer, together with a second example, and before posting to arXiv I would very much value your comments. The draft is attached.

The paper constructs explicit single-ancilla, CNOT-based, interleaved syndrome circuits that reach the full code distance under SD6 noise, in both memory bases and for every number of rounds:
- the gross code [[144,12,12]]: d_circ = 12, compared with at most 11 for every non-interleaved circuit (your Prop. 4);
- the [[90,8,10]] code: d_circ = 10. Every assignment of CNOT orders has d_ext ≤ 8, so this is two above every non-interleaved circuit.

The method keeps the extended code fixed and chooses CNOT orders and timing so that none of the low-weight extended logicals is realised by an undetected circuit error. This turns circuit design into a finite decision problem, which I solve exactly. The solver refutations come with DRAT proofs, checked with drat-trim and cake_lpr. Both results are also confirmed by a direct search on the full detector error model; for [[90,8,10]] this gives a second proof that does not use the extended code at all. As a corollary, your Fig. 12 circuit has d_circ = 11, as you conjectured.

The circuits have periods of 18 and 16 steps per round. Under SD6 with idle noise, the gross circuit has a higher logical error rate than the depth-8 circuits, so shorter periods are the natural next goal.

All circuits, lists of logicals, certificates and reproduction scripts are public at https://github.com/GavinNull/gross-code-distance-12. The work was carried out with AI agents under my direction, and the paper says so explicitly.

I would particularly appreciate your view on the correctness of the results and on whether they are fairly placed relative to your work.

Best regards,
Guancheng Pan
Zhejiang University
3250101086@zju.edu.cn

---

## 致 IBM（arXiv:2308.07915 / 2506.03094 作者，如 Andrew Cross、Ted Yoder）—— 挂 arXiv 后再发

**Subject:** Distance-preserving single-ancilla syndrome circuits for the gross and [[90,8,10]] codes

Dear Dr. [Name],

You may be interested in my preprint arXiv:[XXXX.XXXXX]. It constructs single-ancilla interleaved syndrome circuits with proven circuit distance 12 for the gross code and 10 for the [[90,8,10]] code under SD6 noise, for every number of rounds. The gross result answers an open question of Strikis, Browne and Beverland. For [[90,8,10]], the best previously known value was 8, proven exact for your depth-7 circuit (arXiv:2503.10988).

The circuits have periods of 18 and 16. Reaching full distance at depth comparable to yours is the next goal.

Data and reproduction: https://github.com/GavinNull/gross-code-distance-12. Comments are welcome.

Best regards,
Guancheng Pan
Zhejiang University

---

## 致 Anthropic 研究员（arXiv:2610.22367 的作者 Andi Gu 等）——可与第一封信并行发送

收件人：Andi Gu（Anthropic STEM Fellows，2610.22367 第一作者；邮箱请以论文首页或 arXiv 上的联系方式为准）。可抄送该文的哈佛通讯作者。也可以通过 Anthropic 官方的科研合作或 AI for Science 渠道联系（以官网当前页面为准）。

**Subject:** Certified AI-found syndrome-extraction circuits: the error-correction layer next to your 2610.22367

Dear Dr. Gu,

I read your paper "Discovering state-of-the-art quantum circuits with large language models" (arXiv:2610.22367) with great interest. In your outlook you mention co-design across the fault-tolerant stack. I have just completed a result one layer below yours, in quantum error correction, and I think the two fit together naturally.

Working with Claude agents under my direction, I constructed explicit single-ancilla, interleaved syndrome-extraction circuits that reach the full code distance:
- for the gross code [[144,12,12]], circuit distance 12, answering an open question of Strikis, Browne and Beverland (arXiv:2603.05481);
- for [[90,8,10]], circuit distance 10, two above every non-interleaved circuit.

The agents did the scientific reasoning: the key structural insight, the searches, the proofs, and an independent audit of every claim with separately written code. Every infeasibility claim decided by a solver comes with a DRAT proof, checked with drat-trim and cake_lpr. Paper, circuits, certificates and reproduction scripts: https://github.com/GavinNull/gross-code-distance-12 (release v1.0).

Your work uses LLM-guided evolutionary search with an evaluator for arithmetic circuits; ours uses agent reasoning plus certified exact search for syndrome circuits. Together they look like two complementary pieces of AI-driven fault-tolerant design. I would be glad to hear your thoughts, and I would welcome a conversation about whether there is room to collaborate, for instance on shorter-period circuits or on joint co-design of the algorithm and error-correction layers.

Best regards,
Guancheng Pan
Zhejiang University
3250101086@zju.edu.cn

---

注意事项：
- 发给 Anthropic 研究员的信不要拿我们的工作去和他们的比较，只讲互补。语气自信，但不攀附。
- 第一封在挂 arXiv **之前**发，第二封在挂出**之后**发。
- 信里只写论文中已有、并且经过复核的内容。
- AI 参与的情况与论文致谢保持一致，坦白写明。
- 不抄送 Shaw、Terhal（PI 已决定）。
- 建议等 1–2 周；对方没有回复也照常挂 arXiv（仓库已公开，有时间戳）。
