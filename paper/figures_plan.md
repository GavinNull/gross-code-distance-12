# Figure plan for `paper/draft.tex` (revision c, 2026-10-10)

No figure has been produced yet. Every panel below is drawn only from existing files; nothing is to be
re-computed or invented for the figures. Where a panel would need data that does not exist yet, it says so.
`results/` is not in git: figures built from it need the data archive (README, PI decision 7).
Plotting code, when written, goes to `paper/figures/` (one script per figure, reading the files listed here).

## Fig. 1 (main, top of the Letter): timing diagram of the period-21 gross circuit vs Fig. 12

Purpose: show at a glance what the new circuit is (Table I made visual): one period, six colour classes, where
the X- and Z-check CNOTs sit, and that they interleave; contrast with the 8-step Fig. 12 schedule.

- Panel (a): cand_p21. Rows = the six classes X0, X1, X2, Z0, Z1, Z2 (24 checks each). Horizontal axis = time
  step 0..20. Reset marker at 0, measurement marker at 20, one box per CNOT labelled A1..B3 at its time step.
  Colour the A-block and B-block terms differently; mark the class X1 (unchanged from Fig. 12) and annotate the
  others with s12 / s12·s56.
- Panel (b): Fig. 12 at the same scale (8 steps, pipelined: X checks reset at 4 or 5 and measure at 3 or 4 of
  the next period; Z checks reset at 0/1). Draw the wrap-around explicitly.
- Optional inset: one data qubit's cyclic X/Z CNOT sequence over a period in both circuits (non-interleaved in
  Fig. 12; 4 switches for 48 of the 144 qubits in cand_p21).
- Data: `search/experiments/e021/cand_p21_spec.json` (in git), `results/E-021-gross-new-orders/fig12_spec.json`.
  Per-class orders and times: `uv run python paper/scripts/extract_class_orders.py <spec>` (prints exactly the
  numbers of Table I / SM). The per-qubit switch counts need a small extra script over the spec (not written yet;
  the audit number to check against is "48 qubits × 4 switches", `research/audits/2026-10-10-E-021.md` F1).
- Caption must state: period 21 vs 8; SD6 distance 12 (not LER); depth-8 version open.

## Fig. 2 (main): why the orders had to change — lift outcome across circuit families

Purpose: one panel that carries the "why it was hard" story quantitatively, with only audited counts (plus the
experiment-log control clearly marked).

- Layout: a horizontal "lift outcome" chart, one row per circuit/family, bar = fraction of circuits (or of the
  4224 weight-11 extended logicals) that lift to an undetected circuit error.
  1. Fig. 12 itself: 4224/4224 weight-11 extended logicals lift (C13, C34 positive control).
     Source: `results/E-018-audit/a9_fig12.json`; `results/E-021-audit/b3_fig12_Z_1.json`, `b3_fig12_X_1-2.json`.
  2. Period-8 retimings keeping Fig. 12 orders: 4/4 circuits (up to translation) have weight-11 undetected errors,
     R = 1..6, both bases (C14, C15). Source: `results/E-020-audit/b2_inject_1_3_6.json`, `b2_inject_2_4_5.json`.
  3. Period-8 colour-symmetric circuits in the Fig. 12 class: 944/944 have a weight-11 undetected error at R = 1 (C38).
     Source: `results/E-021-audit/b9_p8.json`.
  4. Random legal deterministic circuits of the search family (SAT sampler without blocking clauses): 233/233 have
     a liftable weight-11 logical, 0 certified (C39; in STATE). Source: `results/E-021-gross-new-orders/randsat_summary.json`.
  5. (dropped in revision c by lead decision: the 39/39 reasoned-candidate count is unaudited; do not plot it.)
  6. cand_p21: 0/4224 lift, R = 1..14, 16, both bases (C34). Source: `results/E-021-audit/cand_p21/b3_cand_{X,Z}_*.json`.
- Optional schematic inset (no data): a "10 data + 1 hook" weight-11 error — ten data-qubit faults plus one ancilla
  fault after the 4th CNOT of an X check, whose two-qubit residual {q5, q6} completes a weight-12 code logical;
  show how detectors of neighbouring Z checks would see the residual under one timing and miss it under another.
  This is an illustration of the mechanism of E-018 §C (no numbers); keep it generic, do not draw a specific
  witness unless taken from `results/E-020-audit/b2_inject_*.json` (injected weight-11 witnesses for the P = 8 retimings).
- Do not plot the frame-model families of Table S-gross as bars: those are bulk statements (sufficiently many
  rounds) and mixing them with exact finite-R counts would mislead. They stay in the SM table.

## Fig. 3 (main; the main text cites it, the full table is in the SM): the 80 morphing circuits — end-cycle distance vs circuit distance

Purpose: the evidence that circuit distances must be proven (C5–C9).

- Scatter / dot plot: x = end-cycle distance d̃, y = exact d_circ, one marker per circuit (both bases equal),
  jittered or with counts; diagonal y = x. The 8 sub-d̃ circuits off the diagonal, labelled
  ([[54,8,8]] std b3 = x² → 6; std b3 = x and rev → 7; [[72,12,8]] rev f_x → 6). Marker shape by mother code
  ([[72]], [[108]], [[144]], [[288]]); filled = independently reproduced by the auditor (all 56 small-mother
  circuits; 3 of 24 [[288]]), open = experimenter pipeline only (21 [[288]] circuits).
- Data: `results/E-019-morphing-family/summary.json` (list of records with `key`, `basis`, `n_end`, `k`, `d_end`,
  `d_circ`, `status`, checks, witness flags) — 160 records = 80 circuits × 2 bases. Auditor agreement:
  `results/E-019-audit/jobs2.out` (small mothers), `results/E-019-audit/dfs/` and `t10_ub288.jsonl` ([[288]]).
  Cross-check counts against Table II of the draft before plotting (18+6+2+2+2+2+18+2+2+2+16+8 = 80).
- Caption: Table IX caption statement ("order not important") holds for the end-cycle codes, not for d_circ; no
  "refuting" wording; [[72,12,8]] = 6 is tightness of an existing bound, not a new discovery.

## Not planned (and why)

- No logical-error-rate plot: E-023 (LER benefit) is in progress and not in the draft; no LER claim may be made.
- No "criterion for when morphing loses distance" figure: E-022 is in progress and not in the draft.
- No figure for the other BB theorems (Table S-bbthm); the earlier idea of a torus diagram of the [[108,8,10]]
  y-parity rule can go to the SM if space allows (data: SM term orders, `results/E-005-noninterleaved-bound/e013_assembled_x2_14_z12_0.json`).
