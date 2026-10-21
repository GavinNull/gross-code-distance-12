#!/bin/bash
# E-033: ccsearch queue, NPAR parallel. Usage: run_cc.sh NPAR "inst mode W" ...   (instances from e029.export dem)
cd "$(dirname "$0")/../../.." || exit 1
O=results/E-033-gross-u11-ler
NPAR=$1; shift
for job in "$@"; do
  set -- $job
  while [ "$(jobs -rp | wc -l)" -ge "$NPAR" ]; do sleep 5; done
  if [ -f $O/runs/$1_$2$3.txt ] && grep -q "^DONE" $O/runs/$1_$2$3.txt; then continue; fi
  /usr/bin/time -p $O/ccsearch $O/inst/$1.txt $2 $3 > $O/runs/$1_$2$3.txt 2>&1 &
done
wait
