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
   Scoop-risk notes: IBM [[72]] high, gross = 11 medium, morphing low–medium (lit notes).
2. **Contacting IBM (Wills / Beverland) or Shaw** to ask whether 2605.21898 App. C's "morphing idling circuit for the
   gross code" is the 2407.16336 [[288,12,18]] → [[144,12,12]] circuit we certify. Outbound contact needs PI approval.
   The draft currently says the identity is not confirmed.
3. **Author list, affiliations, acknowledgements**, and how to disclose that the research and the draft were produced
   by AI agents (lead / experimenter / auditor / lit-scout / writer).
4. **Storyline / venue**: the draft bundles four result groups; PI may prefer to split (e.g. morphing + gross into a
   PRL, BB theorems into a longer methods paper).
5. **How to name the "benchmark family"** for the gross P ≤ 8 result (draft defines it by its rules rather than as
   "our evaluator task").
6. Public code/data release (repository, DOI) for reproduction.

### Content still missing
- **Figures**: none yet. Suggested: (a) schematic of extended code + fold reduction; (b) the 80-circuit landscape
  (d̃ vs d_circ); (c) gross obstruction family map (Table S1 as a diagram); (d) the [[108,8,10]] two-colour rule on the
  torus; (e) a witness anatomy for a sub-d̃ morphing error (CNOT-only, single interior half-cycle).
- **Bibliography**: titles and first names for 13 entries are not recorded in `research/literature/` and are marked
  [UNVERIFIED] (see `claims_map.md` §Bibliography). A lit-scout pass must fill them from arXiv abstract pages.
  Wang–Mueller 2408.10001 authors/title come only from a search-result URL.
- **Novelty checks not yet done** (lit-scout):
  - E-019 (80-circuit family, Table IX caption, [[72,12,8]]/[[72,12,7]] tightness) and E-020/E-018 (gross obstruction)
    have no dedicated novelty note; only indirect coverage by `morphing-d12-novelty.md` (2026-10-08) and
    `novelty-interleaved-circuits.md` (2026-10-02, old).
  - **Caveat found while writing**: 2604.19481 (IonQ, Tripier et al.) lists d_circ = 9 (no "≤") for a [[70,6,9]] BB7
    code, method not found (`novelty-bb108-dcirc10.md`). This threatens the C25 wording "first rigorous circuit distances
    for BB codes with d ≥ 9". The d ≥ 10 wording (C20) is unaffected. Resolve before public use.
  - Refresh all searches (latest notes are 2026-10-07/08).
- **Recommended low-cost cross-check** (from `novelty-gross11-ibm72.md`): run our tools on the tesseract / 2603.22532
  [[72,12,6]] circuits and compare gate by gate with the IBM order.
- **Compilation**: not tested. `revtex4-2.cls` is not in the local TeX cache and the rules forbid downloads.
  Brace/environment balance was checked by script only.
- **Length**: main text ≈ 2.8k words + 2 tables; probably at the PRL limit once figures are added — expect to move
  Table II or the "other BB codes" paragraph to the SM.

### Reproduction pointers (for the SM / data statement)
- One-command lower-bound reproduction: `bash scripts/reproduce_theorems.sh [--with-gross]`
  (log of a full PASS run: `research/reproduction/2026-10-07-reproduce_theorems_full.log`). Covers BB108, the four LRC
  theorems, IBM [[72]], gross Fig. 12. **Does not yet cover** E-017 (morphing 12), E-019 (80 circuits), E-020/E-018
  (gross obstruction); their reproduction commands are only in the audit reports:
  `research/audits/2026-10-08-E-017.md` §Reproduction, `2026-10-08-E-019.md` §复现, `2026-10-08-E-018.md` §复现命令,
  `2026-10-09-E-020.md` §复现命令. A unified script should be added before release.
- Witnesses for negative results: `research/witnesses/` (E-015) and `results/E-014-E-015-audit/b8_gross_X_*.json`
  (gross two-colour). `results/` is not in git — a data archive is needed for release.
- Upper-bound witnesses for the morphing results are in `results/E-017-*/witness_endcycle.json` and
  `results/E-019-*` (not in git).

### Known wording constraints (do not loosen when editing)
- Never "gross code proven 12" (the morphing end-cycle code is inequivalent to the gross code).
- Never "the paper's Table II circuit is 6"; never "[[72,12,8]] = 6 is new"; never "sub-d̃ comes from reset errors".
- Never an unscoped "12 is unreachable" for the gross code; bulk results ≠ R = 3 task results.
- State Prop. 1's premise in the auditor's basis-free form.
- IBM [[72]]: always mention the 2603.22532 partial precedent. BB108: "first for BB d ≥ 10", not "first qLDPC".
