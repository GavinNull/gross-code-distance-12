#!/bin/bash
# E-026b stage A4: lambda = 0.1, p = 2e-3, p18 vs fig12, BP-OSD only, extend A3_2e-3 to <= 190000 shots per basis
# (the only lambda > 0 point where a crossover inside [1e-3, 4e-3] is still open).  4 workers.
cd "$(dirname "$0")/../../.."
/usr/bin/time -l uv run python -m search.experiments.e026b.direct --workers 4 --max-errors 25 --model lam0.1 \
    --circs p18,fig12 --ps 0.002 --decoders bposd --max-shots 190000 --tag A3_2e-3
echo STAGE4_DONE
