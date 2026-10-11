#!/bin/sh
# usage: ladder.sh P max_sec "sub1" "sub2" ...   -- runs cegar at fixed P for each subgroup in turn
P=$1; MS=$2; shift 2
for SUB in "$@"; do
  T=$(echo "$SUB" | tr -d ',' | tr ';' '_'); [ -z "$T" ] && T=triv
  PYTHONPATH=.:tests uv run python -m search.experiments.e024a.cegar --P $P --sub "$SUB" --tighten 0 --max_sec $MS --tag P${P}_s$T > results/E-024a-gross12-period/P${P}_s$T.log 2>&1
done
