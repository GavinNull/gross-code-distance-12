#!/bin/sh
# E-037 sweep: every R below the target (the target R itself is in run_all.sh), both bases, both noise models.
#   sh search/experiments/e037/run_sweep.sh [NPAR]
O=results/E-037-ibm-cert/sweep
mkdir -p $O
P=${1:-3}
{
  for R in 11 10 9 8 7 6 5 4 3 2 1; do for s in ibm:gross:X ibm:gross:Z sd6:gross:Z sd6:gross:X; do echo "$s:$R 9"; done; done
  for R in 9 8 7 6 5 4 3 2 1; do for s in ibm:bb108:X ibm:bb108:Z sd6:bb108:Z sd6:bb108:X; do echo "$s:$R 7"; done; done
} | xargs -P $P -L 1 sh -c 'uv run python search/experiments/e037/certify.py $0 $1 --out '$O' >> '$O'/driver.log 2>&1'
