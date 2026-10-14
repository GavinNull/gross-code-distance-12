#!/bin/bash
# E-026b stage V (lambda = 1 re-check vs E-026) + stage A1 (lambda in {0, 0.1, 0.3}, p in {4e-3, 3e-3}).
# Each call <= 4 sinter workers, run sequentially; /usr/bin/time -l records true CPU (user+sys).
cd "$(dirname "$0")/../../.."
D="uv run python -m search.experiments.e026b.direct"
T="/usr/bin/time -l"
$T $D --model lam1 --circs ibm --ps 0.004 --decoders bposd --max-errors 60 --max-shots 20000 --tag V_ibm
$T $D --model lam1 --circs p18 --ps 0.002 --decoders bposd --max-errors 60 --max-shots 1000 --tag V_p18
$T $D --model lam0,lam0.1,lam0.3 --ps 0.004,0.003 --max-errors 20 --max-shots 40000 --tag A1_hi
echo STAGE1_DONE
