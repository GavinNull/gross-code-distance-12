# paper/ — internal draft (first version 2026-10-09; revision b 2026-10-10)

Files:
- `draft.tex` — PRL-style letter (revtex4-2) + Supplemental Material in the same file. Claim tags `[Cn]`
  (blue superscripts; switch off with `\showclaimtagsfalse`), red `[TODO]` and `[UNVERIFIED]` markers.
- `claims_map.md` — every tag `[Cn]` → STATE confirmed item, audit file + section, results path, wording limits.
  Revision b adds C31–C40 (gross d_circ = 12).
- `figures_plan.md` — three planned figures with their data sources (no figure produced yet).
- `scripts/extract_class_orders.py` — prints per-colour-class CNOT orders/times of a gross schedule spec
  (source of Table I and of Fig. 1).

Scope rule used: only `research/STATE.md` "已确认结果" items 1–10 are claimed, inside the scope stated there and in the
referenced audits. Nothing from "待复核的结论" (E-010 three-colour BB108, E-016 BB108 LER) is claimed.
**In progress and NOT in the draft**: E-022 (structural criterion for when morphing loses distance) and E-023
(whether d_circ gains give measurable logical-error-rate gains; journal `research/journal/2026-10-10-E-023-ler-benefit.md`).
The draft makes no LER claim; open question (ii) is where E-023 would enter if it is confirmed.

## Revision b (2026-10-10): headline changed to the gross-code circuit with d_circ = 12

Structure now: (1) gross circuit, d_circ = 12 (Table I = the full period-21 circuit, 6 colour classes; construction:
extended code fixed by three unordered sets per check, so reversal + in-pair swaps keep d_ext = 11 and the 4224 list;
proof: template identity + Table I (not Prop. 3), exact lift 0/4224, split-and-translate to all R, weight-12
injection; cost: period 21 vs 8 stated in intro, abstract and a "Cost and scope" paragraph; classical control
0/233 vs 39/39); (2) why it was hard: Fig. 12 = 11, P ≤ 8 retimings exact, bulk obstructions (Table in SM),
944/944 colour-symmetric P = 8 in the class; (3) morphing: [[288]]→[[144,12,12]] = 12 (different code) and the
80-circuit table; (4) other BB theorems: one paragraph in the main text, full table (`tab:bbthm`) and text in SM.
The former "Methods in brief" paragraph was dropped (methods are in the SM sections).

### Revision c (2026-10-10, lead decisions on revision b)
- Classical control in the main text reduced to the audited statement (0/233 random vs the constraint-guided search
  producing the certified circuits); 39/39, 4 s / 40 s and the 6×10⁷-sample control only in the SM, labelled unaudited.
- 2606.30592 sentence, SM mention and bib entry deleted (unverified).
- Title 1 kept as working title.
- Trimmed: "Other BB codes" paragraph → one sentence in the Discussion (details in SM `sm:other`, `tab:bbthm`);
  bulk-obstruction details → SM `sm:gross12` (main keeps the exact P ≤ 8 statement + one bulk sentence);
  80-circuit table → SM (`tab:morph`), main text keeps a compact paragraph + reference to planned Fig. 3.
- Word count (script estimate, LaTeX commands stripped): abstract ≈ 230; main body ≈ 2.6k words excluding tables;
  one main-text table (Table I, ≈ 160 words incl. caption). With three figures this should be near the PRL limit.

Proposed titles (current `\title` is option 1, confirmed by lead as working title):
1. "A single-ancilla syndrome circuit with circuit distance 12 for the gross code"
2. "Interleaving restores the full distance of the gross code: a proven distance-12 syndrome circuit"
3. "The gross code admits a distance-12 single-ancilla syndrome circuit, and other circuit distances that had to be proven"
(The old title "Circuit distances of bivariate-bicycle syndrome circuits must be proven, not inferred" fits a split
methods paper, see PI decision 5.)
Avoid in any title: "better", "optimal", "first … to reach code distance", LER language.

## Missing before any submission

### PI decisions (strategic / irreversible — not taken by the writer)
1. **Whether and how to publish** (STATE "待人决策": arXiv paper vs timestamped public repo vs qldpc-challenge vs not yet).
   Scoop-risk notes: IBM [[72]] high, gross = 11 medium, morphing medium (raised 2026-10-09 because of 2608.19917 v2).
2. **Contacting IBM (Wills / Beverland) or Shaw** to ask whether 2605.21898 App. C's "morphing idling circuit for the
   gross code" is the 2407.16336 [[288,12,18]] → [[144,12,12]] circuit we certify. Outbound contact needs PI approval.
   The draft currently says the identity is not confirmed.
3. **Contacting IonQ (Webster or Delfosse) about how d_circ = 9 in 2604.19481 Tables 9–10 was obtained**
   (outbound contact; affects how C20/C25 can be worded).
4. **Author list, affiliations, acknowledgements**, and how to disclose that the research and the draft were produced
   by AI agents (lead / experimenter / auditor / lit-scout / writer).
5. **Storyline / venue / title**: revision b leads with the gross d_circ = 12 circuit and keeps the other three groups
   as support; PI may prefer to split (gross 12 + obstructions as the PRL; morphing 80 + BB theorems as a methods
   paper). Choose among the proposed titles above.
8. **Timing of release vs. depth-8 / LER work** (new, revision b): scoop risk for the gross-12 result is "medium"
   (2608.19917 v2 lists interleaved lower bounds as next step; qldpc-challenge circuit tier accepts n = 144 entries).
   Waiting for E-023 (LER) or a shorter period would strengthen the paper but delays the timestamp; that trade-off is
   the PI's.
9. **Contacting Strikis / Browne / Beverland** about the answer to their open question (outbound contact; PI only).
6. **How to name the "benchmark family"** for the gross P ≤ 8 result (draft defines it by its rules rather than as
   "our evaluator task").
7. Public code/data release (repository, DOI) for reproduction.

### Content still missing
- **Revision b items needing work before submission**:
  - (done in revision c) unaudited control numbers removed from the main text; they remain in the SM, labelled.
  - Re-run `paper/scripts/extract_class_orders.py` on `search/experiments/e021/cand_p21_spec.json` before submission
    (Table I is the writer's extraction; the "from Fig. 12" column is not in the audit, C32).
  - ~~Add the E-021 proof to `scripts/reproduce_theorems.sh` (currently only the audit's command list exists; SM~~ done 2026-10-10 (`--with-gross12`, ALL PASS)
    Reproduction says so).
  - (done in revision c) 2606.30592 sentence removed.
  - Optional (lead): independent second route to the lower bound without the lift (direct DEM solve timed out), and a
    no-symmetry rerun of d_ext = 11 for the Fig. 12 class (≈7×10¹¹ nodes) — currently the proof depends on E-014 and
    E-018 as audited.
  - Length (revision c): main body ≈ 2.6k words + Table I; figures still to be added. If further cuts are needed:
    shorten the "Proof" paragraph (details are duplicated in SM `sm:p21`).
- **Figures**: none yet; plan in `figures_plan.md` (Fig. 1 timing diagram of the period-21 circuit vs Fig. 12; Fig. 2
  lift outcome across circuit families; Fig. 3 the 80 morphing circuits, d̃ vs d_circ). Older ideas (extended code +
  fold schematic, [[108,8,10]] two-colour rule on the torus, sub-d̃ witness anatomy) are SM candidates.
- **Bibliography**: completed from lit-scout's arXiv abstract-page check
  (`research/literature/2026-10-09-paper-novelty.md`, 2026-10-10). Remaining: initials for 2308.07915, 2506.03094,
  2103.02202, 2108.10457 (only surnames recorded in the project notes).
- **Novelty**: dedicated check done 2026-10-09 (same note): no precedent found for the 80-circuit exact d_circ,
  the morphing d_circ = 12 lower bound, or the Fig. 12 retiming obstruction. New citation added: 2608.19917 v2
  proposes our method combination as future work (scoop risk raised to medium). C25 reworded (old "first rigorous
  … d ≥ 9" withdrawn because 2604.19481 lists d_circ = 9 for d = 9–10 BB/GB codes without a method); C20 restricted
  to ℓ,m ≥ 2 and "stated, reproducible proof". Re-check 2604.19481 (v2?) and 2608.19917 (v3?) before release.
- **Optional side experiment (lead decision)**: compute d_circ of IonQ's [[70,6,9]] schedule (2604.19481 Tables 10, 30)
  with our pipeline; the circuit reconstruction from their Sec. IX.2 / Algorithm 1 is not yet checked to be unique.
- **Recommended low-cost cross-check** (from `novelty-gross11-ibm72.md`): run our tools on the tesseract / 2603.22532
  [[72,12,6]] circuits and compare gate by gate with the IBM order.
- **Compilation**: not tested. `revtex4-2.cls` is not in the local TeX cache and the rules forbid downloads.
  Brace/environment balance was checked by script only.
- **Length**: main text ≈ 2.8k words + 2 tables; probably at the PRL limit once figures are added — expect to move
  Table II or the "other BB codes" paragraph to the SM.

### Reproduction pointers (for the SM / data statement)
- One-command reproduction: `bash scripts/reproduce_theorems.sh [--with-gross] [--with-morphing | --all-morphing]
  [--with-gross-retiming] [--skip-base]`. Default: BB108, the four LRC theorems, IBM [[72]]; `--with-gross`: gross
  Fig. 12 (full PASS log: `research/reproduction/2026-10-07-reproduce_theorems_full.log`).
  `--with-morphing`: E-017 morphing [[144,12,12]] d_circ = 12 (single-round W = 11 exhaustive + W = 12 control, fold
  premise of Prop. 1 checked for T = 2..5, both bases) and E-019's 56 small-parent circuits with exact values incl. the
  8 with d_circ < d̃; `--all-morphing` adds the 24 [[288]] circuits (≈ 14 CPU h, not run in full; subset via
  `MORPH288_KEYS`). `--with-gross-retiming`: E-020 P = 8 (auditor's non-SAT C search: 4 assignments with X0 fixed,
  32 = 8 × 4 unfixed; one weight-11 witness per circuit injected at R = 3, both bases, via the evaluator).
  2026-10-10 from a clean output directory: ALL PASS, morphing + retiming 0.9 CPU h / 33 min
  (`research/reproduction/2026-10-10-reproduce_morphing_retiming.log`); `--all-morphing` with [[288]] f_x sw11 and
  f_y paper ALL PASS (`2026-10-10-reproduce_all_morphing_subset.log`). Not in the script: E-018 (bulk obstruction,
  `research/audits/2026-10-08-E-018.md` §复现命令) and the E-020 CEGAR families (`2026-10-09-E-020.md` §复现命令).
- Gross d_circ = 12 (E-021, revision b, period-21 circuit `search/experiments/e021/cand_p21_spec.json`):
  `bash scripts/reproduce_theorems.sh --skip-base --with-gross12`, auditor scripts only (no e021 code): legality +
  extended code = Fig. 12 (key sets); weight-11 extended-logical list rebuilt from scratch (E-018 audit's w11dfs at
  W = 11, expanded by the 24-element group: 4224 per side); CP-SAT lift R = 1..13 both bases 0/4224; positive control
  Fig. 12 R = 1 4224/4224; weight-12 injection; any-R premises. Nothing is read from `results/`. 2026-10-10 from a
  clean output directory: ALL PASS, 1.3 CPU h / 42 min (`research/reproduction/2026-10-11-reproduce_gross12.log`).
  Not in the script (audit §复现命令 only): MITM cross-check, heuristic upper_bound, R = 14/16/20, cand1 / cand1c, P = 8 family.
- Witnesses for negative results: `research/witnesses/` (E-015) and `results/E-014-E-015-audit/b8_gross_X_*.json`
  (gross two-colour). `results/` is not in git — a data archive is needed for release.
- Upper-bound witnesses for the morphing results are in `results/E-017-*/witness_endcycle.json` and
  `results/E-019-*` (not in git).

### Known wording constraints (do not loosen when editing)
Gross d_circ = 12 (revision b, from STATE item 10, audit E-021 and the 2026-10-10 novelty note):
- Say "distance 12" / "reaches circuit distance 12"; never "better circuit", "improved circuit", "outperforms"; no LER claims.
- Always state the cost: period 21 time steps per round vs 8 (IBM / Fig. 12); never present it as a score of the
  evaluator's gross-dcirc task (max_period 8).
- "Answers in the affirmative the open question of 2603.05481 Sec. IV.3" must come with both: the question has no
  depth condition, and the depth-8 version remains open. Quote the question verbatim:
  "whether any interleaved circuit can achieve circuit distance 12". Do not imply SBB asked about depth 8.
- Say "for the gross code itself"; distinguish it from the morphing 12, which is a different [[144,12,12]] code
  (min stabiliser weight 9 vs 6) and has no dedicated ancillas.
- Never "first BB circuit to reach the code distance" ([[72,12,6]]: 2603.22532 public data; our own C21).
- Scope: SD6 fault set + CNOT template (one dedicated ancilla per check, reset–6 CNOT–measure per round); no CZ/H
  compilations, biased noise, leakage.
- The lower-bound reduction is "template identity + SBB Table I", not Prop. 3.
- P = 8 exclusion only for colour-symmetric circuits in the Fig. 12 class (finite R = 1); per-check-free P = 8 and
  periods 9–20 are open. Do not write "P ≤ 8 is impossible".
- The proof depends on E-014 (d_ext = 11) and E-018 (complete 4224 list); a direct DEM solve did not finish.

Earlier constraints:
- Never "gross code proven 12" (the morphing end-cycle code is inequivalent to the gross code).
- Never "the paper's Table II circuit is 6"; never "[[72,12,8]] = 6 is new"; never "sub-d̃ comes from reset errors".
- Never an unscoped "12 is unreachable" for the gross code; bulk results ≠ R = 3 task results.
- State Prop. 1's premise in the auditor's basis-free form.
- IBM [[72]]: always mention the 2603.22532 partial precedent. BB108: "first for BB (ℓ,m ≥ 2) d ≥ 10 with a stated,
  reproducible proof", not "first qLDPC", not "first rigorous for d ≥ 9".
- Table IX caption: say the code-level order-independence "does not extend to the circuit distance"; no
  "contradicting/refuting"; [[54,8,8]] is not an entry of Table IX.
