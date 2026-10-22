#!/bin/bash
# E-033 stage 2 (after L0_hi): lambda=0 p=3e-3; lambda=1 u11 at 3e-3, 2e-3; positive control (ibm lam1 4e-3 BP-OSD).
cd "$(dirname "$0")/../../.." || exit 1
D="uv run python -m search.experiments.e033.direct --workers 3"
$D --circs u11,ibm --ps 0.003 --model lam0 --max-errors 12 --max-shots 40000 --tag L0_3e-3
$D --circs fig12 --ps 0.003 --model lam0 --max-errors 12 --max-shots 20000 --tag L0_3e-3
$D --circs u11 --ps 0.003,0.002 --model lam1 --max-errors 20 --max-shots 20000 --tag L1_u11
$D --circs ibm --ps 0.004 --model lam1 --decoders bposd --max-errors 30 --max-shots 4000 --tag P_ctl
