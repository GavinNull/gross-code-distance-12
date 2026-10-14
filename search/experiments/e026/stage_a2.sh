#!/bin/bash
# E-026 stage A (revised after machine contention): fewer errors per point; /usr/bin/time records true CPU.
cd "$(dirname "$0")/../../.."
D="uv run python -m search.experiments.e026.direct"
T="/usr/bin/time -l"
$T $D --circs ibm,fig12 --ps 0.005,0.004 --max-errors 60 --max-shots 20000 --tag a3_hi
$T $D --circs ibm,fig12 --ps 0.003 --max-errors 40 --max-shots 60000 --tag a4_3e-3
$T $D --circs ibm,fig12 --ps 0.002 --max-errors 20 --max-shots 200000 --tag a5_2e-3
echo STAGE_A2_DONE
