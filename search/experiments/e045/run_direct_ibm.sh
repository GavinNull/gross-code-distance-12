#!/bin/sh
# E-045 Part B sanity beyond the certified R: the E-037 auditor's independent DEM builder + mincc (no E-037 constraints),
# IBM 12+2 / 10+2 model, R > 12 (gross) / R > 10 ([[108]]).  One process at a time.
cd "$(dirname "$0")/../../.."
O=results/E-045-crocker/partB/direct/mincc.jsonl
for R in 11 12 13 14 16 20; do for t in X Z; do
  uv run python search/experiments/e037_audit/run_mincc.py ibm:bb108:$t:$R 7 --sym --out $O; done; done
for t in X Z; do uv run python search/experiments/e037_audit/run_mincc.py ibm:gross:$t:13 9 --sym --out $O; done
