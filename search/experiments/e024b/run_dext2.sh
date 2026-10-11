#!/bin/bash
# E-024b step 1b: coset colourings of index 4, 6, 8, 9 (both sides, sequential, 4 DFS workers)
cd "$(dirname "$0")/../../.."
for sub in "0,1;4,0" "0,2;2,0" "0,2;2,1" "0,0;1,0" "0,0;1,1" "0,0;1,2" "0,0;1,3" "0,0;1,4" "0,0;1,5" "0,0;3,1" "0,0;3,2" "0,1;6,0" "0,3;2,0" "0,3;2,1" "0,3;2,2" "0,2;4,0" "0,3;3,0"; do
  for kind in X Z; do
    PYTHONPATH=. uv run python -m search.experiments.e024b.dextsat2 --kind $kind --sub "$sub" --workers 4 --max_sec 5400 \
      >> results/E-024b-gross12-other-classes/dext2_${kind}_${sub//[,;]/}.log 2>&1
  done
done
echo ALLDONE2 >> results/E-024b-gross12-other-classes/dext_summary.jsonl
