# Outline for revision O (two codes, both gap two, both period 11)

Sources: STATE items 16–19 and audits 2026-10-22-E-032 / -E-030 / -E-033 / -E-031 (new); items 3, 7, 9–15 and
their audits (kept). PRL format: core ≤ 3750 word-equivalents, End Matter ≤ 2 pages, confident tone, each limitation
once.

## Title
Keep: "Interleaving recovers the full circuit distance of the gross and [[90,8,10]] bivariate-bicycle codes"
(still exact: both codes, both full distance).

## Abstract (≈ 150 words)
1. SBB's bound: non-interleaved single-ancilla circuits have d_circ ≤ d_ext; for the gross code ≤ 11, for [[90,8,10]] ≤ 8.
2. We construct period-11 single-ancilla circuits reaching the full distance — 12 for the gross code (answering SBB's question) and 10 for [[90,8,10]] — two above the extended-code distance of their CNOT orders, proven for every number of rounds.
3. Method: choose an order class, even one of lower d_ext, and recover d by exact lifts over the complete lists of extended logicals of weight d_ext and d_ext+1; infeasibility claims carry checked certificates.
4. Practical consequence in one sentence: without idle noise the full distance lowers the logical error rate at p ≈ 3×10⁻³; with standard idle noise the longer period costs more than it gains.

## Main text
- **P1** BB codes; d_circ as the figure of merit.
- **P2** SBB: extended code, Prop. 3, Cor. 1, Prop. 4 (gross ≤ 11), open question; IBM gross circuit d_circ = 10 for R ≤ 3 by exact enumeration; [[90]]: 8 exact for IBM (MaxSAT), every order has d_ext ≤ 8.
- **P3** Result: two period-11 circuits (Table I), d_circ = d, gap two over their own d_ext and over every non-interleaved circuit (Theorems 1, 2); method; Corollary 1 (Fig. 12 = 11); cost sentence.
- **P4** Prior work (as rev. N).
- **Setting** + extended code + the precise meaning of "interleaved" used here (not segmentable; pipelining makes a Z instance straddle the next X instance).
- **Table I** both period-11 circuits (two rows per code: X and Z type; reset, order, steps, measurement).
- **Two lemmas** (Lemma 1 reduction; Lemma 2 light logicals at d_ext and d_ext+1, with zero-image = readout flips).
- **Theorem 1 (gross, period 11)** proof sketch: uniform class with d_ext = 10; lists 144 / 7344; lift R ≤ 31 zero; gap argument (G = 31, R' = 31, End Matter); weight-12 injection. Direct DEM search R = 1, 2.
- **Theorem 2 ([[90]], period 11, also periods 12 and 16)**: every order d_ext ≤ 8 (DRAT) ⇒ non-interleaved ≤ 8; lists 585 / 16830; lift R ≤ 25 zero (two independent chains); gap argument R'_9 = 25; injection. Family bound: within translation-invariant schedules with orders in a d_ext = 8 class, no P ≤ 10 (bulk).
- **Certificates** one paragraph (E-031 wording; u11 list completeness: status).
- **Corollary 1** (Fig. 12 = 11) and the retiming obstruction (End Matter); an earlier period-18 circuit in the Fig. 12 class (SM).
- **Logical error rates** compact: [[90]] c11 vs IBM depth-8 at λ = 0 (0.52 [0.44, 0.62] pooled at 3e-3; every sampled p 2–5e-3 both decoders), λ = 0.1 indistinguishable, λ = 1 worse 6–9× / 9–17×; gross u11 at λ = 0 below Fig. 12 with BP-OSD 3–5e-3 (0.31–0.56), comparable to IBM (0.64 [0.48, 0.85] pooled), λ = 1 worse 7 [4, 12] to 21–39; failures at λ = 0 dominated by decoder failures. Message: full distance pays off when idling is nearly free.
- **Discussion/outlook** method generality; shorter periods; scope sentence.
- Data availability; AI use.

## End Matter
Proof of Lemma 2; gap argument for Theorem 1 (G = 31, R' = 31) and Theorem 2 (R' = 25 / 12 / 12); details of Theorem 2; retimings of Fig. 12; family bounds (gross period-18 family; [[90]] P ≤ 10).

## SM
S1 notation and noise (both codes); S2 proof of Lemma 1; S3 period-11 gross circuit (circuit, non-segmentability, lists, lift, gap, upper bound, controls); S4 [[90,8,10]] (bound, lists, periods 11, 12, 16, family bound); S5 direct DEM search; S6 certificates; S7 logical error rates (period-11 circuits; IBM gross d_circ = 10 for R ≤ 3; earlier period-18 data); S8 Fig. 12 (d_ext = 11, 4224 list, retimings, Table); S9 earlier period-18 gross circuits (construction, proof, frame-model period bound, uniqueness of the class, timing diagram, mechanism figure); S10 verification and data; S11 morphing end-cycle code.

## Figure
Fig. 1 (old) explains the period-18 circuit's mechanism; it does not explain the period-11 circuit, whose order class has d_ext = 10 and whose distance comes from pipelining. Revision O moves the old Fig. 1 to SM S9 and has no main-text figure until a new Fig. 1 is commissioned (request in the report).
