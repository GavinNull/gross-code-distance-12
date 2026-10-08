#!/bin/sh
# E-020: run the subgroup hierarchy for period $1 from list file $2 (lines "tag generators"), lane $3 of $4 lanes.
P=$1; LIST=$2; LANE=$3; NL=$4; MAXS=${5:-3600}
cd /Users/ephemeral/Desktop/qec-ai-search
n=0
while read tag gen; do
  if [ $((n % NL)) -eq $LANE ]; then
    PYTHONPATH=.:tests uv run python -m search.experiments.e020.cegar --P $P --sub "$gen" --tag ${tag}_P$P --max_sec $MAXS \
      > results/E-020-gross-perchk-pipeline/cegar_${tag}_P$P.log 2>&1
  fi
  n=$((n + 1))
done < $LIST
