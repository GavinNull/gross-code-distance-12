# 联系信稿（PI 审阅后由 PI 本人发送）

PI 决定（2026-10-21）：三封信都不等 arXiv，直接发。附件是论文 PDF（`paper/draft.pdf`），链接用 GitHub。收件人邮箱请从对方论文或主页上核对后再填。
公开链接：
- 论文 PDF：https://github.com/GavinNull/gross-code-distance-12/blob/main/paper/draft.pdf
- 数据与复现（Release v2.0）：https://github.com/GavinNull/gross-code-distance-12/releases/tag/v2.0
- 仓库：https://github.com/GavinNull/gross-code-distance-12

注（2026-10-24 更新）：信中所有结论都已经独立复核：两个码都在周期 11 下达到满距离，并补充了中性原子噪声模型下的结果。

---

## 第一封：致 Strikis、Browne、Beverland（arXiv:2603.05481 作者）

**To:** strikis@maths.ox.ac.uk　**Cc:** michael.beverland@gmail.com
（两个邮箱都取自 arXiv:2603.05481 v2 论文正文。Browne 的邮箱论文中没有印，如需加上，请从 UCL 官网查询。）

**Subject:** Interleaved single-ancilla circuits reaching distance 12 for the gross code and 10 for [[90,8,10]]

Dear Dr. Strikis, Prof. Browne and Dr. Beverland,

In "High-performance syndrome extraction circuits for quantum codes" you ask whether any interleaved circuit can achieve circuit distance 12 for the gross code. I have an affirmative answer, together with a second example, and I would very much value your comments. The paper is attached.

It constructs explicit single-ancilla, CNOT-based syndrome circuits with an 11-step period that reach the full code distance under SD6 noise, in both memory bases and for every number of rounds:
- For the gross code [[144,12,12]], d_circ = 12. The circuit is uniformly tiled, with the same CNOT order on every check, and pipelined. Your Prop. 5 caps every uniformly tiled non-interleaved circuit at 10, and your Prop. 4 caps every non-interleaved circuit at 11.
- For the [[90,8,10]] code, d_circ = 10. Every assignment of CNOT orders has d_ext ≤ 8, so this is two above every non-interleaved circuit.

The method fixes an order class, even one of lower extended-code distance, and recovers the full distance by exact lift computations over complete lists of the lightest extended logicals. Every solver decision is backed by a checked certificate (VeriPB for the extended-code distances and list completeness; DRAT checked by drat-trim and cake_lpr for the lifts). A direct search on the full detector error model confirms both results independently. As a corollary, your Fig. 12 circuit has d_circ = 11, as you conjectured.

Under standard SD6 with idle noise the new circuits have higher logical error rates than the depth-8 circuits. Without idle noise, which follows your App. G.2, the [[90,8,10]] circuit is below IBM's, and in a neutral-atom noise model with literature parameters it is also below IBM's, under the stated assumptions on ancilla moves and unpaired atoms.

Circuits, logical lists, certificates and reproduction scripts are at https://github.com/GavinNull/gross-code-distance-12. The work was carried out with AI agents under my direction, as the paper states.

I would especially appreciate your view on the correctness of the results and on whether they are fairly placed relative to your work.

Best regards,
Guancheng Pan
Chu Kochen Honors College, Zhejiang University
3250101086@zju.edu.cn

---

## 第二封：致 IBM（arXiv:2308.07915 / 2506.03094 作者，如 Andrew Cross、Ted Yoder）—— 不等 arXiv，直接发

**To:** 这两篇论文都没有印作者邮箱。可以通过 LinkedIn、IBM Quantum 官网的联系渠道，或者请 Beverland（IBM Quantum，已在第一封信的抄送里）转交。

**Subject:** Distance-preserving single-ancilla syndrome circuits for the gross and [[90,8,10]] codes

Dear Dr. [Name],

I would like to share a new result on syndrome-extraction circuits for your bivariate-bicycle codes; the paper is attached.

I construct explicit single-ancilla syndrome circuits with an 11-step period and proven circuit distance 12 for the gross code and 10 for the [[90,8,10]] code, under SD6 noise, in both memory bases and for every number of rounds. For the gross code this answers an open question of Strikis, Browne and Beverland (arXiv:2603.05481), who showed that non-interleaved single-ancilla circuits cannot exceed 11. For [[90,8,10]] the best value so far was 8, proven exact for your depth-7 circuit (arXiv:2503.10988).

Along the way, exact enumeration shows that your depth-8 gross circuit has circuit distance exactly 10 for every number of rounds up to 12, with machine-checked lower bounds, in agreement with an independent exhaustive search by C. Crocker (doi:10.5281/zenodo.23452754). Under standard SD6 our circuits have higher logical error rates than yours, because of idling. In a neutral-atom noise model, where both use the same number of array moves per round, the [[90,8,10]] circuit has the lower rate under the stated assumptions. Reaching the full distance at depth 8 is the next goal, and I would be glad to hear whether the structure we found suggests a route there.

The circuits, logical lists, DRAT certificates and reproduction scripts are public: https://github.com/GavinNull/gross-code-distance-12. Comments are very welcome.

Best regards,
Guancheng Pan
Chu Kochen Honors College, Zhejiang University
3250101086@zju.edu.cn

---

## 第三封：致 Anthropic 研究员（Andi Gu，arXiv:2610.22367 第一作者）——个人介绍与合作意向

**To:** andigu@g.harvard.edu（取自 arXiv:2610.22367 论文正文；作者单位同时列为哈佛和 Anthropic STEM Fellows Program）。也可以同时走 Anthropic 官方的 Fellows 或科研合作渠道。

**Subject:** Two research results obtained with Claude agents, and a wish to work with you

Dear Dr. Gu,

My name is Guancheng Pan, and I am a second-year undergraduate at Chu Kochen Honors College, Zhejiang University. Your paper on discovering quantum circuits with LLMs (arXiv:2610.22367) is very close to what I care about most, which is how to do real research with AI, so I wanted to introduce myself and two results I obtained this way.

**Nivat's conjecture.** I have a proof of Nivat's conjecture in its convex form, with a complete Lean 4 formalisation. Nivat posed the conjecture in 1997 as the two-dimensional analogue of the Morse–Hedlund theorem: a configuration of Z² with at most mn distinct m×n patterns for some m, n must be periodic. It is one of the best-known open problems in symbolic dynamics and combinatorics on words, with a decade of partial results by Kari–Szabados, Cyr–Kra and Colle. The convex form is the natural general statement, since Khetan's counterexample shows that convexity cannot be dropped, and it contains the original conjecture. At the heart of the proof is a single zonotope that appears twice with opposite signs. It is the exact cost of the affine relations a window carries, and it is also the exact capacity of an independent family of quadratic characters, so the two cancel. The Lean development has about 216,000 lines, contains no `sorry`, and uses only Lean's standard axioms. It also formalises every result quoted from the literature, and in doing so it exposed a step in a published lemma that does not go through as written. https://github.com/Ephemeral6/convex-nivat-star-configurations

**Quantum error correction, one layer below your work.** Your outlook mentions co-design across the fault-tolerant stack. I recently obtained certified syndrome-extraction circuits that reach the full circuit distance of two bivariate-bicycle codes, both with an 11-step period: distance 12 for IBM's gross code, which answers an open question of Strikis, Browne and Beverland, and distance 10 for [[90,8,10]], each two above the extended-code bound of its CNOT orders. The agents found the key structural fact: pipelining lets a check's readout fall between two hook errors, so extended-code logicals that silently pass a segmented circuit are caught. They turned the design problem into a finite one, solved it exactly with every solver decision backed by a checked certificate, and confirmed the results by a direct search on the full detector error model. In a neutral-atom noise model with literature parameters the [[90,8,10]] circuit has a lower logical error rate than IBM's. Every claim was audited independently with separately written code. The full research record is public, including every mistake and correction. https://github.com/GavinNull/gross-code-distance-12

**The method.** Both results come from the same research system, which I built: an orchestration of Claude agents in Claude Code with parallel workstreams, dedicated refutation agents, independent auditors, machine-checkable proofs and pre-registered predictions, with me deciding at defined gates. Building it taught me how to make agents do the reasoning and not just the chores, where they fail (overclaiming, subtle encoding errors, plausible but wrong steps), and how to design processes that catch those failures.

I would love to work with you, or with Anthropic more broadly, on AI for scientific research, as a fellow, an intern, or a collaborator on a concrete project. I would be glad to talk whenever it suits you.

Best regards,
Guancheng Pan
Chu Kochen Honors College, Zhejiang University
3250101086@zju.edu.cn
GitHub: https://github.com/Ephemeral6 · https://github.com/GavinNull

---

注意事项：
- 三封信都只写论文中已有、并经过复核的内容。
- AI 的参与在三封信里都坦白写明，与论文致谢一致。
- 不抄送 Shaw、Terhal（PI 已决定）。
- 第三封里关于 Nivat 的背景与证明思路，请 PI 逐句核对，确保对前人工作的表述准确。
