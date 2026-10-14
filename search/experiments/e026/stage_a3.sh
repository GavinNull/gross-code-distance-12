#!/bin/bash
# E-026 stage A3: p18 at 1e-3 (more shots, the practical-p anchor) and 1.25e-3; ibm/fig12 at 2e-3 and 1e-3 with
# fixed shot budgets (upper bounds / few-error estimates).
cd "$(dirname "$0")/../../.."
D="uv run python -m search.experiments.e026.direct"
T="/usr/bin/time -l"
$T $D --circs p18 --ps 0.001 --max-errors 40 --max-shots 20000 --tag a6_p18_1e-3
$T $D --circs ibm,fig12 --ps 0.002,0.001 --max-errors 40 --max-shots 10000 --tag a7_low_ub
$T $D --circs p18 --ps 0.00125 --max-errors 60 --max-shots 6000 --tag a8_p18_1.25e-3
echo STAGE_A3_DONE
