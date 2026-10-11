#!/bin/sh
# usage: lattice.sh P max_sec  -- cegar at fixed P for every nontrivial proper subgroup of G24 and the trivial group
P=$1; MS=$2
for SUB in "1,2" "1,5" "0,3;2,1" "0,3;3,0" "2,1" "2,4" "4,5" "3,0" "3,3" "0,3;6,0" "4,2" "0,3" "6,0" "6,3" ""; do
  T=$(echo "$SUB" | tr -d ',' | tr ';' '_'); [ -z "$T" ] && T=triv
  LOG=results/E-024a-gross12-period/P${P}_s$T.log
  if grep -q "^STATUS" $LOG 2>/dev/null; then continue; fi
  PYTHONPATH=.:tests uv run python -m search.experiments.e024a.cegar --P $P --sub "$SUB" --tighten 0 --max_sec $MS --tag P${P}_s$T > $LOG 2>&1
done
