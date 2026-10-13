# 挂 arXiv 后的联系信稿（草稿，PI 审阅后由 PI 本人发送）

先填好 arXiv 编号、你的姓名和单位，再发。收件人邮箱请从对方论文或主页上核对，这里不预填。

---

## 1. 致 Strikis、Browne、Beverland（arXiv:2603.05481 作者）

**Subject:** A distance-12 interleaved single-ancilla circuit for the gross code (re your Sec. IV.3)

Dear Dr. Strikis, Prof. Browne and Dr. Beverland,

In Sec. IV.3 of your paper "High-performance syndrome extraction circuits for quantum codes" (arXiv:2603.05481) you leave open whether any interleaved circuit can reach circuit distance 12 for the gross code. In arXiv:[XXXX.XXXXX] we give one: a single-ancilla, CNOT-based, interleaved circuit with d_circ = 12 under SD6 noise, in both memory bases and for every number of rounds.

The construction keeps the extended code of your Fig. 12 circuit (d_ext = 11). Reversing a check's CNOT order and swapping the first two or the last two CNOTs leaves the extended code unchanged, so we choose orders from this class and CNOT times such that none of the 4224 weight-11 extended logicals can be realised by eleven undetected faults. The lower bound combines two short arguments with an exact computation. The price is a period of 18 steps per round instead of 8; within colour-symmetric schedules, 18 is the minimum.

Along the way we also prove that your Fig. 12 circuit has d_circ = 11, as you conjectured.

The circuits, the lists of logicals, the certificates and the reproduction scripts are available at [Zenodo DOI]. We would be glad to hear any comments, in particular on the presentation of your results.

Best regards,
[Name]
[Affiliation]

---

## 2. 致 IBM（arXiv:2308.07915 / 2506.03094 的作者，如 Andrew Cross、Ted Yoder）

**Subject:** Distance-12 single-ancilla syndrome circuit for the gross code

Dear Dr. [Name],

Our preprint arXiv:[XXXX.XXXXX] may interest you. We construct a single-ancilla syndrome-extraction circuit for the gross code [[144,12,12]] with proven circuit distance 12 under SD6 noise, for any number of rounds, answering an open question of Strikis, Browne and Beverland (arXiv:2603.05481).

The circuit has period 18 rather than 8, and we have not evaluated its logical error rate. Whether depth 8 can reach distance 12 is still open.

Data and reproduction scripts: [Zenodo DOI]. Comments are welcome.

Best regards,
[Name]
[Affiliation]

---

注意事项：
- 信里只写论文和复核过的结论里有的内容，不提尚未公开的 morphing 判据工作。
- PI 已决定：不抄送 Shaw、Terhal。
- 是否向 IonQ 询问其 d_circ = 9 的计算方法，与本文无关，建议以后再说。
