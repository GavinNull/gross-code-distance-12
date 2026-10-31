#!/bin/bash
# Theorem 5 bulk lifts on the auditor's lists: CP-SAT (B_audit) on EVERY set, then theory B's Bellman-Ford dc.py on
# orbit representatives; positive controls (weight = target) at the end.
cd "$(dirname "$0")/../../.."
F="uv run python -m search.experiments.e043_audit.lift"
O=results/E-043-audit
$F ibm90 Z 7 --flips 0
$F ibm90 X 6 --flips 1; $F ibm90 X 7 --flips 0
for c in b9 b10 g9; do
  w=7; [ $c = g9 ] && w=9
  for b in Z X; do $F $c $b $w --flips 1; $F $c $b $((w+1)) --flips 0; done
done
$F ibmg Z 9 --flips 0
$F ibmg X 8 --flips 1; $F ibmg X 9 --flips 0
# second solver
dc() { uv run python -m search.experiments.e043_audit.reps $1 $2 $3 >/dev/null;
       uv run python -m search.theory.B.dc --code $4 --spec $5 --basis $2 --list $O/reps_$1_$2_w$3.pkl --flips $6 --out $O/dc.jsonl; }
dc ibm90 Z 7 bb90 search/experiments/e030/ibm90_spec.json 0
dc ibm90 X 6 bb90 search/experiments/e030/ibm90_spec.json 1
dc ibm90 X 7 bb90 search/experiments/e030/ibm90_spec.json 0
for b in Z X; do
  dc b9 $b 7 bb90 search/experiments/e043/b9_d9_spec.json 1;  dc b9 $b 8 bb90 search/experiments/e043/b9_d9_spec.json 0
  dc b10 $b 7 bb90 search/experiments/e043/b10_d9_spec.json 1; dc b10 $b 8 bb90 search/experiments/e043/b10_d9_spec.json 0
  dc g9 $b 9 gross search/experiments/e043/g9_d11_spec.json 1;  dc g9 $b 10 gross search/experiments/e043/g9_d11_spec.json 0
done
dc ibmg Z 9 gross search/experiments/e033/ibm_gross_spec.json 0
dc ibmg X 8 gross search/experiments/e033/ibm_gross_spec.json 1
dc ibmg X 9 gross search/experiments/e033/ibm_gross_spec.json 0
# positive controls (one more flip / weight = target): the solver must find lifts where witnesses exist
$F ibm90 Z 7 --flips 1 --reps; $F ibm90 X 7 --flips 1 --reps
for b in Z X; do $F b9 $b 8 --flips 1 --reps; $F b10 $b 8 --flips 1 --reps; $F g9 $b 10 --flips 1 --reps; done
$F ibmg X 8 --flips 2 --reps
