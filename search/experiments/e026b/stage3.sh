#!/bin/bash
# E-026b stage A3 (after stage2): lambda=0 top-up at 3e-3, 2e-3 for lambda 0 / 0.1, p18 at lambda 0.3 lower p,
# si1000cx reference.  4 sinter workers (nothing else runs).
cd "$(dirname "$0")/../../.."
while kill -0 83746 2>/dev/null; do sleep 30; done   # wait for stage2.sh (PID 83746)
D="uv run python -m search.experiments.e026b.direct --workers 4 --max-errors 25"
T="/usr/bin/time -l"
$T $D --model lam0 --ps 0.003 --decoders bposd  --max-shots 15000 --tag A1_hi
$T $D --model lam0 --ps 0.003 --decoders relay5 --max-shots 30000 --tag A1_hi
$T $D --model lam0,lam0.1 --ps 0.002 --decoders bposd  --max-shots 10000 --tag A3_2e-3
$T $D --model lam0,lam0.1 --ps 0.002 --decoders relay5 --max-shots 10000 --tag A3_2e-3
$T $D --model lam0.3 --circs p18 --ps 0.002,0.0015 --max-shots 4000 --tag A3_p18_lam0.3
$T $D --model si1000cx --ps 0.002,0.001 --decoders bposd  --max-shots 4000 --tag S_si1000cx
$T $D --model si1000cx --ps 0.002,0.001 --decoders relay5 --max-shots 8000 --tag S_si1000cx
echo STAGE3_DONE
