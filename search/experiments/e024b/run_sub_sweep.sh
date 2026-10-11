#!/bin/bash
# E-024b: Fig. 12 class with finer symmetry (subgroup SUB of ker((a+b) mod 3)), wrap, periods PS (pairs run concurrently).
cd "$(dirname "$0")/../../.."
X=A1A2A3B3B1B2,A1A2A3B1B2B3,A1A3A2B3B1B2; Z=A1A3A2B3B1B2,A1A2A3B1B2B3,A1A2A3B3B1B2; R=results/E-024b-gross12-other-classes
SUB=${SUB:-1,2}; TAGS=${TAGS:-s12}; PS=${PS:-"17 16 15 14 13 12"}; MAXS=${MAXS:-2400}
run() { PYTHONPATH=.:tests uv run python -m search.experiments.e024b.gsat --col 3,1,1 --x $X --z $Z --P $1 --sub "$SUB" \
          --max_sec $MAXS --tag gs_fig12_${TAGS}_P$1 > $R/gs_fig12_${TAGS}_P$1.log 2>&1; }
set -- $PS
while [ $# -gt 0 ]; do
  run $1 & p1=$!
  if [ $# -gt 1 ]; then run $2 & p2=$!; wait $p2; fi
  wait $p1
  shift; [ $# -gt 0 ] && shift
done
echo DONE > $R/subsweep_${TAGS}_done.txt
