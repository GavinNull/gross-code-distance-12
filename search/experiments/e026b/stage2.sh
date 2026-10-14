#!/bin/bash
# E-026b stage A2 (replaces the stopped A1 call; A1_hi.csv data kept). Per-decoder shot caps keep each series
# <~ 1000-2000 CPU s; 3 sinter workers (+1 process for lead.py) = 4 processes.
cd "$(dirname "$0")/../../.."
D="uv run python -m search.experiments.e026b.direct --workers 3 --max-errors 25"
T="/usr/bin/time -l"
# lambda = 0, 4e-3 and 3e-3 (A1_hi resume file so the p18 Z data is extended, not duplicated)
$T $D --model lam0 --ps 0.004,0.003 --decoders bposd  --max-shots 5000  --tag A1_hi
$T $D --model lam0 --ps 0.004,0.003 --decoders relay5 --max-shots 12000 --tag A1_hi
# lambda = 0.3 and 0.1, 4e-3 and 3e-3
$T $D --model lam0.3,lam0.1 --ps 0.004,0.003 --decoders bposd  --max-shots 3000 --tag A1_hi
$T $D --model lam0.3,lam0.1 --ps 0.004,0.003 --decoders relay5 --max-shots 6000 --tag A1_hi
echo STAGE2_DONE
