#!/bin/bash
# E-033 stage 3 (after stage 2): lambda=1 ibm top-up at 2e-3 (E-026 had 1-3 failures); lambda=0.1 u11 at 4e-3, 3e-3
# (ibm / fig12 at lambda=0.1 from E-026b, pooled in analyze).
cd "$(dirname "$0")/../../.." || exit 1
D="uv run python -m search.experiments.e033.direct --workers 3"
$D --circs ibm --ps 0.002 --model lam1 --max-errors 15 --max-shots 50000 --tag L1_ibm2e-3
$D --circs u11 --ps 0.004,0.003 --model lam0.1 --max-errors 15 --max-shots 12000 --tag L01_u11
