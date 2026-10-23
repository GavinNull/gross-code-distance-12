# Claims map for `paper/draft.tex` (revision d, 2026-10-12: headline = STATE item 13 / cs_P18_H24; items 10, 12 also used)

**Revision O4 (2026-10-24).** E-034 audited CONFIRMED (`research/audits/2026-10-23-E-034.md`, STATE item 20): C58
upgraded from "pending audit" to "every infeasibility claim used in the proofs of both theorems is accompanied by a
checked certificate" (abstract, main text Certificates paragraph, SM S6), with the audit's qualifiers kept; SM states
the ~18 GB memory for the W11 VeriPB check. E-035 not mentioned.


**Revision O3 (2026-10-23).** C56 framing: SBB 2603.05481 v2 App. H Prop. 5 (verbatim check by the lead: every
uniformly tiled non-interleaved gross SEC has d_circ ≤ 10); the period-11 circuit is uniformly tiled and interleaved
⇒ +2 within that class, +1 over the best non-interleaved circuit (11). [[90]] +2 already at period 16; new: period 11.
C55 wording: "exactly 10 under SD6 for R ≤ 3 (exact enumeration); previously only ≤ 10" (2308.07915, 2506.03094,
2503.10988). New citations from `research/literature/2026-10-22-period11-novelty.md`: 2308.08648 (pipelined
product-coloration circuits; abs page checked), 2603.01628 (surface-code interleaving; abs page checked), SBB App. F and
App. G.2, SI1000 (2108.10457) for λ = 0.1. C58: u11 list-completeness certificate and c11 lifts to R ≤ 25 (E-034)
written as "produced, pending audit".


**Revision O2 (2026-10-22): new Fig. 1 (`figures/fig1_u11.pdf`).** New tag C61: the mechanism example of Fig. 1(b)
and the sentence in "The circuits" (a readout falls between the arrivals of two hook residuals on the same data qubit:
X45's hook reaches qubit 123 at tick 6, X48's at tick 10, Z69 reads it at tick 8, so its detector fires; in the
segmented control, same orders, X block steps 1–6, Z block 8–13, period 15, both arrivals precede the read and the
weight-10 logical lifts, injection-verified). Source: `paper/figures/fig1_u11_data.json` (figure agent, lead's facts).
**Audited** (`research/audits/2026-10-22-fig1-u11.md`): example CONFIRMED (both Z69 detectors are forced; wording
fixed); the "straddle" wording REFUTED and replaced; typicality used only in the audited form (all 144 lift in the
segmented circuit, none in the period-11 circuit at R = 1; three or four Z checks see two hook residuals on opposite
sides of their read; a single detector forbids each lift). Never 96/30/66/6/33/9. Fig. 1(a) facts (XXX then ZZZ; 6-cycle witness) are C56 (E-032 audit §1). Fig. 1(c)
shows G = 31 also for the [[90]] circuit; this follows from its constants (D = 11, starts {0, 1}, Δ = 10; E-030
audit §1), the same as the gross circuit's.


**Revision O (2026-10-22): two codes, both gap two, both period 11.** Outline `paper/outline_O.md`.

| tag | claim in draft (short) | STATE item | audit | data | scope / wording constraint |
|---|---|---|---|---|---|
| C55 | IBM's depth-8 gross circuit: exactly 144 (Z) / 288 (X) weight-10 undetected logicals per round, constant for R = 1–3, none lighter for R ≤ 3 (exact enumeration) ⇒ d_circ = 10 for up to three rounds | 18 | `research/audits/2026-10-22-E-033.md` §5a | `results/E-033-*` | Always "for up to three rounds" / "R ≤ 3"; lower bound rests on the audited ccsearch completeness |
| C56 | Period-11 gross circuit (Table I; `search/experiments/e032/u11_spec.json`): translation invariant, wrapping, legal, deterministic; not segmentable (mixed strongly connected components, 6-cycle witness) although each data qubit does XXX then ZZZ per period; uniform class of A1A2A3B3B1B2, d_ext = 10, lists 144 / 7344 (two enumerations); zero-image = 72 readout flips per round; lift R = 1..31 zero (three implementations); G = 31, R' = 31; weight-12 injection R = 1,2,3,6,10,31; direct DEM R = 1, 2 none ≤ 11; controls (period-10: 432/576; segmented: 144/144/7344); ~1/70 random schedules pass the R ≤ 2 screen | 16 | `research/audits/2026-10-22-E-032.md` §1–7 | `results/E-032-gross-short-period/`, `results/E-032-audit/` | "interleaved" only in the precise non-segmentable sense; no LER / depth claims; list completeness not certified |
| C57 | Period-11 [[90,8,10]] circuit (Table I; `search/experiments/e030/c11_spec.json`) and period-12 circuit: d_circ = 10 every R, both bases; same extended code as c16 (585 / 16830); c11 lift R ≤ 25 by two independent chains, R'_8 = 22, R'_9 = 25; c12 R' = 12; injection R = 1,2,5,11. Family bound: translation invariant, orders in one of four d_ext = 8 classes, P ≤ 10 bulk UNSAT 48/48 | 17 | `research/audits/2026-10-22-E-030.md` §1–2 | `results/E-030-bb90-period-ler/`, `results/E-030-audit/` | Never "11 is the minimal period"; family bound bulk-only and class-restricted |
| C58 | Certificates: every infeasibility claim used in the proofs of both theorems (and of the c16 result) has a checked certificate. u11: VeriPB d_ext ≥ 10 and 144/7344 list completeness (both bases), DRAT/drat-trim + LRAT/cake_lpr lifts R ≤ 31. c11: VeriPB d_ext ≥ 8 and 585/16830 lists (c16 extended code), DRAT lifts R ≤ 25 (both bases); c12 lifts R ≤ 12; c16 lifts R ≤ 12. W11 proofs 4.6e11 bytes checked as streams, SHA-256 recorded, ~18 GB memory. Fig. 12 d_ext ≥ 9 certified. Verdict "s VERIFIED UNSATISFIABLE" | 19 | `research/audits/2026-10-22-E-031.md` §1–5; `research/audits/2026-10-23-E-034.md` §1–5 (STATE item 20) | release certificates | Keep qualifiers: encodings generated by our code, cross-checked against independent implementations; Lemma 1 / Table I and any-R reduction are mathematical arguments with computationally verified premises. Never "all computational inputs are certified" / "fully formally verified" |
| C59 | [[90]] LER: λ = 0 c11 below IBM depth-8 at every sampled p 2–5e-3, both decoders; 3e-3 BP-OSD pooled 0.52 [0.44, 0.62] (independent 0.57 [0.47, 0.70]); λ = 0.1 indistinguishable; λ = 1 worse 6–9× (BP-OSD), 9–17× (Relay); leading order IBM 315/540 weight-8 per round, c11 24507 weight-10; crossing estimate indicative | 17 | `2026-10-22-E-030.md` §3–4 | as C57 | No "beats IBM" without λ = 0; no "monotone"; no 0.37 headline |
| C60 | Gross LER: λ = 0 u11 below Fig. 12 with BP-OSD at 3–5e-3 (0.31–0.56; 3e-3 independent 0.33 [0.23, 0.49]), Relay only 4–5e-3 (0.35–0.54); vs IBM comparable (0.64–0.96 point estimates; 3e-3 independent 0.73 [0.50, 1.05], pooled 0.64 [0.48, 0.85]); λ = 0.1 no resolved difference (intervals spanning 3–10); λ = 1 worse 7 [4, 12] (BP-OSD 2e-3) to 21–39 (3e-3); λ = 0 failures dominated by BP-OSD decoder failures; u11 weight-12 counts 69756 (R = 1) / 233244 (R = 2, Z), not converged | 18 | `2026-10-22-E-033.md` §1–6 | `results/E-033-*` | Never "beats/outperforms IBM"; never 0.53; never "163488 per round"; no X/Z asymmetry |

Moved to SM (history, S10–S16): the period-18/21 circuits (C31–C37, C41–C46, C49–C52), with the old Fig. 1 as an SM
figure and Table I of revision N as Table S3 (circuit A). The main text keeps Corollary 1 (C10, C11) and the Fig. 12
retiming obstruction (C14–C18, End Matter).


**Revision N (2026-10-21, third external review).** Numbers unchanged. C50: new SM Table S5 (λ = 1 per-round rates
with failure counts, from `research/journal/2026-10-14-E-026-gross-ler.md` lines 47–54 and audit
`2026-10-14-E-026.md` §2: p18/IBM = 1.52e3 [1.10e3, 2.14e3] at 2e-3); main text now says the "≥ 3 at 1e-3" is a
direct-sampling lower bound (IBM 0/20000, 95% upper 3.0e-5) and that the comparison is with BP-OSD (with Relay-BP at
1e-3 no ordering is established). C52: 0.37 [0.28, 0.49] marked as the independent re-sampling (Table S4 has
0.34 [0.19, 0.59]). C2: new SM S15 with the E-017 audit §4.2 computation (min stabiliser weight exactly 9 vs 6;
invariance under qubit permutations and local Cliffords), cited in the intro. C45: section renamed "Period lower
bound in the symmetric family", scope in its first sentence. C51: abstract now says every solver decision is
DRAT-certified and the extended-code inputs rest on independent exhaustive searches. All hard-coded SM numbers
replaced by \ref (fixes "in line with S9" → S11).


**Revision M (2026-10-17, PRL submission version).** No number, scope or audited claim changed; tags kept.
Tables I and II merged into one double-column Table I (`tab:circuit`; [[90]] rows at the bottom); former Fig. 2
(timing) moved to SM S2 as Fig. S1; Fig. 1 caption cut to 141 words. Moved to End Matter (after the references):
proof of Lemma 2, proof of Lemma 4 (gap argument), details of Theorem 2 (lists, readout-flip case, controls,
round splitting, upper bound), Fig. 12 retimings (C14–C18), optimality detail (C45–C47, C38). Abstract no longer
mentions Corollary 1 (stated in the intro). `paper/scripts/count_words.py` gives the PRL count.


**Revision L (2026-10-15): one method, two codes.** Outline in `paper/outline_L.md`.
New tags:

| tag | claim in draft (short) | STATE item | audit (file § section) | results / data | scope / wording constraint |
|---|---|---|---|---|---|
| C53 | [[90,8,10]]: c16 (Table II: X order A2A1A3B2B3B1 at 1,3,5,6,8,10; Z order B1B3B2A3A1A2 at 2,4,6,7,9,12; reset 0, meas 15, period 16, steps 11/13/14 empty; translation invariant; legal; deterministic; XZXZXZ interleaving) has d_circ = 10 for every R, both bases, SD6. Every per-check order: X-side d_ext ≤ 8 (SAT, 90 types / 54 admissible, 558 weight-10 X logicals, 17910 combinations, 3555 vars / 21690 clauses, CaDiCaL UNSAT, drat-trim VERIFIED) ⇒ non-interleaved ≤ 8 (SBB Cor. 1), attained (segctl lifts 585). Lists 585 (w8) / 16830 (w9) per basis (DFS + MITM identical); Lemma 2 case analysis (w8; w8 + zero image = readout flips, 45 per round; w9); lift R = 1..12 both bases 0, three implementations + R = 1 exhaustive; controls u16 315, segctl 585/540/16830; round splitting R' ≤ 12; weight-10 injection R = 1,2,3,6,10,13. Lemma 2 (general light-logical structure) is the audit's §1 counting argument. "First explicit single-ancilla circuits whose d_circ exceeds the d_ext of every choice of orders" (to our knowledge) | 14 | `research/audits/2026-10-15-E-028.md` §1–6; novelty `research/literature/2026-10-15-bb90-novelty.md` | `search/experiments/e028/c16_spec.json`; `results/E-028-bb90-interleaved/`, `results/E-028-audit/` | Period 16 vs IBM 8 steps; LER not evaluated; Z-side per-check-free d_ext not computed (not needed); "non-interleaved circuit with the same extended code attains 8" (segctl), not "with the orders of Table II". Tesseract 2503.10988 exact 8 for the IBM circuit; Bi–Chang–Puri 2606.30592 biased-noise upper bound 10 for the unchanged IBM circuit. Table II verified by `paper/scripts/check_tables.py` |
| C54 | Direct DEM search (ccsearch; same family as S4, independent implementation, different pruning; R = 1 reproduced by a second independent implementation, which also reproduced d_ext = 11 and the 4224 list; 1672 random known-answer instances): gross A R = 1 exactly 12, R = 2 (66 root cases) and R = 3 (96) none ≤ 11; weight-12 injection checked at R = 1, 2 (and S8). c16 R = 1..12 none ≤ 9, weight 10 found R = 1–3; u16 control 9. c16 any R via minimal logical + splitting (R' ≤ w + 3 ≤ 12) without extended-code input. R = 1 direct SAT on c16 DEM UNSAT (E-028 audit) | 15 (+14) | `research/audits/2026-10-15-E-029.md` §1–7 ("论文措辞"); E-028 audit §3 | `results/E-029-direct-dcirc/`, `results/E-029-audit/` | Never "different algorithms"; never "certificate" for these searches; R = 2, 3 for gross only root-case spot checks by the auditor (not a second full run) — the draft attributes only R = 1 to the second implementation |


**Revision k (2026-10-15, tone pass).** No number, scope or audited fact changed. Abstract and intro P3 lead with the
construction and Theorem 1; the method is stated as a general tool. Limitations now stated once each: frame-model scope
of the minimal periods (C45) in the "Optimality" paragraph; uncertified d_ext / 4224-list inputs (C11, C13) in the
Lemma 2 paragraph and SM S4/S12; practical cost (C44, C50, C52) in one "Cost and outlook" paragraph (λ* ≈ 0.3,
per-layer caveat, CX-native variant and the ⌈d/2⌉ / 26× coefficient statements are now in SM S11 only). Retiming
obstructions (C16) stated as proven for all Table S3 families.


**Revision i (2026-10-15).** **New C52 (E-026b, idle sensitivity, audited `research/audits/2026-10-15-E-026b.md`):**
main-text "Role of idle noise" paragraph = audit §7 wording, lightly adapted (numbers and caveats unchanged; "type-(b)
weight-12" rendered as "weight-12 families … one type of weight-12 logical is not enumerated"); abstract and
Discussion sentence (λ = 0 beats Fig. 12 at p = 4e-3; λ = 0.1 loses) from audit §2; SM S11 table = journal
`research/journal/2026-10-14-E-026b-idle-sensitivity.md` direct-sampling tables (per-round ratios; λ = 0, 0.1, 0.3,
si1000cx) + audit §2b independent re-sampling (0.37 [0.28, 0.49], 2.73 [2.14, 3.47]) + audit §4 layer counts
(18 = 12 CX-only + 6 M/R; Fig. 12 2 + 6; duration ratio 1.1–1.3) + audit §5 (compilation +11.8% / +6–9% mass) + audit
§3a/3b (A6 ratios 0.0104, 0.084, 0.84, 26; crossing ≈ 0.32; F = 0.3/2/3 → 0.50/0.24/0.20). Not used: "ties IBM",
"per unit time", calling si1000cx "SI1000", IBM λ ≈ 0.6. SM sections renumbered: S11 idle noise, S12 verification.
Final pass: no internal process strings in draft.tex; the only placeholder left is the Zenodo DOI.


**Revision h2 (2026-10-15).** C51 (E-027) is now **audited**: `research/audits/2026-10-15-E-027.md`, all CONFIRMED
(batches with selector disjunction checked structurally on 4 batches; 9 shipped and 3 regenerated large proofs and
4 lift-batch proofs reproduced byte-identically; 129 records). Text now: lift instances combined into batches by a
selector disjunction (unsat batch ⇒ unsat members), each batch DRAT-refuted, drat-trim + cake_lpr; 129 unsatisfiable
clause sets (104 all-logical obstruction/optimality + 25 length-2-only for Table S3), each with a DRAT proof;
"accompanied" = included if ≤ 100 MB, otherwise SHA-256 hash + byte-identical regeneration script. Table S3 len-2-only
re-runs "each accompanied by a DRAT proof" (note: of the 25, the auditor re-ran 10 and record-checked 15). S11 states
the certificates cover solver decisions only; template and Lemma 1 reduction are pen-and-paper / code-level (S5).
Limitation sentence kept verbatim.


**Revision h (2026-10-14).**
- C16: all Table S3 rows now re-solved UNSAT with only the 360/basis ten-data + one-length-2-residual logicals
  (the last 5 in `results/revg-len2only/run.log`) ⇒ daggers dropped, audit option (A) sentence used, Corollary 1's
  retiming claim restored to all Table S3 families. "Each accompanied by a DRAT proof" is NOT written for the
  len-2-only instances (pending lead confirmation); text says "(certificates in the data set)".
- **New C50 (E-026, LER):** STATE E-026 + audit `research/audits/2026-10-14-E-026.md` §4 (rows 1, 2, 4, 5, 7, 10;
  wording used: worse at every sampled p ≥ 1e-3; above pseudo-threshold for p ≥ 3e-3; ≈1.5e3× worse than IBM at
  2e-3; ≥ 3× at 1e-3 (direct bound); 3168 vs 288 idle locations, 2.8× fault mass; matched fault mass ⇒ alike;
  ⌈d/2⌉ = 6 for both; ≈26× coefficient for enumerated families). Not written: "no crossover with IBM at low p"
  (UNVERIFIED), the ≈4e2 extrapolation. Placeholder "[idle-noise sensitivity — pending E-026b]".
- **New C51 (E-027, certificates):** `research/journal/2026-10-14-E-027-certificates.md` + STATE line 223
  (104/104 CaDiCaL UNSAT, drat-trim VERIFIED, cake_lpr VERIFIED; lift CNFs for A R ≤ 32, B R ≤ 24, C R ≤ 14,16;
  Fig. 12 R = 1 control 4224/4224 SAT). **Status: experimenter-reported; no auditor report on E-027 was available
  to the writer at revision h** — the lead decided to use the wording. Limitation sentence (d_ext = 11 and the
  4224-list completeness have no checkable certificate) added in SM S4 and S11. Not written: "every
  computer-assisted step is certified".


**Revision g3 (2026-10-14, audit `research/audits/2026-10-14-revg-proofs.md`).** S5 and S7 CONFIRMED; wording fixes
applied verbatim (S5 opening and (c); S7 first-round detector reason b − a ≤ 21 < G; main-text insertion range
4 ≤ x ≤ 18R; 2D − 3 noted as sufficient, 2D − 2 kept). Frame-model sentence in "Cost and optimality" made
conditional; model-liftable defined with pairing in S9. **C16 changed (audit item 3b):** the Table S3 certificates
use all 4224 logicals; a re-run with only the 360/basis ten-data + one-length-2-residual logicals gave UNSAT for
20 instances (sym24 common frame P = 38; sym24 pipelined P = 8..12, both encodings; nine P = 9 subgroups) ⇒ those
rows carry † ("proven"); P = 9 ⟨(4,2)⟩ (order 3), the three P = 10 subgroups and no-symmetry common frame P ≤ 16 are
pending ⇒ "obstructed within the frame model". Corollary 1's retiming sentence restricted to the † families.


**Revision g2 (2026-10-14, reference audit `research/literature/2026-10-14-reference-audit.md`).** C2 is used again
(intro): "this end-cycle code is not equivalent to the gross code under qubit permutations and local Cliffords, since
its minimum stabiliser weight is 9 rather than 6" — our result, E-017 audit §4.2 (exactly 9 vs 6), not attributed to
Wills. Wills 2605.21898 App. C is cited only for "believed to have circuit distance 12" (circuit not given;
"presumably" the Shaw–Terhal one). The interleaved lower bound is attributed to SBB (Theorem 1, Eq. (12));
Nguyen 2608.19917 only proposed using it to screen schedules. "Check-dependent CNOT orders, by check type
[Tomita–Svore] or by colour class [Kishony–Fowler, SBB]". Non-interleaved defined in SBB's sense (Sec. II A).
Shaw–Terhal 2604.09797 cited once in SM S7 as the time-reversal single-round reduction (relevance from
`2026-10-10-gross-d12-novelty.md` and the reference audit; its full text was not re-read). Open from the reference
audit: Webster 2026 "smallest BB circuit exact" was UNVERIFIABLE this time (old note supports it) — re-check
Sec. 5.5.3 / Table 28 before submission.


**Revision g (2026-10-14, external review).** No numbers changed. C45 (minimum periods) is now worded as a
model statement: UNSAT of the bulk Pauli-frame model means every schedule of the family has a *model-liftable*
weight-11 logical; the needed direction (model lift ⇒ genuine undetected error for sufficiently many rounds) is
proven (E-018 audit C1, Helly argument, 75 injections) only for logicals of ten data errors + one length-2
residual; for logicals with several residual columns it is confirmed on 991/991 sampled cases (E-024b audit §2.3)
but not proven ⇒ "strong evidence, not a theorem". The Fig. 12 retiming obstructions (C16) use only single
length-2-residual logicals, so their direction is the proven one. C10 / Corollary 1 is now phrased as SBB Prop. 3 +
Cor. 1 + our d_ext = 11. Lemma 1's single-fault image property (SBB Table I) is proved case by case in SM S5 for
our template (writer's proof; check by auditor recommended). S7 now derives R' = 32 term by term from
`results/E-024a-gross12-period/anyr2_cs_P18_H24.json` (lo = 4, c_hi = −18, span 510). Placeholders:
"[LER comparison — pending E-026]" (Discussion), "[certificate wording — pending E-027]" (Lemma 2, SM S11).


**Revision e (2026-10-12, restructure to one result).** Tags render as nothing in the PDF (`\showclaimtagsfalse`)
but stay in the source. Tags used in revision e: C10, C11, C13–C18, C31–C36, C38–C47 (SM sections carry hidden tags
too: S2 C31/C41/C43, S3 C32/C42, S4 C11/C13, S5 C33, S6 C34/C42, S7 C35/C43, S8 C36/C42, S9 C10/C13–C18,
S10 C38/C39/C45–C47). **Not used in this paper** (moved to a separate paper; rows kept below for it): C1–C9 (morphing),
C12 (old novelty wording), C19–C30 (other BB codes, novelty notes), C37 (old P=21 cost; replaced by C44), C48 (cross-code
LER; replaced by one generic sentence with no numbers). Circuit names in the PDF: A = cs_P18_H24 (Table I),
B = p18w (Table S1), C = cand_p21 (Table S2). Writer additions in revision e that are not claims: the definition of
"non-interleaved" in the intro paraphrases SBB Cor. 1's hypothesis; "Since every CNOT order gives d_ext ≤ 11 … (their
Prop. 4)" paraphrases SBB; author names for 2308.07915, 2506.03094, 2108.10457 (Quantum 5, 605 (2021)) and 2103.02202 (Quantum 5, 497 (2021))
were checked on their arXiv abstract pages on 2026-10-12 (revision e2).


Every tag `[Cn]` in the draft maps to: the confirmed item in `research/STATE.md` ("已确认结果", item number),
the audit report and section that confirms it, and the raw-results path(s). `results/` is not in git;
paths are relative to the repository root. "Scope" repeats the wording limits that the draft must respect.

Tables of the draft (revision d): Table I (main, `tab:p18`, the period-18 gross circuit) maps to C41, C42 — the only
table in the main text. Figures: Fig. 1 (`fig:timing`) C41, C42, C44; Fig. 2 (`fig:lift`) C13, C14, C15, C34, C38, C39, C42; Fig. 3 (`fig:morph`) C5–C9. In the SM, `tab:morph` (80 morphing circuits, moved from the main text; main text refers to it
and to the planned Fig. 3) maps to C5–C9, `tab:gross` (bulk obstruction status for
the Fig. 12 orders) maps to C16, C17, and `tab:bbthm` (all proven distances; the former main Table I plus the new gross
row) maps to C31, C10, C1, C5, C19, C21, C22 (x4). Tables are referenced by `\ref`, so their S-numbers follow the SM order.

| tag | claim in draft (short) | STATE item | audit (file § section) | results path(s) | scope / wording constraint |
|---|---|---|---|---|---|
| C1 | Shaw–Terhal morphing circuit, [[288,12,18]] mother code, f_x, repo layer order, end-cycle [[144,12,12]]: d_circ = 12 for every number of rounds, both bases, noisy or ideal boundaries; single-round instance 144 rows × 864 cols, 72-translation symmetry, 12 orbits; W=11 DFS 0 solutions on two equivalent instances (2.8e10 / 2.0e11 nodes per basis); weight-12 witness injected | 6 | `research/audits/2026-10-08-E-017.md` §1, §2, §4.1, §4.2, §8 (verdict table) | `results/E-017-gross-morphing-scoping/dfs/`, `results/E-017-gross-morphing-scoping/witness_endcycle.json`, `results/E-017-audit/` (c2_*, c3_*, dfs/, c8_*, c10_*.json) | SD6, independent single-operation faults. Only this specific circuit (f_x, repo order). Never "gross code proven 12". Circuit has no dedicated ancillas (STATE wording "单辅助比特" refers to bare single-qubit measurement; draft says "without dedicated ancillas") |
| C2 | End-cycle code min stabiliser weight exactly 9 (gross: 6) ⇒ not equivalent to gross code under qubit permutations / local Cliffords; end-cycle distance exactly 12 | 6 | `2026-10-08-E-017.md` §4.2 | `results/E-017-audit/` (c8_endcycle outputs, stabw_*), `results/E-017-gross-morphing-scoping/endcycle.json` | Says nothing about other equivalence notions. IBM 2605.21898 App. C circuit identity NOT confirmed (draft says so) |
| C3 | Prop. 1 (2604.09797) fold premise verified computationally in the basis-free form (general + local), r = 2..T, T = 2..5, both bases, incl. noisy final round; per-fault wording of the paper is basis-dependent; arbitrary T = machine-checked hypotheses + written argument | 6 | `2026-10-08-E-017.md` §3, §7 issue 2 | `results/E-017-audit/c3_*.json` | Must use auditor's formulation, not "time-reversal symmetry holds". Draft SM S4 gives the formulation |
| C4 | Novelty: to our knowledge first rigorous d_circ lower bound for any morphing circuit | 6 (novelty clause) | — (lit note, not audit) `research/literature/morphing-d12-novelty.md` §问题 2, §新颖性判断 | — | "to our knowledge"; search date 2026-10-08; restricted to the specific circuit |
| C5 | 80 two-round morphing circuits (10 (code, hom) × Table IV/VIII × 2×2 term orders), reconstructed from 2407.16336 Tables IV/VIII/IX, gate-identical 80/80 to independent implementation; exact d_circ both bases: 72 = d̃, 8 < d̃; small-mother circuits 112/112 instances agree on full T=4 | 8 | `research/audits/2026-10-08-E-019.md` §1, §2.1, §2.3, §6 | `results/E-019-morphing-family/summary.{md,json}`, `results/E-019-morphing-family/solve_*_T4.json`, `results/E-019-audit/jobs2.out`, `results/E-019-audit/t0_build.json` | Cite Table IX as source of Table VIII permutations. Three-round Z_3 morphing and App. C non-Abelian codes not covered |
| C6 | [[108,8,10]] f_y → [[54,8,8]]: Table IV four legal term orders give 6,6,7,7; b3 = x² (round 1) → 6, b3 = x (incl. public repo order) → 7. Table IX caption of 2407.16336 says the A/B element ordering is "not important" for Table IV schedules because the end-cycle codes are invariant under a2↔a3, b2↔b3; the end-cycle codes are invariant but the circuit distance is not. Table IX lists only (ℓ,m) = (6,6), (12,6), so [[54,8,8]] is not an entry of it; Table I's ≤7 equals repo-order exact value | 8 | `2026-10-08-E-019.md` §1 (last bullet), §2.1, §6 row 2, §7 issue 2; caption wording: `research/literature/2026-10-09-paper-novelty.md` §(a) | `results/E-019-morphing-family/solve_bb108_y_{paper,std01,std10,repo}_{X,Z}_T4.json`, `results/E-019-audit/jobs2.out` | Do NOT write "the paper's Table II circuit is 6". No "contradicting/refuting" phrasing: say the code-level invariance "does not extend to the circuit distance" |
| C7 | [[144,12,12]] f_x sw01/sw10 → [[72,12,8]]: d_circ = 6; Table IX already gives ≤6 ⇒ our contribution is tightness. [[72,12,7]] (f_y sw01/sw10) = 7, tight | 8 | `2026-10-08-E-019.md` §1, §2.1, §6 rows 3–4 | `results/E-019-morphing-family/solve_bb144_x_sw{01,10}_*_T4.json`, `solve_bb144_y_sw{01,10}_*_T4.json` | Not a "new discovery" of [[72,12,8]] |
| C8 | Sub-d̃ witnesses: CNOT faults only, single interior half-cycle, no-idle model, all 8 circuits × 2 bases (16/16 injected into full-detector circuits); values identical over 96 noise/time-window settings | 8 | `2026-10-08-E-019.md` §2.2, §3, §6 row 6 | `results/E-019-audit/jobs1.out`, `results/E-019-audit/t6_log.jsonl` | Mechanism must NOT be written as "from reset errors" |
| C9 | All 24 [[288,12,18]]-derived circuits preserve d̃ (12 or 10): proven by experimenter pipeline; 3 independently reproduced (f_x sw11 d̃=10 incl. full T=3; f_y paper and f_xy sw11 d̃=12); arbitrary T relies on experimenter's per-circuit fold computation (code + flags audited, 160/160 flags true) | 8 | `2026-10-08-E-019.md` §4, §5, §6 row 7 | `results/E-019-morphing-family/solve_bb288_*_T4.json`, `results/E-019-audit/dfs/`, `results/E-019-audit/t10_ub288.jsonl` | Wording: "24 proven, 3 independently reproduced" |
| C10 | Strikis–Browne–Beverland (2603.05481) gross Fig. 12 circuit: d_circ = 11, any R, both bases | 3 | `research/audits/2026-10-05-E-014-E-015.md` §A1–A6, "A verdict", final verdict table row E-014 | `results/E-014-gross-dcirc11-proof/out_*.txt`, `inst_{X,Z}.txt`; `results/E-014-E-015-audit/a5_lat/`, `a8_sub8`, `a10_gross_witness.json`, `a7_table1_gross.json` | Independent single-operation faults; evaluator memory experiment |
| C11 | Extended code 360 merged cols/side (144/144/72 by He-weight), 24-element order-preserving translation group (a+b≡0 mod 3), 15 orbits; W=10 DFS 0 solutions (~2e10 nodes/side), reproduced on lattice-coordinate instance and with order-8 subgroup (45 orbits, ~5e10 nodes/side); no-symmetry run not done | 3 | `2026-10-05-E-014-E-015.md` §A1, §A2, §A5 | as C10 | — |
| C12 | Novelty: first rigorous d_circ lower bound for any gross-code syndrome circuit; optimal among non-interleaved (via Strikis Prop. 4) | 3 (novelty clause) | lit note `research/literature/novelty-gross11-ibm72.md` §1, §4 table row 1 | — | Must NOT say "best gross circuit" (morphing / IBM 2605.21898 believed 12) |
| C13 | Each side exactly 4224 weight-11 extended logicals (176 free orbits of 24); 360 are "10 data + r2"; exact augmented-observable lift checker complete and sound; Fig. 12 lifts 4224/4224 (auditor R=1..3; experimenter R=1..6) | 7 | `research/audits/2026-10-08-E-018.md` §A, §B, §C1 | `results/E-018-gross-interleaved-12/w11_all_{X,Z}.pkl`, `stage_a_summary.json`, `lift_fig12.json`; `results/E-018-audit/a2_collect.json`, `a9_fig12.json`, `a1_basics.json` | — |
| C14 | Benchmark family (gross-dcirc task, period ≤ 8): keeping Fig. 12 per-check orders forces P = 8, one start per check; exactly 32 conflict-free assignments = 4 mod global translation (non-SAT backtracking + two SAT encodings); all colour-uniform, deterministic, non-interleaved, incl. Fig. 12; independent of lattice isomorphism choice | 9 | `research/audits/2026-10-09-E-020.md` §1 | `results/E-020-gross-perchk-pipeline/p8_legal.json`, `P8_plegal.log`, `results/E-020-audit/p8search_fix0.txt`, `p8search_nofix.txt`, `p8_inst.txt` | Draft describes the family by its rules (not as "the evaluator") — PI may want the benchmark named |
| C15 | Those 4 circuits: injection-verified weight-11 undetected logicals for R = 1..6, both bases (72/72) ⇒ in that task (R=3) no retiming of Fig. 12 exceeds 11; exact, includes boundaries, frame-model-free | 9 | `2026-10-09-E-020.md` §2 | `results/E-020-audit/b2_inject_1_3_6.json`, `b2_inject_2_4_5.json`; experimenter lift runs in `results/E-020-gross-perchk-pipeline/` | Not for changed CNOT orders; not for R ≥ 7 (finite-R statement) |
| C16 | Bulk obstructions (every legal deterministic circuit keeping Fig. 12 orders has a bulk "10 data + 1 hook" weight-11 undetected error ⇒ d_circ ≤ 11 for sufficiently many rounds): symmetric non-wrapping frame any P (P=38 compression); symmetric pipelined P = 8, 9, 10 (two CP-SAT encodings + exhaustive P=8,9); P = 11 (CP-SAT + CEGAR); P = 12 single encoding; P=9 subgroups |H| = 12 (3), 8, 6 (3), 4 (<(0,3),(6,0)>, <(3,3)>), 3; P=10 subgroups |H| = 12 <(1,2)>, 8, 6 <(2,4)>; per-check-free non-wrapping frame P ≤ 16 (experimenter-only encoding; auditor reproduced, independent encoding UNKNOWN) | 7 and 9 | `2026-10-08-E-018.md` §C1, §C3, §C5, §D; `2026-10-09-E-020.md` §3 | `results/E-018-audit/a5_*.json`, `a3_enum_P8_Z.json`, `a3_enum_P9_Z.json`; `results/E-018-gross-interleaved-12/design*`; `results/E-020-gross-perchk-pipeline/cegar_*.json`; `results/E-020-audit/c1_a5_sym_P11_n15.json`, `c1_a5_sym_P12_n15.json`, `cegar_*.json` | Bulk (large R) only; NOT applicable to R=3 task except via C15. Never unscoped "unreachable". P=12 must say "single encoding" |
| C17 | Open cases: per-check-free and |H|=2 pipelined P ≥ 9; |H|=4 <(3,0)> at P=9 (UNKNOWN); unlisted P=10 subgroups; symmetric pipelined P ≥ 13; per-check-free non-wrapping P > 16; changed CNOT orders. Classical control: ~1.1e5 random-walk evaluations + 2000 SAT-enumerated P=9 per-check circuits, all 720 single-hook logicals liftable (evidence only) | 7 and 9 ("未覆盖/未决定") | `2026-10-08-E-018.md` §D "不能写"; `2026-10-09-E-020.md` §3 "不能写" | `results/E-020-gross-perchk-pipeline/control_P9.json`, enumstats output | Draft lists *more* open cases than STATE (unlisted P=10 subgroups, symmetric P ≥ 13) — this is a strengthening of honesty, not of claims |
| C18 | Frame model agrees with exact DP in the bulk on tested circuits, but not at the initial time boundary (P=16 counterexample: 96 model-blocked logicals lift via round-0 detectors) | 7 ("被推翻的辅助说法") | `2026-10-08-E-018.md` §C2 | `results/E-018-audit/a5_sym_P16_n1.json` (+ a6_bulk output) | Must not write "frame model and exact DP agree in general"; must not use the "2-orbit minimal core" mechanism (refuted, §C4) — draft does not mention it |
| C19 | [[108,8,10]] y-parity two-colour depth-8 single-ancilla circuit: d_circ = 10 (IBM ≤ 8); explicit term orders (X even [0,1,2,5,3,4], odd [2,1,0,5,3,4]; Z even [3,4,5,2,1,0], odd [3,4,5,0,1,2]); d_ext = 10 both sides (270 cols, 10 orbits of 27, W=9 0 solutions with and without symmetry) | 2 | `research/audits/2026-10-05-E-013.md` Stage 1 (F1 term orders), Stage 3, 3b, 3c, Verdict | `results/E-013-audit/dfs_W9.txt`, `dfs_W9_nosym.txt`, `dfs_W10.txt`, `s7_table1_R3.json`, `s3_screen.txt`; `results/E-005-noninterleaved-bound/e013_assembled_x2_14_z12_0.json` | Use the corrected (F1) term orders; non-interleaving true but not load-bearing for the lower bound |
| C20 | Novelty: first d_circ = 10 circuit for [[108,8,10]]; first circuit distance for a BB code (ℓ,m ≥ 2) with d ≥ 10 that comes with a stated, reproducible proof; 2604.19481 lists d_circ = 9, method unstated, for a [[54,2,10]] GB code; not first for qLDPC (HGP 2308.15520, layer codes 2609.39522, certificates 2609.37231); method builds on 1404.3747, 2603.28852, 2603.05481 | 2 (novelty clause) | lit notes `research/literature/novelty-bb108-dcirc10.md` §结论, §3; `research/literature/2026-10-09-paper-novelty.md` 问题 2, 建议的改写 2 | — | "to our knowledge"; must credit Strikis LRC framework; "BB" means ℓ,m ≥ 2 (GB codes excluded explicitly) |
| C21 | IBM [[72,12,6]] (2308.07915) circuit: d_ext = 5; exact lift shows no weight-5 undetected error R = 1..10 (auditor; experimenter R=1..8); arbitrary R via split/translation argument ⇒ d_circ = 6 both bases; partial precedent 2603.22532 (Z basis, R=6, CZ/SI1000 exact 6 in public data); qldpc-challenge PR #724 upper bound 6/6 | 4 | `2026-10-05-E-014-E-015.md` §B7, verdict rows e, e' | `results/E-015-bb-generalization/ibm_lift_bb72_w5*.json`, `ibm_lift_bb72_R5-8.log`; `results/E-014-E-015-audit/` (b_ibm, b7_periodic outputs) | Arbitrary-R step (3) is a written argument with machine-checked hypotheses. Must state the 2603.22532 precedent |
| C22 | LRC theorems: [[72,12,6]] two-colour (X 4/34, Z 30/0) = 6; coprime [[126,12,10]] uniform block 14 = 9; (20,3) [[120,8,12]] uniform = 10; (31,2) [[124,10,10]] uniform = 9; all 864 proper two-colour BB72 states d_ext = 6 | 5 | `2026-10-05-E-014-E-015.md` §B6, verdict rows a–d | `results/E-015-bb-generalization/assembled_*.json`, `exact_bb72_T6.json`; `results/E-014-E-015-audit/b6/`, `b6_*`, `b10_bb72_states.json` | Equivalence of project (20,3) [[120,8,12]] to literature [[120,8,12]] (2601.09911) UNVERIFIED — draft says so |
| C23 | Negatives: every two-colour LRC on gross (all three index-2 colourings) ≤ 10; every two-/three-class mod-3 LRC on [[90,8,10]] ≤ 8 | 5 | `2026-10-05-E-014-E-015.md` §B8, verdict rows f, g | `results/E-014-E-015-audit/b8_gross_X_{01,10,11}.json`, `b9_full_*.log` | Template is non-interleaved, so d_circ ≤ via Cor. 1 |
| C24 | Partitionable non-interleaved: [[90,8,10]] ≤ 9 (10 impossible), [[108,8,10]] ≤ 10; uniform: BB90 ≤ 8 any depth, BB108 depth-8 ≤ 9; IBM-type pipelined circuits not covered | 1 | `research/audits/2026-10-03-E-005.md` §0 (C1, C2, C4, C5), §1.2, §1.3 | `results/E-005-noninterleaved-bound/single_*.json`, `results/E-005-audit/single_bb90_X.json`, `uniform_*`, `t2_partition.json` | "non-interleaved" must mean partitionable |
| C25 | Novelty (rewritten 2026-10-10): apart from [[72,12,6]], the first circuit distances for BB codes with d ≥ 10 that come with a stated, reproducible proof; 2604.19481 reports d_circ = 9 for [[70,6,9]] BB, [[102,22,9]] GB and [[54,2,10]] GB without describing the method (not stated anywhere in v1, the only version); 2603.22532 completed only the smallest BB circuit with exact solvers | 5 (novelty clause) | lit notes `research/literature/novelty-gross11-ibm72.md` §4; `research/literature/2026-10-09-paper-novelty.md` 结论 3, 问题 2, 建议的改写 1, 3 | — | Old wording "first rigorous … d ≥ 9" withdrawn. Not "first BB proof" (2603.22532 has d=6). Whether to ask IonQ about their method is a PI decision |
| C26 | (unused; the BB72 864-state statement is folded into C22) | — | — | — | — |
| C27 | Prop. 3 key step (each fault image = 0 or one extended column) checked computationally on BB108 (R=3), gross Fig. 12 (R=1..3), IBM BB72 (R=1..10), the four LRC theorems | 2, 3, 4, 5 | `2026-10-05-E-013.md` Stage 3b item 3; `2026-10-05-E-014-E-015.md` §A6, §B7, §B6 (Table I column) | `results/E-013-audit/s7_table1_R3.json`; `results/E-014-E-015-audit/a7_table1_gross.json` | — |
| C28 | Morphing upper-bound witnesses use idle components after a reset layer (or initial reset flips); lower bounds hold for any SD6 sub-model | 6 (scope) | `2026-10-08-E-017.md` §6 | as C1 | — |
| C29 | 2608.19917 v2 (Nguyen, Rimbach-Russ, Bosco) proposes combining the Strikis non-interleaved lower bound with the Shaw–Terhal single-round time-reversal reduction, as future work, no numbers | — (literature) | `research/literature/2026-10-09-paper-novelty.md` §(b), 建议的改写 6 | — | Method-idea precedent only; does not affect C4 result novelty |
| C30 | Dedicated search (2026-10-09): no prior exact d_circ for any morphing circuit, no prior evaluation of the 80-circuit family beyond 2407.16336's BP-OSD upper bounds, no prior result on retimings of Fig. 12 (interleaved 12 open per 2603.05481) | — (literature) | `research/literature/2026-10-09-paper-novelty.md` §(a), (b), (c), 新颖性判断 | — | Evidence strength: (a) medium-high, (b) medium-high, (c) medium |


### New tags for the gross d_circ = 12 headline (STATE item 10, E-021; audit `research/audits/2026-10-10-E-021.md`)

Results paths: experimenter `results/E-021-gross-new-orders/`, auditor `results/E-021-audit/` (cand1 at top level,
`cand_p21/`, `cand1c/` subdirectories). Specs in git: `search/experiments/e021/{cand_p21,cand1,cand1c}_spec.json`.
Circuit names: cand_p21 = period 21 (the circuit of Table I), cand1 = period 38, cand1c = period 26 (DAG compression of cand1).

| tag | claim in draft (short) | STATE item | audit (file § section) | results path(s) | scope / wording constraint |
|---|---|---|---|---|---|
| C31 | Single-ancilla, CNOT-based, interleaved syndrome circuit for the gross code itself (matrices element-wise equal to the benchmark's; colour-symmetric; all ancillas reset at step 0 / measured at step 20; period 21): d_circ = 12 in both memory bases, every R, SD6. Legality, determinism (64 noiseless shots, DEM for R=1,2,3,6), L0; interleaving: 48 data qubits switch 4× (cyclic X/Z sequence over one period) | 10 | `2026-10-10-E-021.md` §1, F1 (cand_p21), F2 (cand1c); verdict table | `results/E-021-audit/cand_p21/b1_legal.json`, `results/E-021-audit/b1_legal.json` | Always "distance 12", never "better circuit"; no LER claim; SD6 + CNOT template only; "for the gross code itself"; not an evaluator gross-dcirc score (max_period 8). The draft states only "48 data qubits switch four times" for cand_p21 (audit F1); the audit's "96 × 2" split is for cand1 (§1) |
| C32 | Extended code depends only on {q1,q2}, {q1,q2,q3}, {q5,q6} per check ⇒ reversal, s12, s56 (8-element class) preserve it; key sets equal to Fig. 12 (360 cols/side) for all three circuits. cand_p21 uses only in-pair swaps: X1 class (24 checks) identical to Fig. 12, other 120 checks s12 or s12·s56. Table I orders/times; Fig. 12 orders in SM | 10 | `2026-10-10-E-021.md` §2, F1 ("24 个校验与 Fig. 12 顺序相同，120 个是 … 其他变体") | `results/E-021-audit/b2_ext.json`, `results/E-021-audit/cand_p21/b2_ext.json`; Table I extracted by `paper/scripts/extract_class_orders.py` from `search/experiments/e021/cand_p21_spec.json` and `results/E-021-gross-new-orders/fig12_spec.json` | **Writer's extraction**: the per-class orders/times in Table I and the "only in-pair swaps" observation (transformation column) were read by the writer's script from the spec files (the script asserts support equality and class uniformity); consistent with the audit's 24/120 count but the transformation column itself is not in the audit. Re-run the script before submission |
| C33 | Lift reduction uses the template identity (augmented H_i observable = sum of all detectors of check i) + SBB Table I; NOT Prop. 3; insensitive to interleaving; checked on the DEM (telescoping_bad = 0, bad_obs = 0, image set = 360 columns) for every R used up to 20, both bases; fewer detectors (no X-check detectors in a Z memory) only strengthen the lower bound | 10 ("归约依据是‘模板恒等式 + Table I’（不是 Prop. 3）") | `2026-10-10-E-021.md` §3; issue 2 | `results/E-021-audit/b2_ext.json`, b3 runs (assertions) | Must not cite Prop. 3 as the basis for the gross-12 lower bound |
| C34 | Exact lift: 0/4224 per basis; cand_p21 R = 1..14, 16 (CP-SAT) and R = 1..3 (MITM); cand1 R = 1..14, 16, 20 (CP-SAT) + R ≤ 3 (MITM); cand1c R = 1..14; positive control Fig. 12 4224/4224 (Z R=1; X R=1,2; both methods); experimenter's own lift R = 1..6 agrees | 10 | `2026-10-10-E-021.md` §4a, F1, F2 | `results/E-021-audit/b3_cand_{X,Z}_*.json`, `b4_cand_*_R{1,2,3}.json`, `b3_fig12_*`, `b4_fig12_*`; `results/E-021-audit/cand_p21/b3_cand_*`, `b4_cand_*`; experimenter `results/E-021-gross-new-orders/lift_p21_R1-14.json`, `lift_cand1_R1-6.json`, `lift_cand1_R7-14.json`, `lift_cand1c.json` | Depends on C11 (d_ext = 11, E-014) and C13 (complete 4224 list, E-018) |
| C35 | Any R: round separation + layer periodicity (machine-checked) + split lemma + translation to R' ≤ 13 (auditor) / deletion to R' ≤ 14 (experimenter, checked by auditor) | 10 ("‘不跨空轮 + 时间平移’推到任意 R") | `2026-10-10-E-021.md` §6, F1, F3 | `results/E-021-audit/b7_periodic.json`, `results/E-021-audit/cand_p21/b7_periodic.json`; `results/E-021-gross-new-orders/anyR_p21.log`, `anyR_premises.log` | Written argument with machine-checked premises; state both parts |
| C36 | Upper bound: weight-12 data logical injected after data reset, R = 1,3,6,10, both bases, 0 detectors + observable flip, removing one qubit ⇒ detected. Heuristic upper_bound best = 12 (cand1 R = 1,2,3,7,10; cand_p21 R = 1,3,7; both bases) | 10 | `2026-10-10-E-021.md` §5, §4c, F1 | `results/E-021-audit/b6_inject.json`, `b8_ub.jsonl`; `results/E-021-audit/cand_p21/b6_inject.json`, `b8_ub.jsonl` | Heuristic is evidence only |
| C37 | Cost/scope: period 21 (cand_p21), 38 (cand1), 26 (cand1c) vs 8 for IBM / Fig. 12 (~2.6×); same qubit count (one ancilla per check); SD6 + CNOT template only; direct DEM solve without lift: MaxSAT 7200 s timeout, CP-SAT 3600 s UNKNOWN (R=1, Z) ⇒ not part of proof; d_ext = 11 not re-run without symmetry | 10 ("限定") | `2026-10-10-E-021.md` §4b, "写作可用的表述" 限定; lit note §1 | `results/E-021-audit/b5_Z_R1_maxsat_None.json`, `b5_Z_R1_cpsat_12.json` | "distance 12" only; LER not evaluated; depth-8 open; "2.6×" is 21/8 (writer arithmetic) |
| C38 | Period-8 colour-symmetric circuits in the Fig. 12 class: exactly 944 legal deterministic (two independent enumerations, hash-identical); all 944 have a weight-11 undetected logical at R = 1, Z basis (witnesses rechecked) | 10 ("同扩展码类颜色对称 P=8 的 944 个电路全部有权重 11") | `2026-10-10-E-021.md` F4 | `results/E-021-audit/b9_p8.json`, `b9_p8.log`; experimenter `results/E-021-gross-new-orders/p8class_H24*.json`, `p8screen_{0,1}.jsonl` | Colour-symmetric only; per-check-free P = 8 NOT excluded; finite R (R = 1) |
| C39 | Classical control: same family; SAT sampler without logical clauses: 2277 legal deterministic in 9 min, none with 0 modelled liftable (min 25/184), random 10% (233) exact-lifted → 0 certified. Reasoned search: model candidate in 4.1 s (98 lazy rounds) → cand1; 300 model candidates in 40 s; 40 shortest after compression, 39 lifted R = 1..6, 39/39 certified (2 of period 21); uniform-random rejection sampler 6×10⁷ samples → 41 deterministic, min 68/184 modelled liftable. With Fig. 12 orders pinned the model is UNSAT | 10 (only "随机合法电路抽 233 个，0 个认证") | — (not audited; the auditor re-ran only cand1, cand1c, cand_p21) | `results/E-021-gross-new-orders/randsat_summary.json`, `randctl_summary_shuffle.json`, `enumscreen.jsonl`, `nwenum.jsonl`, `nwfull_H24_12_03*.json`, `ctl_fig12_H24.json`; journal `research/journal/2026-10-10-E-021-gross-new-orders.md` §跟进 (3), (2d) | **Revision c (lead decision)**: main text uses only the audited control — "0 of 233 random legal circuits in the same class certify, whereas the constraint-guided search produced the certified circuits". The 39/39 count, 4 s / 40 s timings and the 6×10⁷-sample control appear only in SM `sm:p21`, explicitly labelled as unaudited experiment-log observations not used in the main text |
| C40 | Novelty + open question: SBB 2603.05481 v2 Sec. IV.3 verbatim "whether any interleaved circuit can achieve circuit distance 12"; no depth condition, no impossibility conjecture; App. H.2 "non-staggered, interleaved variants" (= depth-8 question, left open); no previous gross-code-itself circuit with d_circ = 12, numeric or rigorous, single or multi-ancilla; evidence medium-high; scoop risk medium | 10 (novelty clause) | — lit note `research/literature/2026-10-10-gross-d12-novelty.md` §1, §2, 新颖性判断, 推荐措辞 | — | "answers in the affirmative" must come with: no depth condition in the question + depth 8 open. Not "first BB circuit reaching code distance" (2603.22532 [[72]]). Distinguish morphing 12 (different code, no dedicated ancillas) |

### Revision d tags (STATE items 12, 13; audits `research/audits/2026-10-11-E-024b.md`, `research/audits/2026-10-11-E-023.md`)

Results: auditor `results/E-024b-audit/` (subdirs per TAG, e.g. `cs_P18/`, `p18w/`), experimenter
`results/E-024a-gross12-period/`, `results/E-024b-gross12-other-classes/`; specs in git
`search/experiments/e024a/cs_P18_H24.json`, `search/experiments/e024b/p18w_spec.json`.
C31–C37 (period 21) remain valid and are now used for the secondary circuit only.

| tag | claim in draft (short) | STATE item | audit (file § section) | results path(s) | scope / wording constraint |
|---|---|---|---|---|---|
| C41 | cs_P18_H24: single-ancilla, CNOT-based, pipelined (resets {2,15,16,17}, measurements {0,14,15,16}), interleaved (96 data qubits × 4 switches, 48 × 2), colour-symmetric circuit for the gross code itself (matrices element-wise equal to the benchmark's), legal, deterministic, L0: d_circ = 12, every R, both bases, SD6 | 13 | `2026-10-11-E-024b.md` §A-a (b1, b2, b3, b6), "写作可用的表述" | `results/E-024b-audit/cs_P18/` (b1_legal, b2_ext, b3_cand_*, b6_inject) | "distance 12" only; SD6 + CNOT template; not an evaluator score |
| C42 | Table I (orders/steps, ⟨rev,s12,s56⟩ map; all 144 checks change); extended code = Fig. 12 (360 cols/side); Table I property + template identity checked for each R; exact lift 0/4224 R = 1..32 both bases (64 runs; experimenter to R = 36); Fig. 12 positive control 4224/4224; weight-12 injection R = 1,3,6,10 | 13 | `2026-10-11-E-024b.md` §A-a; §1.2 (positive control) | as C41; experimenter `results/E-024a-gross12-period/` certify outputs | **Table I is the writer's extraction** (`paper/scripts/extract_class_orders.py cs_P18_H24.json fig12_spec.json`, asserts support, class uniformity, class membership); matches audit "144/144 反转 + 对内互换". Fig. 1 caption facts supplied by lead, asserted against the audit |
| C43 | Any R: cs_P18 gap argument (settling D = 18; split if fault-free gap ≥ G = 52 = 2D + 17 − 1; boundary condition D + S + 17, S = 5; span ≤ 510 layers; layer-periodic insertion for x ∈ [4, 18R]; deletion ⇒ R' ≤ 32), no extra premise, checked line by line by the auditor. p18w: slab argument needs premise (A) (machine-checked, 0 violations, R = 3, 8, 24), R' ≤ 23, lift R ≤ 24; second circuit legal, pipelined, 24 checks = Fig. 12 order | 13 | `2026-10-11-E-024b.md` §1.1–1.4, §A-a, "发现的问题" 1–2 | `results/E-024b-audit/p18w/`, `s1_slab*`, `s2_period*` outputs | Must not cite `anyR_wrap.py` alone; cite premise (A) and the layer-by-layer insertion check. "17" read as the longest reset-to-measure span (dm_max in the audit) — writer's interpretation of the audit's symbol |
| C44 | Cost: period 18 vs 8 (2.25×); same qubit count | 13 (+10 限定) | `2026-10-11-E-024b.md` "写作可用的表述" (last bullet) | — | 2.25 = 18/8 (writer arithmetic); no LER claim for the gross circuits |
| C45 | Minimum period in colour-symmetric families (Fig. 12 class, (a+b) mod 3): pipelined P = 8..17 and non-wrapping P = 20 UNSAT in the bulk frame model ⇒ minima 18 / 21; two encodings for pipelined (gsat, TimeSAT); final CNFs re-solved by independent solvers (3 for P = 20 nw and P = 12, 2 for P = 17); encoding completeness (P = 8: 944 = independent set; 75/75 sampled circuits accepted); clause soundness 991/991 + 99/99 vs exact DEM; X0/Z2 window ≤ 14 UNSAT at P = 24 (explanation only) | 13 | `2026-10-11-E-024b.md` §2, §A-b, 补记 | `results/E-024b-audit/` (t0_enc, t1_nogood, r1_gsat, r2_cnf, r3_cegar024a outputs) | Bulk (sufficiently many rounds), not finite R; only within this family; window ≥ 15 is not a proof of P ≥ 18 |
| C46 | Uniqueness: among the 24 translation-coset colourings of index 2, 3, 4, 6, 8, 9 (3, 4, 3, 12, 1, 1 subgroups), one order type per colour, the only extended-code class with d_ext ≥ 11 on both sides is Fig. 12's (up to translation); witnesses re-verified; 48/48 UNSAT replay; 45 bad-triple types with verified weight-10 witnesses | 13 | `2026-10-11-E-024b.md` §3 | `results/E-024b-audit/` (u1_dext outputs) | Not "unique among all orders": per-check-free and index 12, 18, 24, 36 not done. Draft uses "d_ext ≥ 11 on both sides" / "d_ext = 11" (Fig. 12 has exactly 11, C11) |
| C47 | Reduced symmetry (partial): |H| = 12 ⟨(1,2)⟩ excludes P ≤ 11; every |H| ≥ 2 excludes P = 8; spot-checked (P = 10 ⟨(1,2)⟩; P = 8 ⟨(6,3)⟩, ⟨(0,3)⟩), not fully re-audited; per-check-free and other subgroups at P = 12..17 undecided | 13 ("未决定") | `2026-10-11-E-024b.md` §A-c | `results/E-024b-audit/` (r3_cegar024a P10_s12, P8_s63, P8_s03) | Say "spot-checked"; E-025 (mixed families) unaudited — not cited |
| C48 | LER: d_circ is a guarantee of the circuit; leading-order structural estimates (not rigorous bounds) ~4–5× ([[54,8,8]] morphing 6 vs 7) and ~10× (BB108 IBM ≤ 8 vs ours 10) at p = 1e-4; method cannot determine the ratio at p ≳ 5e-4; ratio grows more slowly than p^-1; practical decoders (BP-OSD, Relay-BP) at 5e-4–1e-3 on [[54]]: at most ~1.2–1.6× (95% upper limits), because decoders fail on similar small fractions of weight 3–5 fault sets; BB108 undetermined; gross circuits not evaluated | 12 | `2026-10-11-E-023.md` 声称 1 可用措辞, 声称 2 可用措辞, (c) | `results/E-023-audit/` (a9, a11, a12 outputs) | Never "MLE lower bound", "p^-1", or any original E-023 [[54]] decoder numbers (dense detector basis, void); no LER claim for gross circuits |

### Revision e2/e3 tag

| tag | claim in draft (short) | STATE item | source | results path(s) | scope / wording constraint |
|---|---|---|---|---|---|
| C49 | Mechanism (Key idea, Fig. 1b): example weight-11 "10 data + 1 hook" logical (data 0, 1, 6, 12, 16, 19, 74, 78, 79, 91; hook {9,25} = residual after the 4th CNOT of X check 7 in Fig. 12), Z memory, R = 1. Fig. 12: hook lands on 25, 9 at ticks 10, 11, after Z15 and Z6 read 9 (ticks 6, 4) ⇒ undetected. Period 18: reversed order ⇒ same column only from an ancilla fault between the 2nd and 3rd CNOT, spread to 8, 91, 82, 85 (deposits 8, 9, 10, 18); Z15 sees 85 at 18 after its read at 15 (late), Z6 sees 82 at 10 before its read at 13 (early); the four final detectors of Z6, Z12, Z15, Z18 form a minimum conflicting set ⇒ odd parity at Z6. Typicality (audited sentence, used verbatim): for all 360 such logicals the lift fails at R = 1; every irreducible conflicting detector set has 4–10 detectors; the smallest has 4, 5 or 9 (exact minimum-cardinality counts 144/168/48) | — (illustration of item 13's certified circuit) | `research/audits/2026-10-12-fig1-mechanism.md` (论断 1 CONFIRMED with wording refinement "between the second and third CNOT"; 论断 2 "4 to 10" CONFIRMED for irreducible sets) | `paper/figures/fig1_concept_data.json`; audit outputs `results/fig1-audit/` | **Do not cite 128/184/41/7** (REFUTED as intrinsic: depends on deletion order). "Exactly two errors per check" holds for the example; only 48/360 logicals are pure 4-check cycles, so "timing turns the potential logical into a parity cycle" is stated for the example only. Lift model = one DEM term per column (as Lemma 2) |

Note on C21 reuse: the main-text sentence "Nor is ours the first BB circuit proven to reach the code distance" uses C21
(IBM [[72,12,6]] = 6 with the 2603.22532 partial precedent).

## Quantities in the draft that are NOT from STATE / audits (writer's additions)

- (revision b) The p^⌈d_circ/2⌉ sentence and the "essentially every reported d_circ is an upper bound" sentence were
  removed from the intro.
- (revision b) "The IBM circuit (8 time steps per round) has d_circ ≤ 10" — `research/literature/2026-10-10-gross-d12-novelty.md` §2 row 2308.07915.
- (revision c) The 2606.30592 (biased-noise) sentence, its SM mention and its bib entry were deleted (lead decision: unverified).
- (revision b) Mechanism sentences in "Construction" / "Why the original orders cannot reach 12" (extended code fixed by three
  sets per check; the bulk certificate is an inconsistency of timing conditions) paraphrase audit §2 and E-018 §C; they are
  explanations, not new claims.
- Abstract/intro (old revision): "logical error rate scales as p^⌈d_circ/2⌉ for a minimum-distance decoder" — textbook statement, no number from literature.
- Intro: "essentially every reported d_circ is an upper bound" — supported by lit notes (`novelty-bb108-dcirc10.md` §3, `novelty-gross11-ibm72.md` §2.2), not an audit item.
- Discussion: "10^10–10^11 search nodes on a workstation" — taken from audit node counts (C1, C11).
- SM S6: SD6 definition follows `evaluators/noise.py` docstring and `research/literature/noise-models.md` (arXiv 2108.10457).

## Bibliography traceability

All arXiv numbers in the draft appear in `research/literature/*.md`. Titles, full author names, versions and journal
references of all 15 entries flagged earlier (incl. the new 2608.19917) were verified on arXiv abstract pages by
lit-scout (`research/literature/2026-10-09-paper-novelty.md` 问题 3, read 2026-10-10) and copied into the draft;
no `[UNVERIFIED]` marker remains in the bibliography. 2408.10001 is now Quantum 10, 2009 (2026).
For 2308.07915, 2506.03094, 2103.02202, 2108.10457 the project notes record surnames and titles only
(`refs-verified.md`, `noise-models.md`); initials are still to be added.
The one remaining `[UNVERIFIED]` in the draft is not bibliographic: equivalence of the project's (20,3) [[120,8,12]]
to the [[120,8,12]] of 2601.09911 (SM "Other BB codes").

Revision b/c (2026-10-10): the entry for arXiv:2606.30592 added in revision b was removed again in revision c
(unverified; lead decision). All must-cite references of that note (2308.07915, 2603.05481, 2506.03094, 2407.16336,
2605.21898, 2604.09797, 2608.19917, 2603.22532) are cited in the revised main text.
