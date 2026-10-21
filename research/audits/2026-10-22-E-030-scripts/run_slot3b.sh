#!/bin/bash
cd "$(dirname "$0")/../../.." || exit 1
S=research/audits/2026-10-22-E-030-scripts
O=results/E-030-audit
until [ -f $O/slot3.done ]; do sleep 15; done
uv run python $S/a6_c13_sig.py > $O/a6_c13_sig.log 2>&1
uv run python $S/a3_lift.py search/experiments/e030/c12_spec.json Z 1 2 3 4 > $O/a3_c12_Z.log 2>&1
uv run python $S/a3_lift.py search/experiments/e030/c12_spec.json X 1 2 3 4 > $O/a3_c12_X.log 2>&1
echo DONE > $O/slot3b.done
