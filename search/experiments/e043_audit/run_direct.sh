#!/bin/bash
# direct exhaustive search on the evaluator's SD6 DEM (no extended code / lemmas); one mitmsearch process at a time
cd "$(dirname "$0")/../../.."
D="uv run python -m search.experiments.e043_audit.direct"
# upper-bound witnesses at R = 1 (W = claimed d_circ)
for b in Z X; do
  $D ibm90 $b 1 8; $D b9 $b 1 9; $D b10 $b 1 9; $D ibmg $b 1 10; $D g9 $b 1 11
done
# lower bounds: nothing of weight <= t - 1
for R in 1 2 3 4; do for b in Z X; do $D ibm90 $b $R 7; $D b9 $b $R 8; $D b10 $b $R 8; done; done
for R in 1 2 3; do for b in Z X; do $D ibmg $b $R 9; $D g9 $b $R 10; done; done
