#!/bin/bash
# E-044 phase A pilot: one task at a time per queue.  usage: pilot.sh "circ:basis:model" ...
cd "$(dirname "$0")/../../.." || exit 1
for t in "$@"; do
  IFS=: read c b m <<< "$t"
  case $c in g10|u11|ibm) fam=gross;; *) fam=bb90;; esac
  PYTHONPATH=.:tests uv run python -m search.experiments.e044.strat run --circ $c --basis $b --model $m \
     --alloc results/E-044-crossover/alloc/pilot_$fam.json --tag pilot --batch 100
  echo "DONE $t $(date)"
done
