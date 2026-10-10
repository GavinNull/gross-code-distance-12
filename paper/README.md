# paper/ — internal first draft (2026-10-09)

Files:
- `draft.tex` — PRL-style letter (revtex4-2) + Supplemental Material in the same file. Claim tags `[Cn]`
  (blue superscripts; switch off with `\showclaimtagsfalse`), red `[TODO]` and `[UNVERIFIED]` markers.
- `claims_map.md` — every tag `[Cn]` → STATE confirmed item, audit file + section, results path, wording limits.

Scope rule used: only `research/STATE.md` "已确认结果" items 1–9 are claimed, inside the scope stated there and in the
referenced audits. Nothing from "待复核的结论" (E-010 three-colour BB108, E-016 BB108 LER) is claimed.

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
5. **Storyline / venue**: the draft bundles four result groups; PI may prefer to split (e.g. morphing + gross into a
   PRL, BB theorems into a longer methods paper).
6. **How to name the "benchmark family"** for the gross P ≤ 8 result (draft defines it by its rules rather than as
   "our evaluator task").
7. Public code/data release (repository, DOI) for reproduction.

### Content still missing
- **Figures**: none yet. Suggested: (a) schematic of extended code + fold reduction; (b) the 80-circuit landscape
  (d̃ vs d_circ); (c) gross obstruction family map (Table S1 as a diagram); (d) the [[108,8,10]] two-colour rule on the
  torus; (e) a witness anatomy for a sub-d̃ morphing error (CNOT-only, single interior half-cycle).
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
- Witnesses for negative results: `research/witnesses/` (E-015) and `results/E-014-E-015-audit/b8_gross_X_*.json`
  (gross two-colour). `results/` is not in git — a data archive is needed for release.
- Upper-bound witnesses for the morphing results are in `results/E-017-*/witness_endcycle.json` and
  `results/E-019-*` (not in git).

### Known wording constraints (do not loosen when editing)
- Never "gross code proven 12" (the morphing end-cycle code is inequivalent to the gross code).
- Never "the paper's Table II circuit is 6"; never "[[72,12,8]] = 6 is new"; never "sub-d̃ comes from reset errors".
- Never an unscoped "12 is unreachable" for the gross code; bulk results ≠ R = 3 task results.
- State Prop. 1's premise in the auditor's basis-free form.
- IBM [[72]]: always mention the 2603.22532 partial precedent. BB108: "first for BB (ℓ,m ≥ 2) d ≥ 10 with a stated,
  reproducible proof", not "first qLDPC", not "first rigorous for d ≥ 9".
- Table IX caption: say the code-level order-independence "does not extend to the circuit distance"; no
  "contradicting/refuting"; [[54,8,8]] is not an entry of Table IX.
