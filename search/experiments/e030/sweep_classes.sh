#!/bin/bash
# E-030: uniform family (|Hs| = 45) cegar9 over all 4x4 combinations of the d_ext = 8 uniform classes.
# Usage: sweep_classes.sh "P list" NOWRAP MAXSEC
cd "$(dirname "$0")/../../.." || exit 1
O=results/E-030-bb90-period-ler
CL="A1A2A3B2B1B3 A1A2A3B3B1B2 A1A3A2B2B1B3 A1A3A2B3B1B2"
for P in $1; do for xo in $CL; do for zo in $CL; do
  t=cls_${xo}_${zo}_P${P}_$([ "$2" = 1 ] && echo nw || echo w)
  PYTHONPATH=.:tests uv run python -m search.experiments.e028.cegar9 --xo $xo --zo $zo --hs "0,1;1,0" --P $P \
    --nowrap $2 --max_sec $3 --tag ../E-030-bb90-period-ler/$t > $O/$t.log 2>&1
  echo "$t $(grep -h STATUS $O/$t.log)"
done; done; done
