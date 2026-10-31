# Outline for revision P: minimum period for full circuit distance

Status: plan for PI review (STATE, PI decision 2026-10-31: rewrite around optimal periods + mechanism + pair
obstruction; v2.0 draft not submitted). `paper/draft.tex` (O6) is not edited until this outline is approved.
Sections 1–9 are paper-facing; section 10 (claims ledger) and section 11 (open decisions) are internal and never
enter the paper.

---

## 0. What I learned from the format rules and the exemplars

**PRL rules (journals.aps.org/prl/authors and /authors/length-guide, read 2026-10-31).**
- Core (abstract to acknowledgments, abstract excluded) ≤ 3750 words. Displayed equations 16 words/row (32 for
  two-column); single-column figure 150/aspect + 20; double-column figure 300/(0.5·aspect) + 40; table 13 + 6.5/line
  (double-column 26 + 13/line).
- End Matter: up to 2 pages after the references, not counted; for content specialists need (proofs belong here).
- SM: useful but not essential; the paper must stand alone without it. Every reference cited in the SM must also
  appear in the main reference list (so moving a paragraph to the SM does not shorten the bibliography).
- 100-word justification required at submission. No abstract word limit on the page; keep ≈ 150 words as before.

**Exemplars (structure, 2–3 lines each).**
1. Xu, Chen, Gühne, *Proof of the Peres conjecture for contextuality*, PRL 124, 230401 (2020), arXiv:2001.07656.
   Exact minimality (18 vectors) = known construction + new lower bound. Intro states the conjecture as the open
   problem in one paragraph; an early table + figure show the optimal object; the lower bound is a lemma-driven case
   analysis whose exhaustive computer search over small graphs sits in appendices; ends with open questions.
   *Lesson*: name the open problem, show the optimal object early, keep the search as a lemma's proof, not the story.
2. Huber, Gühne, Siewert, *Absolutely maximally entangled states of seven qubits do not exist*, PRL 118, 200502
   (2017), arXiv:1608.06228. Closes the last open case; the title is the result. Main result stated as a numbered
   observation in the main text with a short self-contained proof; a matching "how close can one get" bound
   (32 of 35) with an attaining state; generalisation in an appendix.
   *Lesson*: impossibility + attaining example together make the optimality; the title can state the number.
3. Shaw, Terhal, *Lowering connectivity requirements for bivariate bicycle codes using morphing circuits*, PRL 134,
   090602 (2025), arXiv:2407.16336. Same code family and venue. Construction stated via a named criterion; circuit
   distances in a compact Table 1; conceptual Fig. 1 of the protocol; formal propositions and proofs in appendices;
   short Outlook.
   *Lesson*: a BB-circuit letter carries one table of numbers and one conceptual figure; proofs go to the back.
4. Li, Gan, Wu, Zhang, Zhang, Liu, *A parity obstruction to degree-optimal syndrome extraction in bivariate bicycle
   codes*, arXiv:2509.26494 v4 (2026-10-16; no journal ref). Closest in content: an optimality result for BB
   syndrome circuits (depth 7 optimal, depth 6 impossible), analytic parity obstruction + DRAT certificates, a
   matching construction where the hypothesis fails. Scope stated up front (single round, no staggering, no circuit
   distance); unproved solver results labelled as indications.
   *Lesson*: put the class/hypotheses in the theorem, give an analytic obstruction for the mechanism and
   certificates for the rest, and state the scope once.
5. Chao, Reichardt, *Quantum error correction with only two extra qubits*, PRL 121, 050502 (2018),
   arXiv:1705.02329. A resource-minimal circuit construction told around one idea (flags), one figure per idea,
   extensions in one paragraph.
   *Lesson*: one idea, one figure; extensions compressed.

Common shape: problem → precise open question → result stated as a number → idea → (lower bound via an obstruction
lemma, upper bound via an explicit object) → cost/scope once → open questions. This is the outline below.

---

## 1. The one central result

> Among translation-invariant single-ancilla syndrome-extraction circuits, the minimum period at which the circuit
> distance equals the code distance is exactly 10 for the gross code [[144,12,12]] and exactly 11 for
> [[90,8,10]]; at period 8 the best circuit distances are 11 and 8. Interleaving is what makes this possible: a
> circuit can be re-timed into a non-interleaved one exactly when an integer round-offset cochain is a coboundary,
> an extended-code logical fails to become an undetected fault when a system of difference constraints has a
> negative cycle, and at period 8 a flat two-qubit hook, together with the fact that every pair of check qubits
> lies in a minimum-weight logical, costs one unit of distance.

Everything else in the paper serves this sentence. Lower bounds: for sufficiently many rounds. Constructions: every
number of rounds, both memory bases. Noise: SD6, CNOT template.

## 2. Title options

1. **Minimum period of distance-preserving syndrome extraction for bivariate-bicycle codes** (recommended: names the
   quantity that is determined, as in exemplar 2).
2. Optimal periods for full-distance single-ancilla circuits of the gross and [[90,8,10]] codes.
3. Interleaving, coboundaries and the minimum period of distance-preserving syndrome circuits.

## 3. Abstract draft (≈ 160 words; background, gap, result, idea, cost)

Single-ancilla syndrome-extraction circuits for bivariate-bicycle codes lose circuit distance unless the CNOTs of
overlapping X and Z checks are interleaved, but how short a distance-preserving circuit can be has remained open.
We answer this for translation-invariant circuits, in which all checks of one type share a CNOT timing repeated with
period P. Under circuit-level depolarizing noise, the minimum period at which the circuit distance equals the code
distance is 10 for the gross code [[144,12,12]] and 11 for [[90,8,10]], and at period 8 the best circuit distances
are 11 and 8. The circuits reach full distance for every number of rounds; the impossibility results hold for
sufficiently many rounds and are certified. Interleaving acts through an integer cochain of round offsets: a circuit
can be re-timed into a non-interleaved one exactly when this cochain is a coboundary, and a lightest logical of the
extended code is blocked when difference constraints along its hooks form a negative cycle. The extra idle steps
make the full-distance circuits worse than IBM's depth-8 circuits under standard idle noise.

(Last sentence = cost; the λ = 0 advantage of the [[90]] circuit is in the main text, not the abstract, unless the
PI prefers it here.)

## 4. Paragraph-by-paragraph outline (one-sentence purpose each)

### Introduction (≈ 800 words)
- **I1 Problem.** BB codes need syndrome circuits whose circuit distance d_circ equals d, single-ancilla circuits
  are the hardware-minimal choice, and the number of time steps per round (the period) sets their idle cost, so the
  question is the shortest period at which full distance is possible.
- **I2 What was known.** SBB's extended code gives d_circ ≥ d_ext for every single-ancilla circuit and
  d_circ ≤ d_ext for non-interleaved ones (gross ≤ 11 by a 90-case numerical search, Prop. 4; uniformly tiled ≤ 10,
  Prop. 5), interleaved circuits were left open, and existing depth lower bounds (depth ≥ 7) concern correctness
  of a single round, not distance [Li et al. 2509.26494; Zhang et al. 2603.21499].
- **I3 Open question.** State it in one sentence: within the natural class of translation-invariant single-ancilla
  circuits, what is the minimum period with d_circ = d, and why does interleaving help at all.
- **I4 Result.** Theorem 1 in words (10 for gross, 11 for [[90,8,10]], period-8 optima 11 and 8), with the
  qualifiers stated once (sufficiently many rounds for the bounds; every R for the circuits; SD6).
- **I5 Idea.** The round-offset cochain δ, coboundary ⇔ re-timable to non-interleaved (generalising SBB's
  definition), liftability as difference constraints with negative-cycle certificates, and the pair obstruction
  that kills period 8 analytically and replaces the numerical step of SBB's Prop. 4 by a pair-covering property.
- **I6 Prior work.** Exact circuit distances and certificates [Manes–Claes; Webster–Jacob–Higgott; Tesseract;
  Liang et al.; Ghosh et al. LP bounds], morphing circuits [Shaw–Terhal; Wills et al.], pipelining [Xu et al.],
  interleaving for the surface code [Hirai et al.], hook orientation [Tomita–Svore; Kishony–Fowler; Dennis et al.],
  and the Z2 correctness parity of overlapping checks [Li et al.; Durazo Rocha et al.] of which δ is the integer,
  multi-round refinement.

### Setting and class (≈ 350 words + one display)
- **S1 Model.** Memory experiment, one ancilla per check reset–6 CNOTs–measured each round, SD6 faults merged into
  DEM mechanisms, d_circ counts mechanisms; hook residuals and the extended code with distance d_ext (SBB Table I,
  Prop. 3) in three sentences.
- **S2 Class T(P)** (display, Definition below) and the two facts the reader needs: determinism ⇔ equal round
  offsets on the two shared qubits, so a circuit is described by its signature (orders, 3×3 offset matrix G); the
  class is empty for P < 8 and contains IBM's depth-8 circuits.

### Theorem 1 (≈ 150 words)
- **T1** State Theorem 1 (exact text in §5) immediately after the class, then point to Table I/Fig. 2 for the
  numbers and the reference circuits.

### Key idea (≈ 650 words + Fig. 1)
- **K1 Staircase indices and δ.** An error on a data qubit is seen by each reader at a definite instance index;
  for an X check c and Z check z sharing two qubits, δ(c,z) is the instance of z that first sees errors deposited by
  instance 0 of c, and determinism makes it well defined.
- **K2 Proposition 2.** Coboundary ⇔ re-timable to non-interleaved; then every extended logical lifts and
  d_circ ≤ d_ext in the bulk; SBB's Cor. 1 is the constant-δ case for every R; for translation-invariant BB circuits
  δ is a 3×3 matrix and is a coboundary iff its nine entries agree.
- **K3 Necessary, not sufficient.** One sentence: IBM's depth-8 gross circuit has a non-coboundary δ yet
  d_circ = 10 = d_ext, so a nontrivial class is needed but the light logicals decide.
- **K4 Lifting as difference constraints (Theorem 4 + Corollary 5).** Fixing how each column is realised, lifting
  an extended logical is a system x_a − x_b ≤ c; it is infeasible iff there is a negative cycle; the simplest
  certificate is two hooks read in opposite orders by two private readers (holonomy around a 4-cycle of the
  overlap graph); Fig. 1(b) shows it for the period-11 gross circuit, where every weight-10 extended logical has
  such a certificate of holonomy 2, robust to one readout flip.
- **K5 Lemma 3 (pair obstruction).** If a two-qubit hook is flat (G constant on the checks it meets oddly) and the
  pair lies in a weight-d logical, one hook replaces two data errors and d−1 faults suffice; for both codes every
  pair of check qubits lies in a weight-d logical of each type; in a non-interleaved circuit every hook is flat,
  which yields SBB's Prop. 4 bound without its numerical search (see ledger, item L-12 for the status of this
  sentence).

### Proof of Theorem 1 (≈ 600 words)
- **P1 Period 8.** Every one of the 17,424 signatures of T(8) has a flat pair hook (first or last pair of the X or
  Z order), so Lemma 3 gives d_circ ≤ d−1 for both codes; for [[90,8,10]] explicit witnesses give ≤ 8.
- **P2 Periods 9 and 10.** Explicit undetected fault patterns (a pair hook plus re-timed data errors, and
  multi-hook lifts of light extended logicals) cover every legal timing vector of T(9) for both codes and T(10) for
  [[90,8,10]]; coverage is certified two ways (DRAT proofs of the SAT encodings, and an exhaustive SAT-free check
  over all canonical timing vectors, 10,271,304 at P = 10), and each pattern is a nontrivial logical verified by
  stim injection; in sampled cases the witnesses are already undetected at R ≥ 2.
- **P3 Attaining circuits.** Table II gives the period-10 gross circuit and the period-11 [[90,8,10]] circuit;
  Theorem 4 applies (window conditions hold, no zero-image hooks, d ≤ d_ext + 2), the complete lists of extended
  logicals of weight d_ext and d_ext+1 (3204 / 121,104 and 585 / 16,830 per basis) have zero bulk lifts, and a
  weight-d data logical after initialisation gives the upper bound; an exhaustive search of the full DEM, which uses
  neither the extended code nor the lemmas, confirms no lighter logical at R = 1–3 in both bases (gross) and at R = 1, 2 in the X basis ([[90]]; ledger L-5).
- **P4 Period 8, best values.** The gross circuit of period 8 in Table II reaches 11 for every R (same criterion
  with target 11 ≤ d_ext + 2), equal to SBB's non-interleaved Fig. 12 circuit, which is outside T; IBM's [[90,8,10]]
  circuit attains 8.
- **P5 Period-11 gross circuit and optimality within a signature.** The earlier-known period of 11 for the gross
  code is not optimal in T; the period-11 circuits are period-optimal within their own signatures (period lemma,
  End Matter), so the gain at P = 10 comes from a different offset pattern, not from compressing the same one.

### Cost (≈ 250 words)
- **C1 Idle cost under SD6.** Two or three extra idle layers per round; at p = 2×10⁻³ the period-10 gross circuit
  has a per-round logical error rate about 2.3 times lower than the period-11 one but about ten times higher than
  IBM's depth-8 circuit with the same BP-OSD decoder; the [[90,8,10]] circuit is worse than IBM's by 6–9
  (BP-OSD) / 9–17 (Relay-BP).
- **C2 When distance pays.** Without idle errors the [[90,8,10]] circuit is below IBM's at every sampled p in
  2–5×10⁻³ with both decoders (0.52 [0.44, 0.62] at 3×10⁻³), indistinguishable at λ = 0.1; one sentence on the
  neutral-atom model with its two decisive assumptions (or SM pointer only, decision Q3).

### Discussion and open questions (≈ 250 words)
- **D1 What the theorem says and does not say.** Scope stated once: translation-invariant, one CNOT timing per check
  type, separate reset and measurement layers, SD6; per-check timings, merged measure-reset layers, multiple
  ancillas and other noise are outside.
- **D2 Open questions.** Shortest period without translation invariance; whether d_circ = d is possible at period
  8 for the gross code outside T; an analytic proof of the P = 9, 10 bounds; whether the window conditions are
  necessary; criterion for d ≥ d_ext + 3 (larger codes).
- **D3 Method transfer.** The criterion is a finite R-independent computation; one sentence that it transfers
  directly (the period-11 template gives d_circ = 10 for [[108,8,10]], SM) and fails for [[90]] with the same labels,
  so labels must be chosen per code.

### Data availability (≈ 50 words)
- Circuits, lists, witness patterns, certificates, scripts at [Zenodo DOI].

---

## 5. Statements exactly as they will appear

**Definition (class T(P)).** Let A = A₁+A₂+A₃ and B = B₁+B₂+B₃ define a BB code. A syndrome-extraction schedule
is in T(P) if (i) every check has one ancilla, which is reset, coupled to its six data qubits by CNOTs and measured,
in that order; (ii) all X checks share CNOT times t_X(ℓ), ℓ ∈ {A₁,…,B₃}, and all Z checks share t_Z(ℓ), the j-th
round adding jP; (iii) the six times of each type are distinct and span at most P−3 steps, leaving one step for
reset before and one for measurement after; (iv) the six CNOTs on every data qubit fall on distinct steps modulo P;
(v) the measured operators are the checks, i.e. for every overlapping X and Z check the two shared qubits see the
same relative round. CNOT orders are arbitrary and rounds may wrap around the period. Faults are SD6 with the
CNOT template.

**Theorem 1 (optimal periods).** Under SD6 noise:
(a) for [[90,8,10]], every circuit in T(8) has d_circ ≤ 8 and every circuit in T(9) or T(10) has d_circ ≤ 9;
(b) for the gross code [[144,12,12]], every circuit in T(8) or T(9) has d_circ ≤ 11;
(c) the circuits of Table II, in T(10) for the gross code and in T(11) for [[90,8,10]], have d_circ = d in both
memory bases for every number of rounds R ≥ 1, and the period-8 gross circuit of Table II has d_circ = 11 for
every R.
The bounds in (a), (b) hold for every sufficiently large number of rounds. Hence, in T, the minimum period with
d_circ = d is 10 for the gross code and 11 for [[90,8,10]], and the largest d_circ at period 8 is 11 and 8.
[The "8 at period 8 for [[90]]" being attained needs IBM's lower bound; see ledger L-6.]

**Proposition 2 (round-offset cochain).** Suppose every overlapping X and Z check share exactly two data qubits,
and let δ(c,z) be the instance of Z check z that first reads an error deposited by instance 0 of X check c on a
shared qubit. (a) The circuit can be relabelled, instance by instance, into one in which each X instance acts on
every shared qubit between two consecutive instances of each overlapping Z check if and only if
δ(c,z) = b_z − a_c for integers a, b, i.e. δ is a coboundary. (b) In that case every extended-code logical is
realised by undetected faults, and d_circ ≤ d_ext for sufficiently many rounds. (c) If δ is constant in the
standard labelling, (b) holds for every R; this is SBB's Cor. 1. For a translation-invariant BB circuit δ is a
3×3 integer matrix, and it is a coboundary iff its nine entries are equal.
[Followed by one sentence: a non-coboundary δ is necessary for d_circ > d_ext in the bulk but not sufficient;
IBM's depth-8 gross circuit is the counterexample.]

**Lemma 3 (pair obstruction).** Let a circuit be in T(P), and let S be the residual of a hook that leaves the last
two qubits of the X-check order, or the last four (equal modulo the check to the first two); the Z-check order
in the X basis is symmetric. Suppose G is constant
on the overlapping Z checks that S meets an odd number of times. If the two qubits of S (respectively the first two)
lie in the support of a weight-d logical of the code, then for sufficiently many rounds there is an undetected set
of d−1 faults that flips this logical. For the gross code and for [[90,8,10]] every pair of qubits in a check lies
in a weight-d logical, for both check types.
[End Matter: the general form with cost: |L| − |T| + 1 + min_v Σ_{e∈E(S)} |G(e) − v| faults.]

**Theorem 4 (lifting criterion).** Fix a memory basis and a target t ≤ d with t ≤ d_ext + 2. Assume the window
conditions (the unrolled circuit's reader instances −1 and R read before the first and after the last layer) and
that no hook residual has zero syndrome and zero logical image. If, for every w with d_ext ≤ w ≤ t−1, no extended
logical of weight w together with at most t−1−w readout flips can be realised by undetected faults in the bulk,
then d_circ ≥ t for every R ≥ 1.

**Corollary 5 (negative cycles).** For a fixed choice of realisation of each column and pairing at each reader,
the realisability of an extended logical is a system of difference constraints, infeasible iff its constraint
graph has a negative cycle. In particular, if the logical contains hooks of X checks c and c′ with two Z checks z,
z′ that meet no other of its columns and δ(c,z) − δ(c′,z) ≠ δ(c,z′) − δ(c′,z′), it cannot be realised.

End Matter lemmas (text drafted at writing time): A1 reduction + light logicals (|F| = |S| + z + 2c); A2 window
lemma (finite undetected sets embed in the bulk; inclusion only); A3 period lemma (a signature is realisable at
period P iff a difference system has no positive cycle; the signatures of the period-11 circuits have minimum
period exactly 11).

## 6. Figures and tables

- **Fig. 1 (conceptual, double column, aspect ≈ 2.4 ⇒ ≈ 290 words).** (a) The overlap graph of an X check with its
  nine Z checks and δ as an integer label on each edge: constant (non-interleaved), a coboundary (re-timable), and
  the period-11 gross circuit's δ = −[j ≠ B₁] (not a coboundary). (b) The negative cycle on u11's list-0 weight-10
  extended logical, Z basis: hooks X45 (residual of length 4) and X59 (length 2), private readers Z58 and Z60,
  holonomy 2 — the same logical as the old Fig. 1(b), but the bulk certificate, not the R = 1 X45/X48/Z69 story
  (ledger L-9). (c) Pair obstruction cartoon: a flat pair hook replacing two data errors of a weight-d logical.
  Figure data must be regenerated from the theory-B audit outputs, not from `fig1_u11_data.json`.
- **Table I (single column, ≈ 13 + 6.5×9 ≈ 75 words): period vs best d_circ in T.**

  | P | gross: bound in T | gross: attained | [[90,8,10]]: bound in T | [[90,8,10]]: attained |
  |---|---|---|---|---|
  | 8 | ≤ 11 | 11 (Table II); IBM 10 (R ≤ 12); SBB Fig. 12: 11, not in T | ≤ 8 | 8 (IBM) |
  | 9 | ≤ 11 | open (decision Q2) | ≤ 9 | open |
  | 10 | 12 | **12** (Table II) | ≤ 9 | open |
  | 11 | 12 | 12 (u11) | 10 | **10** (c11) |

  If the PI prefers a plot, the same data as Fig. 2 (single column); the table is cheaper in words.
- **Table II (double column, ≈ 26 + 13×6 ≈ 105 words).** Reset step, CNOT order, CNOT steps, measurement step for
  X and Z checks of: gross period 10 (X order A₁A₂B₁A₃B₂B₃, steps 0,1,2,3,4,7; Z the reverse order, wrapping),
  gross period 8 (11), [[90,8,10]] period 11 (from O6 Table I). Exact rows regenerated from the specs at writing.
  u11 appears only in Fig. 1 and Table I.

## 7. What moves where

**End Matter (≤ 2 pages).** Proof of Proposition 2; Lemma A1 and proof; window lemma A2; proof of Theorem 4;
general Lemma 3 with cost and its proof; the pair table (which pairs/triples lie in weight-d logicals); period
lemma A3.

**SM, ordered by the main text.**
- S1 Notation, SD6 template, staircase model and the fault-to-model correspondence table (every SD6 fault component
  is one model fault); equality of model and DEM signature sets for all circuits used.
- S2 δ for all circuits used (u11, c11, g10, g8, IBM, segmented controls), with the coboundary test.
- S3 Theorem 4: window conditions per circuit, solvers, the two-hook certificates for u11 (all 144), statistics
  for c11 (405/585 hook-only), the remark that the period-10 and period-8 gross circuits need exact solving.
- S4 Class T(P): canonical form, enumeration counts (22,608 / 784,944 / 10,271,304 vectors; 17,424 / 67,536 /
  267,984 signatures), signature lemma, determinism lemma.
- S5 Period 8: flat-pair exhaustion over T(8), explicit witnesses, pair-property witnesses (60 logicals).
- S6 Periods 9, 10: witness patterns, CNF encoding, DRAT certificates (5), SAT-free exhaustive re-check, injection
  tests, minimal-R sampling.
- S7 Attaining circuits: g10 (lists, lifts, direct DEM R = 1–3, upper bound), c11 (lists, lifts; older R ≤ 25 lift
  certificates as a second proof), g8 (lists, lifts, weight-11 witnesses for many R).
- S8 Period-8 references: IBM gross d_circ = 10 for R ≤ 12 (certificates), SBB Fig. 12 d_circ = 11 (d_ext = 11 with
  SBB Prop. 3 / Cor. 1), IBM [[90]] = 8 (cited).
- S9 Logical error rates (g10, u11, c11, IBM; λ = 0, 0.1, 1); S10 neutral-atom model (if kept, Q3).
- S11 Transfer example: [[108,8,10]] with the period-11 template (d_circ = 10, any R) and the [[90]] failure.
- S12 Verification and data.

**Dropped from O6.**
- The "two theorems for two period-11 circuits" framing, the gap argument (G = 31, R′ = 31/25) as the main proof
  (replaced by Theorem 4; may remain one SM sentence as an independent second proof for c11 and u11).
- Corollary on Fig. 12 as a headline; it survives as one Table I entry with an SM proof.
- Retimings of Fig. 12, period-18/21 circuits, the colour-symmetric family bound, the [[90]] "four order classes,
  P ≤ 10" family bound (superseded by Theorem 1(a)), the old period-18 mechanism figure.
- Morphing end-cycle code non-equivalence (SM S11 of O6) and its prior-work sentence.
- LER: u11 vs Fig. 12 at λ = 0 and the u11 λ = 1 numbers (u11 is no longer a headline circuit); the [[90]] c11
  λ = 0/0.1/1 comparison stays (cost paragraph); g10 vs u11 vs IBM at λ = 1 is added; the gross neutral-atom
  numbers stay out (confounded, as in O6); [[90]] neutral-atom per Q3.
- Certificates paragraph of O6 in the main text; replaced by one sentence in P2/P3 with exact scope (ledger L-15).

## 8. Word budget (core limit 3750)

| Section | Words |
|---|---|
| Introduction I1–I6 | 800 |
| Setting + Definition (display ≈ 4 rows = 64) | 410 |
| Theorem 1 | 150 |
| Key idea K1–K5 incl. Prop. 2, Lemma 3, Thm 4, Cor. 5 | 650 |
| Fig. 1 (double column) | 290 |
| Proof of Theorem 1 P1–P5 | 600 |
| Table I | 75 |
| Table II | 105 |
| Cost C1–C2 | 250 |
| Discussion D1–D3 | 250 |
| Data availability | 50 |
| **Total** | **≈ 3630** (≈ 120 words reserve) |

End Matter ≈ 1,400–1,600 words (two pages). O6 core was ≈ 2,740 words of text plus Table I and the Fig. 1 block.

## 9. References

**Add:** Li, Gan, Wu, Zhang, Zhang, Liu, arXiv:2509.26494 (parity obstruction, depth 7 optimal, single round); Zhang
et al., arXiv:2603.21499 (no depth-6 circuits, SMT); Delfosse, Beverland, Tremblay, arXiv:2109.14599 (depth bounds
under locality); Liang et al., arXiv:2609.37231 (fault-response certificates; check against existing Liang2026
entry); Ghosh et al., arXiv:2610.03429 (LP upper bounds on circuit distance); Dennis, Kitaev, Landahl, Preskill,
quant-ph/0110143 (hooks); Durazo Rocha et al., arXiv:2609.40319 (even-parity interleaving constraint); Kishony et
al., arXiv:2602.09099 (minimum period for surface-code hook schedules, contrast); tool citations: CaDiCaL,
drat-trim, cake_lpr, VeriPB; a standard reference for difference constraints / Bellman–Ford.
**Keep:** Bravyi et al.; Strikis–Browne–Beverland (Props. 3–5, Cor. 1, Sec. II.1, App. F, G.2); Tesseract;
Webster–Jacob–Higgott; Manes–Claes; Shaw–Terhal 2025 (PRL 134, 090602); Wills et al.; Xu et al.; Hirai et al.;
Tomita–Svore; Kishony–Fowler; Gidney (SD6, SI1000, stim); Crocker (IBM gross value).
**Drop if Q3 = drop neutral atoms from the paper entirely:** Evered, Bluvstein ×2, Muniz, Radnaev, Tsai, Viszlai
(they must stay if the SM keeps the neutral-atom section, since SM references must be in the main list).
**Drop:** Shaw–Terhal 2026 (2604.09797, fold), Nguyen et al. (screening; optional), Sun–Cai (optional), Bi–Chang–
Puri (only if the [[90]] prior-work sentence goes).

---

## 10. Claims ledger (internal; never in the paper)

| # | Claim as it will be written | STATE item | Audit | Required wording / limits |
|---|---|---|---|---|
| L-1 | Class T(P) definition (§5) | 28 | 2026-10-30-E-040-impossibility §1, §7 | Must include: one timing per check type, span ≤ P−3, distinct mod P on data, determinism, arbitrary order, wrap; SD6 + CNOT template. Outside: per-check timing, merged measure–reset, multiple ancillas, non-SD6 |
| L-2 | [[90]] T(8) ≤ 8; T(9), T(10) ≤ 9; gross T(8), T(9) ≤ 11 | 28 | E-040-impossibility (all 5 CONFIRMED) | "for sufficiently many rounds", never "every R"; may add "in sampled cases already at R ≥ 2"; certified by DRAT + SAT-free exhaustive check |
| L-3 | g10 (period 10) d_circ = 12, every R, both bases | 27 | 2026-10-30-E-040-circuits §3–4, §9 | Single-ancilla, CNOT template, SD6; distance only. No certificates for its lists/lifts (two independent enumerations, two solvers, direct DEM R = 1–3) — see Q1 |
| L-4 | g8 (period 8) d_circ = 11, every R | 27 | E-040-circuits §5, §9 | Only **ties** SBB Fig. 12 (11); higher than IBM (10) by one; never "period-8 record"; criterion applied with target t = 11 ≤ d_ext + 2 |
| L-5 | c11 (period 11) d_circ = 10, every R; c11 period-optimal in T | 17, 26, 28 | 2026-10-22-E-030; 2026-10-29-theoryB §5; E-040-impossibility §5 | Earlier proof (R ≤ 25 lifts + gap) and criterion route both valid; certificates per item 20 for the older route |
| L-6 | [[90]] best at P = 8 is 8, attained by IBM | 28, 14 | E-040-impossibility §7 | Upper bound ours; "= 8" needs IBM's lower bound from Tesseract MaxSAT (2503.10988), which is for their round count — cite with that qualifier |
| L-7 | IBM gross depth-8: d_circ = 10 for R ≤ 12, in T(8) | 23 | 2026-10-26-E-037; E-040-circuits §5 | "for every R ≤ 12", SD6 and IBM's model; never unqualified |
| L-8 | SBB Fig. 12 d_circ = 11, not in T | 3 | 2026-10-05-E-014 | Combined with SBB Prop. 3 / Cor. 1 |
| L-9 | Fig. 1(b) negative cycle: u11 list-0 logical, hooks X45 (len 4), X59 (len 2), readers Z58, Z60, holonomy 2; all 144 weight-10 logicals of u11 have such certificates (both bases) | 26 | 2026-10-29-theoryB §4; 2026-10-22-fig1-u11 | Must use u11, **never g10/g8** (their non-liftability has no short certificate: g10 1224/3204 with holonomy 1 only, g8 0/432). Old R = 1 story (X45/X48/Z69) is a different certificate of the same logical; do not mix in one panel |
| L-10 | Prop. 2 (coboundary ⇔ re-timable; bulk d_circ ≤ d_ext; constant δ ⇒ SBB Cor. 1 for every R) | 26 | theoryB §2 | Bulk statement; finite-R only for constant δ (SBB case). Requires |Q| = 2 (holds for gross, [[90]], [[108]]; not bb18). Novel (lit 2026-10-30, mid-high) |
| L-11 | Non-coboundary δ necessary, not sufficient (IBM depth-8 gross) | 26 | theoryB §2 item 3–4 | IBM twist is on A₂ (not B₁ like u11); never say d_circ < d_ext |
| L-12 | Lemma 3 pair obstruction; pair property for both codes; T(8) ⇒ ≤ d−1 | 28 | E-040-impossibility §5 (Lemma F, table (iii) 60/60, Thm 1 22,608/22,608) | "every T(8) signature has a flat pair hook" is an exhaustive check, not a hand proof. The sentence "replaces the numerical step of SBB Prop. 4" (non-interleaved, not translation-invariant, every R) is **not audited**: needs a short audit before use, else restrict to "within T and in the bulk" and say "the mechanism behind SBB's Prop. 4 is a pair-covering property" (lit note 2026-10-30 §3: partially known) |
| L-13 | Theorem 4 criterion with hypotheses t ≤ d_ext + 2, window conditions, no zero-image hooks | 26, 27 | theoryB §3–4; E-040-circuits §3a, §8.2 | Window conditions fail for most random schedules; checked per circuit; inclusion form (finite ⊆ bulk) only; general d ≥ d_ext + 3 not covered |
| L-14 | Corollary 5 negative cycles / two-hook certificate | 26 | theoryB §4 | Standard difference-constraint argument; novelty mid-high; phrase as making SBB's qualitative detection mechanism decidable |
| L-15 | Certificates: impossibility = DRAT (5 proofs) + SAT-free exhaustive; c11/u11 older routes VeriPB/DRAT/cake_lpr | 20, 28 | 2026-10-23-E-034; E-040-impossibility §4 | Never "all computational inputs are certified"; for g10/g8 no certificates (unless Q1 = certify); encodings generated by our code and cross-checked |
| L-16 | Period lemma; u11, c11 signatures have P_min = 11 | 28 | E-040-impossibility §5 | Within their own signatures only |
| L-17 | LER: g10 ≈ 2.3× better than u11, ≈ 10× worse than IBM under SD6 (λ = 1), p = 2×10⁻³, BP-OSD | 27 | E-040-circuits §7 | IBM multiple from pooled counts; λ = 0 not done for g10; p = 1×10⁻³ unresolved |
| L-18 | c11 vs IBM: λ = 0 below at every sampled p 2–5×10⁻³, both decoders (0.52 [0.44, 0.62] at 3×10⁻³ pooled); λ = 0.1 indistinguishable; λ = 1 worse 6–9× / 9–17× | 17 | 2026-10-22-E-030 | Never "beats IBM" without λ = 0 |
| L-19 | Neutral atoms ([[90]] c11 0.40–0.82 under three assumptions; reverses under unpaired-atom error) | 21 | 2026-10-24-E-035 §5 | Both decisive assumptions in the same sentence; gross not reported |
| L-20 | [[108,8,10]] template circuit d_circ = 10 any R; template fails on [[90]] | 26 | theoryB §6–7 | Example only, not a constructive theorem; E-013 already has a depth-8 [[108]] circuit at 10 |
| L-21 | Novelty of minimum-period bounds (high), δ cochain and negative cycles (mid-high), pair obstruction (partially known) | — | lit 2026-10-30-theory-novelty | Cite SBB Props. 4–5, Li et al., Zhang et al., Dennis et al. |

## 11. Open decisions for the PI (≤ 3)

**Q1. Certificates for the period-10 gross circuit before submission?**
(a) Submit as is: g10 rests on two independent list enumerations, two independent bulk solvers and a direct DEM
search at R = 1–3; the paper says certificates cover the impossibility results and the period-11 circuits.
(b) First certify g10 (VeriPB for d_ext = 10 and the 3204 / 121,104 lists; DRAT for the bulk lift instances), then
submit with "every infeasibility claim is certified". (Recommended: b — g10 is now the headline circuit; cost is
mainly CPU, the list sizes are larger than u11's.)

**Q2. The open cells of Table I (gross P = 9; [[90]] P = 9, 10)?**
(a) Leave them as upper bounds only ("open" in the table).
(b) Run one more experiment to determine the best d_circ in T(9) (gross: is 11 attained?) and T(9), T(10)
([[90]]: is 9 attained?), so the table is complete. (Recommended: b — it completes "best d_circ vs period" and is
cheap with the existing enumeration; if it fails within budget the cells stay "open".)

**Q3. Where does the neutral-atom analysis go?**
(a) One main-text sentence in the cost paragraph + SM section (references stay).
(b) SM only, no main-text mention.
(c) Drop from this paper (saves seven references; can go to a later paper). (Recommended: a.)
