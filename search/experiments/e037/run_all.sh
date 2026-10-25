#!/bin/sh
# E-037 production certificates: W = d_circ - 1 at the target R, both bases, both noise models; 3 jobs in parallel.
#   sh search/experiments/e037/run_all.sh
O=results/E-037-ibm-cert/cert
mkdir -p $O
printf '%s\n' \
  "ibm:gross:X:12 9" "ibm:gross:Z:12 9" "sd6:gross:Z:12 9" "sd6:gross:X:12 9" \
  "ibm:bb108:X:10 7" "ibm:bb108:Z:10 7" "sd6:bb108:Z:10 7" "sd6:bb108:X:10 7" |
  xargs -P 3 -L 1 sh -c 'uv run python search/experiments/e037/certify.py $0 $1 --out '$O' >> '$O'/driver.log 2>&1'
