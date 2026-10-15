#!/bin/bash
# E-028 step 1: all coset colourings of Z15 x Z3 (index 3, 5, 9, 15), both sides.
cd "$(dirname "$0")/../../.."
for sub in "0,0;1,0" "0,0;1,1" "0,0;1,2" "0,0;3,1" "0,1;5,0" "0,0;3,0" "0,0;0,1" "0,0;5,0" "0,0;5,1" "0,0;5,2"; do
  for k in X Z; do
    PYTHONPATH=.:tests uv run python -m search.experiments.e028.dext --kind $k --sub "$sub" --workers 4 --max_sec 3600 2>&1 | grep -E "SURVIVOR|DONE|\|H\|"
  done
done
