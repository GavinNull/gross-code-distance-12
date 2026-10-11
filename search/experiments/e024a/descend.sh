#!/bin/sh
# usage: descend.sh "<sub generators>" Pstart Pmin max_sec
# runs cegar at P = Pstart, Pstart-1, ... while CERTIFIED; stops at first non-CERTIFIED (UNSAT / UNKNOWN) or Pmin.
SUB="$1"; P=$2; PMIN=$3; MS=$4
TAGSUB=$(echo "$SUB" | tr -d ',' | tr ';' '_'); [ -z "$TAGSUB" ] && TAGSUB=triv
while [ $P -ge $PMIN ]; do
  LOG=results/E-024a-gross12-period/P${P}_s${TAGSUB}.log
  PYTHONPATH=.:tests uv run python -m search.experiments.e024a.cegar --P $P --sub "$SUB" --max_sec $MS --tag P${P}_s${TAGSUB} > $LOG 2>&1
  grep -q "CERTIFIED it=" $LOG || break
  P=$((P-1))
done
