#!/bin/bash
# E-030: ccsearch queue (<= $NPAR parallel). Usage: run_cc.sh NPAR "inst mode W" ...
cd "$(dirname "$0")/../../.." || exit 1
O=results/E-030-bb90-period-ler
NPAR=$1; shift
for job in "$@"; do
  set -- $job
  while [ "$(jobs -rp | wc -l)" -ge "$NPAR" ]; do sleep 2; done
  /usr/bin/time -p $O/ccsearch $O/inst/$1.txt $2 $3 > $O/runs/$1_$2$3.txt 2>&1 &
done
wait
