#!/bin/bash
# E-030: cegar9 sweep over subgroup families (wrapping allowed), class A1A2A3B2B1B3 both sides.
# Usage: sweep_cegar.sh NPAR MAXSEC "P1 P2 ..." "hs1" "hs2" ...
cd "$(dirname "$0")/../../.." || exit 1
O=results/E-030-bb90-period-ler
NPAR=$1; MAXSEC=$2; PS=$3; shift 3
for P in $PS; do
  for hs in "$@"; do
    t=$(echo "$hs" | tr ',;' '__')
    [ -f $O/cg9_hs${t}_P${P}_w.log ] && grep -q STATUS $O/cg9_hs${t}_P${P}_w.log && continue
    while [ "$(jobs -rp | wc -l)" -ge "$NPAR" ]; do sleep 2; done
    PYTHONPATH=.:tests uv run python -m search.experiments.e028.cegar9 --xo A1A2A3B2B1B3 --zo A1A2A3B2B1B3 \
      --hs "$hs" --P $P --nowrap 0 --max_sec $MAXSEC --tag ../E-030-bb90-period-ler/cg9_hs${t}_P${P}_w \
      > $O/cg9_hs${t}_P${P}_w.log 2>&1 &
  done
done
wait
