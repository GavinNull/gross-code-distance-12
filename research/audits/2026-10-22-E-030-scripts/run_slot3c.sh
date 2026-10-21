#!/bin/bash
cd "$(dirname "$0")/../../.." || exit 1
S=research/audits/2026-10-22-E-030-scripts
O=results/E-030-audit
until [ -f $O/slot3b.done ]; do sleep 15; done
uv run python $S/a7_ibm_count.py Z 1 2 > $O/a7_ibm_Z.log 2>&1
uv run python $S/a7_ibm_count.py X 1 2 > $O/a7_ibm_X.log 2>&1
echo DONE > $O/slot3c.done
