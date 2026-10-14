# 挂 arXiv 前的联系信稿（PI 审阅后由 PI 本人发送）

PI 决定（2026-10-14）：补完模拟和证书后，先写信，再挂 arXiv。附件是论文 PDF（`paper/draft.pdf`）。仓库已公开：https://github.com/GavinNull/gross-code-distance-12。收件人邮箱请从对方论文或主页上核对后再填。

---

## 致 Strikis、Browne、Beverland（arXiv:2603.05481 作者）

**Subject:** An interleaved single-ancilla circuit with circuit distance 12 for the gross code (re: your Sec. IV C)

Dear Dr. Strikis, Prof. Browne and Dr. Beverland,

I am a student at Zhejiang University. Your paper "High-performance syndrome extraction circuits for quantum codes" (arXiv:2603.05481) asks whether any interleaved circuit can achieve circuit distance 12 for the gross code. I believe I have an affirmative answer, and I would be grateful for your comments before I post it on arXiv. The draft is attached.

The result is a single-ancilla, CNOT-based, interleaved circuit for [[144,12,12]] with d_circ = 12 under SD6 noise, in both memory bases and for any number of rounds. The construction keeps the extended code of your Fig. 12 circuit fixed. Reversing a check's CNOT order and swapping the first two or the last two CNOTs leave the extended code unchanged, so I choose orders within this class, together with CNOT times, such that none of the 4224 weight-11 extended logicals can be realised by eleven undetected faults. The lower bound combines a reduction, an exact finite-round computation (each solver refutation comes with a DRAT proof checked with drat-trim and cake_lpr) and an argument that extends it to every number of rounds. As a corollary, your Fig. 12 circuit has d_circ = 11, as you conjectured.

There is a clear cost. The period is 18 time steps per round instead of 8, and with SD6 idle noise the circuit has a much higher logical error rate than your Fig. 12 circuit or the IBM circuit. It wins only when idle errors are much weaker than gate errors. I therefore present it as a structural answer to your question, not as a practical improvement. Whether period 8 can reach distance 12 remains open.

The circuits, the lists of logicals, the certificates and the reproduction scripts are public at https://github.com/GavinNull/gross-code-distance-12. Most of the work, including the searches, the proofs and their independent re-checking, was done with AI agents under my direction; the paper states this explicitly.

I would particularly value your view on whether the result is correct and fairly placed relative to your work.

Best regards,
Guancheng Pan
Zhejiang University
3250101086@zju.edu.cn

---

## 致 IBM（arXiv:2308.07915 / 2506.03094 作者，如 Andrew Cross、Ted Yoder）—— 挂 arXiv 之后再发

**Subject:** Distance-12 single-ancilla syndrome circuit for the gross code

Dear Dr. [Name],

You may be interested in my preprint arXiv:[XXXX.XXXXX]. It constructs a single-ancilla syndrome-extraction circuit for the gross code [[144,12,12]] with proven circuit distance 12 under SD6, for any number of rounds, answering an open question of Strikis, Browne and Beverland (arXiv:2603.05481).

The circuit has period 18 rather than 8. Under SD6 with idle noise its logical error rate is much higher than that of your depth-8 circuit; it is competitive only when idle errors are much weaker than gate errors. Whether depth 8 can reach distance 12 remains open.

Data and reproduction: https://github.com/GavinNull/gross-code-distance-12. Comments are welcome.

Best regards,
Guancheng Pan
Zhejiang University

---

注意事项：
- 第一封信在挂 arXiv **之前**发；第二封在挂出之后发。
- 信里只写论文里有、并已复核的内容。不提尚未发表的 morphing 判据工作（它在公开仓库里，不用主动提）。
- AI 参与的说明与论文致谢一致，坦白写出，避免对方事后觉得被隐瞒。
- PI 已决定：不抄送 Shaw、Terhal。
- 是否向 IonQ 询问其 d_circ = 9 的计算方法，与本文无关，建议以后再说。
- 等待回复的时间建议设为 1–2 周；对方没有回复，就照常挂 arXiv（仓库已公开，有时间戳）。
