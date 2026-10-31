#!/bin/bash
# E-044 phase C (decided 2026-11-01 after phase B left only 5-11 failures per gross lam1 task, all from the
# starved k >= 22 strata): fixed 2500 (ibm, g10) / 1500 (u11) extra shots at every k = 22..40, tag phaseC;
# then the remaining lam0 tasks of queue B (u11 lam0 dropped: budget; E-033 has direct u11 lam0 data).
cd "$(dirname "$0")/../../.." || exit 1
while pgrep -f "strat run --circ ibm90 --basis X --model lam0" >/dev/null; do sleep 15; done
for t in ibm:Z g10:Z ibm:X g10:X u11:Z u11:X; do
  IFS=: read c b <<< "$t"
  PYTHONPATH=.:tests uv run python -m search.experiments.e044.strat run --circ $c --basis $b --model lam1 \
     --alloc results/E-044-crossover/alloc/phaseC_${c}_${b}_lam1.json --tag phaseC --batch 500
  echo "DONE phaseC $t $(date)"
done
search/experiments/e044/main.sh c11:X:lam0:2500 ibm:X:lam0:5000 g10:X:lam0:5000
