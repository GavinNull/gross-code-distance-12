#!/bin/bash
# E-024b step 1: all colourings of index 2 and 3, both sides (sequential, 4 DFS workers)
cd "$(dirname "$0")/../../.."
for col in 3,1,1 3,1,0 3,0,1 3,1,2 2,1,0 2,0,1 2,1,1; do
  for kind in X Z; do
    [ "$kind$col" = "X3,1,1" ] && continue
    PYTHONPATH=. uv run python -m search.experiments.e024b.dextsat --kind $kind --col $col --workers 4 \
      >> results/E-024b-gross12-other-classes/dext_${kind}_${col//,/}.log 2>&1
  done
done
echo ALLDONE >> results/E-024b-gross12-other-classes/dext_summary.jsonl
