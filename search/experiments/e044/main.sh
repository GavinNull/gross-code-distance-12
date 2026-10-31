#!/bin/bash
# E-044 phase B: per task "circ:basis:model:cpu_seconds" -> alloc (no failure data) -> strat run tag main.
cd "$(dirname "$0")/../../.." || exit 1
for t in "$@"; do
  IFS=: read c b m s <<< "$t"
  PYTHONPATH=.:tests uv run python -m search.experiments.e044.alloc $c $b $m $s
  PYTHONPATH=.:tests uv run python -m search.experiments.e044.strat run --circ $c --basis $b --model $m \
     --alloc results/E-044-crossover/alloc/main_${c}_${b}_${m}.json --tag main --batch 500
  echo "DONE $t $(date)"
done
