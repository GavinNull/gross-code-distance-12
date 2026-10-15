# Outline for revision L (one method, two codes)

Sources: `research/literature/2026-10-12-paper-structure-study.md` (structure), STATE items 3, 7, 9, 10, 12–15 and their
audits (content), `research/literature/2026-10-15-bb90-novelty.md` (citations and novelty wording).
Principle: lead with the result; each limitation stated once, where its claim is made.

## Title options
1. Interleaving recovers the full circuit distance of bivariate-bicycle codes  ← working title
2. Single-ancilla syndrome circuits beyond the extended-code bound: distance 12 for the gross code and 10 for [[90,8,10]]
3. Certified single-ancilla syndrome circuits that reach the code distance of the gross and [[90,8,10]] codes

## Abstract (≈ 170 words, 6 sentences)
1. Single-ancilla syndrome circuits for BB codes are capped by SBB's bound: every non-interleaved circuit has d_circ ≤ d_ext, which for the gross code is at most 11 and for [[90,8,10]] at most 8.
2. We show that interleaving recovers the full code distance: we construct single-ancilla interleaved circuits with d_circ = 12 for the gross code, answering SBB's open question, and d_circ = 10 for [[90,8,10]], two above every non-interleaved circuit.
3. Both are proven under SD6 noise for every number of rounds and both memory bases.
4. The method fixes a low-distance extended code and turns circuit design into a finite, certified decision problem over its low-weight logicals.
5. A direct search on the detector error model confirms both results independently of the extended code; we also confirm SBB's conjecture d_circ = 11 for their original gross circuit.
6. Cost in one clause: periods 18 and 16 time steps per round, against 8 for the IBM circuits.

## Main text
- **Intro P1.** BB codes and the gross code; d_circ is the distance a circuit actually delivers.
- **Intro P2.** SBB: extended code, Prop. 3 (d_circ ≥ d_ext), Cor. 1 (= for non-interleaved), Prop. 4 (gross ≤ 11) and their open question; for [[90,8,10]] the best known value is 8, proven exact for the IBM circuit by MaxSAT.
- **Intro P3.** We show that interleaving lifts d_circ above every order's d_ext — by 1 for the gross code (12, Theorem 1) and by 2 for [[90,8,10]] (10, Theorem 2) — with a general method (Fig. 1) that turns design into a certified finite problem; Fig. 12 = 11 follows; cost stated in one sentence.
- **Intro P4.** Prior work in 4–5 sentences: exact distances (HGP, Webster, certificates); morphing (other code); Tesseract's exact 8 for IBM [[90]]; Bi–Chang–Puri's biased-noise upper bound 10 for the unchanged IBM circuit; Nguyen's screening proposal; check-dependent orders.
- **Setting.** Memory experiment, single-ancilla template with pipelining, SD6, DEM-mechanism counting; residuals, extended code, Table I property.
- **Key idea (Fig. 1, gross mechanism).** Invariance of the extended code under ⟨rev, s12, s56⟩; timing decides lifting; parity-cycle example; audited typicality sentence.
- **Two general lemmas.** Lemma 1 (reduction to extended logicals; proof here, template-level details in SM S5). Lemma 2 (structure at weights d_ext and d_ext+1: distinct columns, or d_ext columns plus one zero-image fault).
- **Construction + Table I (gross, 6 classes) + Table II ([[90]], 2 rows) + Fig. 2 (gross timing).** SAT search with blocking clauses; the two circuits' properties.
- **Theorem 1 (gross).** Proof: Lemma 1 + Lemma 2 at weight 11; finite computation R ≤ 32 (DRAT-certified; inputs from two exhaustive searches — limitation stated here once); gap argument; upper bound. Corollary 1 (Fig. 12 = 11; retimings obstructed).
- **Theorem 2 ([[90]]).** Every per-check order has d_ext ≤ 8 (DRAT-verified) ⇒ every non-interleaved circuit ≤ 8, attained. Proof for c16: Lemma 1 (weight ≤ 7); Lemma 2 at weights 8 and 9 over complete lists 585 / 16830 incl. readout-flip case; lift R ≤ 12 zero; round splitting ⇒ every R; weight-10 injection.
- **Direct cross-check.** One paragraph: exact branch-and-bound on the full DEM (same family as S4, independent implementation, R=1 reproduced by a second implementation): gross R = 1 exactly 12, R = 2, 3 none ≤ 11; [[90]] none ≤ 9 for R ≤ 12 ⇒ with round splitting a proof of Theorem 2 without the extended code.
- **Optimality (gross).** Minimal colour-symmetric periods 18/21 in the bulk frame model (scope clause once); order class forced among coset colourings; less symmetry open.
- **Discussion.** Method generality; Cost and outlook: gross idle-noise results (as rev. k), [[90]] period 16 with 3 empty layers vs IBM 8 steps, LER not evaluated for [[90]]; shorter periods next; scope sentence.
- Data availability; AI use.

## Supplemental Material (main-text order)
S1 notation/noise (both codes) · S2 circuits (gross A, B, C; [[90]] c16 and controls) · S3 invariance · S4 d_ext = 11 and 4224 list · S5 proof of Lemma 1 · S6 Lemma 2 and lift computations (gross) · S7 gap argument · S8 upper bounds · S9 [[90]]: d_ext ≤ 8 for every order (DRAT), lists 585/16830, case analysis, lift R ≤ 12, controls, round splitting · S10 direct DEM search · S11 Fig. 12 and retimings · S12 search and optimality · S13 idle-noise sensitivity · S14 verification and data.
