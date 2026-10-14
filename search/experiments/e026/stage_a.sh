#!/bin/bash
# E-026 stage A direct sampling, phases run sequentially (each <= 6 sinter workers).
set -e
cd "$(dirname "$0")/../../.."
D="uv run python -m search.experiments.e026.direct"
$D --circs p18 --ps 0.002,0.0015,0.001 --max-errors 100 --max-shots 3000 --tag a2_p18_low
$D --circs ibm,fig12 --ps 0.005,0.004 --max-errors 150 --max-shots 20000 --tag a3_hi
$D --circs ibm,fig12 --ps 0.003 --max-errors 100 --max-shots 60000 --tag a4_3e-3
echo STAGE_A_DONE
