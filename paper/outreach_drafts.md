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

## 致 Anthropic 研究员：个人介绍与合作意向（以介绍本人为主）

收件人：Andi Gu（arXiv:2610.22367 第一作者，Anthropic STEM Fellows）。邮箱以论文或 arXiv 上的联系方式为准。也可以走 Anthropic 官方的 Fellows 或科研合作渠道。
个人信息取自两个 GitHub 账号的公开仓库（Ephemeral6、GavinNull），请 PI 逐句核对后再发。

**Subject:** A machine-checked proof of Nivat's conjecture, found with Claude agents: hoping to work with you

Dear Dr. Gu,

My name is Guancheng Pan. I am a second-year undergraduate at Chu Kochen Honors College, Zhejiang University. Your paper on discovering quantum circuits with LLMs (arXiv:2610.22367) is very close to what I care about most, which is how to do real research with AI, and I wanted to introduce myself.

The result I am proudest of is a proof of **Nivat's conjecture**, in its convex form, with a complete Lean 4 formalisation. Nivat posed the conjecture in 1997 as the two-dimensional analogue of the Morse–Hedlund theorem: if a configuration of Z² has at most mn distinct m×n patterns for some m, n, it must be periodic. It is one of the best-known open problems in symbolic dynamics and combinatorics on words. Over the past decade it has drawn a series of partial results: Kari–Szabados's algebraic approach, work by Cyr and Kra, and Colle's results on nonexpansive directions. The convex form is the natural general statement, since Khetan's counterexample shows that it fails for non-convex windows, and it contains the original rectangular conjecture. The core of the proof is a complexity lower bound for "star configurations". In it a zonotope, the Newton polytope of a product of annihilating Laurent polynomials, appears twice with opposite signs: once as the exact cost of the affine relations a window carries, and once as the exact capacity of an independent family of quadratic characters. The two cancel.

The method is what I most want to talk about. The proof and the formalisation were produced by a research system I built: an orchestration of Claude agents in Claude Code, with parallel formalisation lanes, a single integrating agent, dedicated refutation agents that try to break every claim, and independent auditors, while I make the decisions at defined gates. The Lean development has about 216,000 lines and 449 modules, contains no `sorry`, and uses only Lean's standard axioms. It also formalises every result the paper quotes from the literature (Kari–Szabados, Colle, Boyle–Lind, Cyr–Kra), and doing so exposed a step in a published lemma that does not go through as written; the formalisation replaces it with a different construction. The paper's appendix records the timeline, the organisation, and every significant error the agents made and how it was caught. Repository: https://github.com/Ephemeral6/convex-nivat-star-configurations

I have used the same approach in other areas: Mockenhaupt's three-term majorant conjecture (arXiv:2609.09740), Kakimizu's contractibility problem for knots (arXiv:2609.09224), and, most recently, certified distance-preserving syndrome circuits for bivariate-bicycle codes (https://github.com/GavinNull/gross-code-distance-12).

I would love to work with you, or with Anthropic more broadly, on AI for scientific research, as a fellow, an intern, or a collaborator on a concrete project. I would be glad to talk at any time that suits you.

Best regards,
Guancheng Pan
Chu Kochen Honors College, Zhejiang University
3250101086@zju.edu.cn
GitHub: https://github.com/Ephemeral6 · https://github.com/GavinNull

---

注意事项：
- 发给 Anthropic 研究员的信不要拿我们的工作去和他们的比较，只讲互补。语气自信，但不攀附。
- 第一封在挂 arXiv **之前**发，第二封在挂出**之后**发。
- 信里只写论文中已有、并且经过复核的内容。
- AI 参与的情况与论文致谢保持一致，坦白写明。
- 不抄送 Shaw、Terhal（PI 已决定）。
- 建议等 1–2 周；对方没有回复也照常挂 arXiv（仓库已公开，有时间戳）。
